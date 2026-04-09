"""Generic tabular parser and heuristics."""

import pandas as pd

from battery_agent.data_adapters.models import AdapterReadError, AdapterDetectionError
from battery_agent.data_adapters.schema import MAPPER_CONFIG_DIR
from battery_agent.data_adapters.utils import (
    _clean_header_cell,
    _coerce_numeric_series,
    _normalize_header_key,
    _parse_duration_series_to_seconds,
)
from battery_agent.data_adapters.base import BaseCyclerAdapter

ATTACHMENT_PREVIEW_PREFIX = "Attachment extraction preview"

GENERIC_ALIAS_SPECS: dict[str, list[tuple[str, float]]] = {
    "cycle_index": [
        ("cycleindex", 1.0),
        ("cycleid", 1.0),
        ("cyclenumber", 1.0),
        ("cyclereorder", 1.0),
    ],
    "step_index": [
        ("stepindex", 1.0),
        ("stepid", 1.0),
    ],
    "data_point_index": [
        ("datapoint", 1.0),
        ("recordid", 1.0),
        ("index", 1.0),
    ],
    "test_time_s": [
        ("testtimes", 1.0),
        ("testtime", 1.0),
        ("times", 1.0),
        ("timesec", 1.0),
    ],
    "step_time_s": [
        ("steptimes", 1.0),
        ("steptime", 1.0),
        ("timehminsms", 1.0),
    ],
    "timestamp_iso": [
        ("datetime", 1.0),
        ("datetimeiso", 1.0),
        ("realtime", 1.0),
        ("date_time", 1.0),
    ],
    "current_a": [
        ("currenta", 1.0),
        ("current", 1.0),
        ("ima", 0.001),
        ("currentma", 0.001),
        ("controlma", 0.001),
    ],
    "voltage_v": [
        ("voltagev", 1.0),
        ("voltage", 1.0),
        ("ecellv", 1.0),
        ("controlv", 1.0),
    ],
    "power_w": [
        ("powerw", 1.0),
        ("powermw", 0.001),
    ],
    "charge_capacity_ah": [
        ("chargecapacityah", 1.0),
        ("chargecapacity", 1.0),
        ("capacitancechgmah", 0.001),
        ("qchargemah", 0.001),
    ],
    "discharge_capacity_ah": [
        ("dischargecapacityah", 1.0),
        ("dischargecapacity", 1.0),
        ("capacitancedchgmah", 0.001),
        ("qdischargemah", 0.001),
    ],
    "charge_energy_wh": [
        ("chargeenergywh", 1.0),
        ("chargeenergy", 1.0),
        ("engychgmwh", 0.001),
    ],
    "discharge_energy_wh": [
        ("dischargeenergywh", 1.0),
        ("dischargeenergy", 1.0),
        ("engydchgmwh", 0.001),
    ],
    "temperature_c": [
        ("temperaturec", 1.0),
        ("auxtemperature1c", 1.0),
        ("surfacetempdegc", 1.0),
        ("avgtc", 1.0),
        ("maxtc", 1.0),
        ("mintc", 1.0),
    ],
    "internal_resistance_ohm": [
        ("internalresistanceohm", 1.0),
        ("internalresistance", 1.0),
        ("dciro", 1.0),
        ("acrohm", 1.0),
    ],
    "dv_dt_v_per_s": [
        ("dvdtvs", 1.0),
    ],
    "capacity_ah": [
        ("amphr", 1.0),
        ("capacityah", 1.0),
    ],
}


def _frame_is_battery_like(frame: pd.DataFrame) -> bool:
    normalized_columns = {_normalize_header_key(column) for column in frame.columns}
    matched_fields = 0
    for aliases in GENERIC_ALIAS_SPECS.values():
        if any(alias in normalized_columns for alias, _scale in aliases):
            matched_fields += 1
    return matched_fields >= 2


def _parse_spreadsheet_preview_text(text: str) -> tuple[pd.DataFrame, list[str]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sheet_rows: list[list[str]] = []
    warnings: list[str] = ["Parsed from spreadsheet preview text; this may be truncated."]
    in_sheet = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Sheet:"):
            in_sheet = True
            if sheet_rows:
                break
            continue
        if not in_sheet:
            continue
        if stripped.startswith("## Sheet:"):
            break
        if not stripped:
            if sheet_rows:
                break
            continue
        if stripped.startswith("[Preview truncated") or stripped.startswith("[Truncated after"):
            warnings.append(stripped)
            break
        sheet_rows.append([cell.strip() for cell in line.split("\t")])

    if len(sheet_rows) < 2:
        raise AdapterReadError("Spreadsheet preview did not contain a usable tabular section.")

    header = sheet_rows[0]
    width = max(len(header), *(len(row) for row in sheet_rows[1:]))
    padded_header = list(header) + [f"column_{index}" for index in range(len(header), width)]
    padded_rows = [
        list(row[:width]) + [""] * max(width - len(row), 0)
        for row in sheet_rows[1:]
    ]
    return pd.DataFrame(padded_rows, columns=padded_header), warnings


def _generic_alias_maps(columns: list[str]) -> tuple[dict[str, str], dict[str, float], list[str]]:
    normalized_lookup = {_normalize_header_key(column): column for column in columns}
    rename_map: dict[str, str] = {}
    scale_map: dict[str, float] = {}
    warnings: list[str] = []

    for semantic_field, aliases in GENERIC_ALIAS_SPECS.items():
        for alias_key, scale in aliases:
            raw_column = normalized_lookup.get(alias_key)
            if not raw_column:
                continue
            if raw_column in rename_map:
                continue
            rename_map[raw_column] = semantic_field
            if scale != 1.0:
                scale_map[semantic_field] = scale
            break

    if not rename_map:
        raise AdapterDetectionError(
            "Could not recognize battery-relevant columns in the uploaded table."
        )

    return rename_map, scale_map, warnings


def classify_generic_dataset(columns: list[str]) -> tuple[str, str, str]:
    """Classifies a battery dataset using heuristic generic parsing."""
    column_set = set(columns)
    if {"current_a", "voltage_v"} & column_set and (
        {"test_time_s", "step_time_s", "timestamp_iso", "cycle_index"} & column_set
    ):
        return ("raw_timeseries", "battery_timeseries_v1_partial", "Recognized fields")
    if "cycle_index" in column_set and (
        {"capacity_ah", "charge_capacity_ah", "discharge_capacity_ah"} & column_set
    ):
        return ("cycle_summary", "battery_cycle_summary_preview_v1", "Recognized fields")
    return ("tabular_preview", "battery_tabular_preview_v1", "Recognized fields")


class GenericBatteryTabularAdapter(BaseCyclerAdapter):
    adapter_id = "generic_battery_tabular_v1"
    vendor = "Generic battery tabular"

    def __init__(self) -> None:
        self.config_path = MAPPER_CONFIG_DIR / "generic"
        self.config = {}
        self.column_mapping = {}
        self.data_types = {}
        self.scales = {}

    def matching_signals(self) -> set[str]:
        signals: set[str] = set()
        for aliases in GENERIC_ALIAS_SPECS.values():
            signals.update(alias for alias, _scale in aliases)
        return signals

    def sniff_text(self, text: str) -> bool:
        if ATTACHMENT_PREVIEW_PREFIX in text and "spreadsheet preview" in text.lower():
            return True

        try:
            frame = self._read_text(text)
        except AdapterReadError:
            return False
        return _frame_is_battery_like(frame)

    def _read_text(self, text: str) -> pd.DataFrame:
        if ATTACHMENT_PREVIEW_PREFIX in text and "spreadsheet preview" in text.lower():
            frame, _warnings = _parse_spreadsheet_preview_text(text)
            return frame
        return super()._read_text(text)

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            raise AdapterReadError("Parsed dataframe is empty.")

        working = frame.copy()
        working.columns = [_clean_header_cell(column) for column in working.columns]
        rename_map, scale_map, _warnings = _generic_alias_maps(list(working.columns))
        working = working.rename(columns=rename_map)
        working = working.loc[:, ~working.columns.duplicated()].copy()

        for column, scale in scale_map.items():
            if column in working.columns:
                working[column] = _coerce_numeric_series(working[column]) * scale

        for integer_column in ("cycle_index", "step_index", "data_point_index"):
            if integer_column in working.columns:
                working[integer_column] = _coerce_numeric_series(working[integer_column]).astype("Int64")

        for time_field in ("test_time_s", "step_time_s"):
            if time_field in working.columns:
                working[time_field] = _parse_duration_series_to_seconds(working[time_field])

        numeric_columns = (
            "current_a",
            "voltage_v",
            "charge_capacity_ah",
            "discharge_capacity_ah",
            "charge_energy_wh",
            "discharge_energy_wh",
            "temperature_c",
            "internal_resistance_ohm",
            "dv_dt_v_per_s",
            "power_w",
            "capacity_ah",
        )
        for column in numeric_columns:
            if column in working.columns:
                working[column] = _coerce_numeric_series(working[column])

        if "test_time_s" not in working.columns and "step_time_s" in working.columns:
            working["test_time_s"] = working["step_time_s"]

        sort_columns = [
            column
            for column in ("cycle_index", "test_time_s", "step_time_s", "data_point_index")
            if column in working.columns
        ]
        if sort_columns:
            working = working.sort_values(sort_columns, kind="stable")

        return working.reset_index(drop=True)
