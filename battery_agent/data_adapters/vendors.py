"""Vendor-specific cycler adapters: Arbin and Neware."""

import csv
import io

import pandas as pd

from battery_agent.data_adapters.models import AdapterReadError
from battery_agent.data_adapters.base import BaseCyclerAdapter
from battery_agent.data_adapters.utils import (
    _clean_header_cell,
    _coerce_numeric_series,
    _parse_duration_series_to_seconds,
)


class ArbinAdapter(BaseCyclerAdapter):
    adapter_id = "arbin_csv_v1"
    vendor = "Arbin"

    def __init__(self) -> None:
        super().__init__("arbin.yaml")


class NewareAdapter(BaseCyclerAdapter):
    adapter_id = "neware_csv_v1"
    vendor = "Neware"

    def __init__(self) -> None:
        super().__init__("neware.yaml")

    def _read_text(self, text: str) -> pd.DataFrame:
        rows = self._read_rows(text)
        if self._looks_like_hierarchical_export(rows):
            return self._flatten_hierarchical_rows(rows)
        return super()._read_text(text)

    def _read_rows(self, text: str) -> list[list[str]]:
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
        except Exception as exc:
            raise AdapterReadError(f"Failed to read NEWARE text export: {exc}") from exc
        return [[_clean_header_cell(cell) for cell in row] for row in rows]

    def _looks_like_hierarchical_export(self, rows: list[list[str]]) -> bool:
        if len(rows) < 3:
            return False
        cycle_row = rows[0]
        step_row = rows[1]
        record_row = rows[2]
        return (
            len(cycle_row) > 0
            and cycle_row[0] == "Cycle ID"
            and len(step_row) > 1
            and step_row[1] == "Step ID"
            and "Time(h:min:s.ms)" in record_row
        )

    def _flatten_hierarchical_rows(self, rows: list[list[str]]) -> pd.DataFrame:
        cycle_row = rows[0]
        step_row = rows[1]
        record_row = rows[2]
        record_header = list(record_row)
        if not record_header:
            raise AdapterReadError("NEWARE hierarchical export is missing a record header row.")

        if len(record_header) > 0 and cycle_row:
            record_header[0] = cycle_row[0] or "Cycle ID"
        if len(record_header) > 1 and len(step_row) > 1:
            record_header[1] = step_row[1] or "Step ID"

        ir_header = "DCIR(O)"
        step_ir_index = next(
            (index for index, value in enumerate(step_row) if value == ir_header),
            None,
        )
        record_ir_index = next(
            (index for index, value in enumerate(record_header) if value == ir_header),
            None,
        )

        flattened_rows: list[list[str]] = []
        cycle_number = ""
        step_number = ""
        ir_value = ""
        width = len(record_header)

        for source_row in rows[3:]:
            row = list(source_row[:width]) + [""] * max(width - len(source_row), 0)
            first = row[0].strip() if len(row) > 0 else ""
            second = row[1].strip() if len(row) > 1 else ""

            if first:
                cycle_number = first
                continue
            if second:
                step_number = second
                if step_ir_index is not None and step_ir_index < len(row):
                    candidate = row[step_ir_index].strip()
                    if candidate and candidate != "-":
                        ir_value = candidate
                continue
            if not cycle_number:
                continue

            row[0] = cycle_number
            row[1] = step_number
            if record_ir_index is not None and record_ir_index < len(row):
                if not row[record_ir_index].strip():
                    row[record_ir_index] = ir_value
            flattened_rows.append(row)

        if not flattened_rows:
            raise AdapterReadError("NEWARE hierarchical export did not contain any record rows.")

        return pd.DataFrame(flattened_rows, columns=record_header)

    def _normalize_vendor_fields(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = super()._normalize_vendor_fields(frame)
        if "internal_resistance_ohm" in frame.columns:
            frame["internal_resistance_ohm"] = frame["internal_resistance_ohm"].ffill().bfill()

        if "test_time_s" not in frame.columns and "step_time_s" in frame.columns:
            step_time = frame["step_time_s"].fillna(0)
            deltas = step_time.diff().fillna(0)
            frame["test_time_s"] = deltas.where(deltas >= 0, 0).cumsum()

        return frame
