"""Base abstract class for raw cycler adapters."""

import csv
import io
from pathlib import Path

import pandas as pd

from battery_agent.data_adapters.models import AdapterReadError, AdapterSchemaError
from battery_agent.data_adapters.schema import (
    MAPPER_CONFIG_DIR,
    _load_yaml,
    canonical_field_names,
    required_canonical_fields,
)
from battery_agent.data_adapters.utils import (
    _clean_header_cell,
    _coerce_numeric_series,
    _parse_duration_series_to_seconds,
)


class BaseCyclerAdapter:
    """Shared adapter logic for vendor raw-export normalization."""

    adapter_id = "base"
    vendor = "Unknown"

    def __init__(self, config_name: str):
        self.config_path = MAPPER_CONFIG_DIR / config_name
        self.config = _load_yaml(self.config_path)
        self.column_mapping = self._load_column_mapping()
        self.data_types = self._load_data_types()
        self.scales = self._load_scales()

    def _load_column_mapping(self) -> dict[str, str]:
        mapping = self.config.get("column_names", {})
        if not isinstance(mapping, dict) or not mapping:
            raise AdapterSchemaError(
                f"Mapper config `{self.config_path}` must define `column_names`."
            )
        return {
            str(raw_name): str(canonical_name)
            for canonical_name, raw_name in mapping.items()
            if raw_name
        }

    def _load_data_types(self) -> dict[str, str]:
        mapping = self.config.get("data_types", {})
        if not isinstance(mapping, dict):
            return {}
        return {str(name): str(dtype) for name, dtype in mapping.items()}

    def _load_scales(self) -> dict[str, float]:
        mapping = self.config.get("scales", {})
        if not isinstance(mapping, dict):
            return {}
        normalized: dict[str, float] = {}
        for name, scale in mapping.items():
            try:
                normalized[str(name)] = float(scale)
            except (TypeError, ValueError) as exc:
                raise AdapterSchemaError(
                    f"Invalid scale `{scale}` for `{name}` in `{self.config_path}`."
                ) from exc
        return normalized

    def matching_signals(self) -> set[str]:
        return {_clean_header_cell(raw_name) for raw_name in self.column_mapping}

    def sniff_text(self, text: str) -> bool:
        header_candidates = self._extract_header_candidates(text)
        signals = self.matching_signals()
        return any(signals.intersection(candidate) for candidate in header_candidates)

    def _extract_header_candidates(self, text: str) -> list[set[str]]:
        lines = [line for line in text.splitlines() if line.strip()]
        candidates: list[set[str]] = []
        for line in lines[:3]:
            parsed = next(csv.reader([line]), [])
            candidates.append({_clean_header_cell(item) for item in parsed if _clean_header_cell(item)})
        return candidates

    def process_file(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Raw data file `{path}` not found.")
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            return self.process_text(text, source_name=str(path))
        if suffix in {".xls", ".xlsx"}:
            frame = self._read_excel(path)
            return self._normalize_frame(frame)
        raise AdapterReadError(f"Unsupported file format: `{suffix or 'unknown'}`.")

    def process_text(self, text: str, *, source_name: str = "<memory>") -> pd.DataFrame:
        if not text.strip():
            raise AdapterReadError(f"Raw export `{source_name}` is empty.")
        frame = self._read_text(text)
        return self._normalize_frame(frame)

    def _read_text(self, text: str) -> pd.DataFrame:
        try:
            return pd.read_csv(io.StringIO(text), sep=None, engine="python")
        except Exception as exc:
            raise AdapterReadError(f"Failed to read delimited export text: {exc}") from exc

    def _read_excel(self, path: Path) -> pd.DataFrame:
        try:
            workbook = pd.read_excel(path, sheet_name=None)
        except Exception as exc:
            raise AdapterReadError(f"Failed to read Excel export `{path}`: {exc}") from exc

        sheets = [
            frame
            for sheet_name, frame in workbook.items()
            if str(sheet_name).strip().lower() not in {"info", "metadata"}
        ]
        if not sheets:
            raise AdapterReadError(f"No visible sheets found in `{path}`.")
        return pd.concat(sheets, ignore_index=True)

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            raise AdapterReadError("Parsed dataframe is empty.")

        working = frame.copy()
        working.columns = [_clean_header_cell(column) for column in working.columns]
        raw_columns = list(working.columns)

        rename_map = {
            raw_name: canonical_name
            for raw_name, canonical_name in self.column_mapping.items()
            if raw_name in working.columns
        }
        working = working.rename(columns=rename_map)
        working = working.loc[:, ~working.columns.duplicated()].copy()
        working = self._normalize_vendor_fields(working)
        working = self._apply_scales(working)
        working = self._coerce_declared_types(working)
        working = self._fill_default_time_fields(working)
        working = self._sort_rows(working)
        working = self._validate_required_fields(working, raw_columns)

        ordered_columns = [
            field for field in canonical_field_names() if field in working.columns
        ]
        trailing_columns = [column for column in working.columns if column not in ordered_columns]
        return working[ordered_columns + trailing_columns].reset_index(drop=True)

    def _normalize_vendor_fields(self, frame: pd.DataFrame) -> pd.DataFrame:
        if "cycle_index" in frame.columns:
            frame["cycle_index"] = _coerce_numeric_series(frame["cycle_index"]).astype("Int64")
        if "step_index" in frame.columns:
            frame["step_index"] = _coerce_numeric_series(frame["step_index"]).astype("Int64")
        if "data_point_index" in frame.columns:
            frame["data_point_index"] = _coerce_numeric_series(frame["data_point_index"]).astype("Int64")

        for time_field in ("test_time_s", "step_time_s"):
            if time_field in frame.columns:
                frame[time_field] = _parse_duration_series_to_seconds(frame[time_field])

        if "timestamp_iso" in frame.columns:
            frame["timestamp_iso"] = frame["timestamp_iso"].astype(str).str.strip()
            frame.loc[
                frame["timestamp_iso"].isin({"", "nan", "None"}),
                "timestamp_iso",
            ] = pd.NA

        numeric_fields = {
            "current_a",
            "voltage_v",
            "charge_capacity_ah",
            "discharge_capacity_ah",
            "charge_energy_wh",
            "discharge_energy_wh",
            "temperature_c",
            "internal_resistance_ohm",
            "dv_dt_v_per_s",
        }
        for field in numeric_fields:
            if field in frame.columns:
                frame[field] = _coerce_numeric_series(frame[field])

        return frame

    def _apply_scales(self, frame: pd.DataFrame) -> pd.DataFrame:
        for column, scale in self.scales.items():
            if column not in frame.columns:
                continue
            frame[column] = _coerce_numeric_series(frame[column]) * scale
        return frame

    def _coerce_declared_types(self, frame: pd.DataFrame) -> pd.DataFrame:
        for column, dtype in self.data_types.items():
            if column not in frame.columns:
                continue
            if dtype.startswith("int"):
                frame[column] = _coerce_numeric_series(frame[column]).astype("Int64")
                continue
            if dtype.startswith("float"):
                frame[column] = _coerce_numeric_series(frame[column]).astype("float64")
                continue
            if dtype in {"string", "str"}:
                frame[column] = frame[column].astype("string")
        return frame

    def _fill_default_time_fields(self, frame: pd.DataFrame) -> pd.DataFrame:
        if "test_time_s" not in frame.columns and "step_time_s" in frame.columns:
            frame["test_time_s"] = frame["step_time_s"]
        return frame

    def _sort_rows(self, frame: pd.DataFrame) -> pd.DataFrame:
        sort_columns = [
            column
            for column in ("cycle_index", "test_time_s", "step_time_s", "data_point_index")
            if column in frame.columns
        ]
        if sort_columns:
            frame = frame.sort_values(sort_columns, kind="stable")
        return frame

    def _validate_required_fields(
        self,
        frame: pd.DataFrame,
        raw_columns: list[str],
    ) -> pd.DataFrame:
        missing = [field for field in required_canonical_fields() if field not in frame.columns]
        if missing:
            raise AdapterSchemaError(
                "Missing required canonical fields after normalization: "
                + ", ".join(missing)
                + ". Raw columns detected: "
                + ", ".join(raw_columns)
            )
        return frame
