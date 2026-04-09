"""Integration test suite for battery_agent data adapters + tool layer."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from battery_agent.data_adapters import (
    detect_adapter_id_from_text,
    parse_raw_export_file,
    parse_raw_export_text,
)
from battery_agent.tools import _adapter_result_to_payload, _parse_raw_cycler_export_impl


# ---------------------------------------------------------------------------
# Sample datasets
# ---------------------------------------------------------------------------

ARBIN_SAMPLE = """Test_Time,DateTime,Step_Time,Step_Index,Cycle_Index,Current,Voltage,Charge_Capacity,Discharge_Capacity,Charge_Energy,Discharge_Energy,dV/dt,Internal_Resistance,Temperature,Data_Point
0,2026-04-02 00:00:00,0,1,1,0.5,3.21,0.00,0.00,0.00,0.00,0.00,0.012,24.8,1
60,2026-04-02 00:01:00,60,1,1,0.5,3.30,0.01,0.00,0.03,0.00,0.00,0.012,24.9,2
120,2026-04-02 00:02:00,120,2,1,-1.0,3.10,0.01,0.02,0.03,0.06,0.00,0.013,25.1,3
"""

NEWARE_HIERARCHICAL_SAMPLE = """Cycle ID,,,,,,,,,,,,,,,,,,,,,,
,Step ID,,,,,,,,,,,,,,,,,,,,,DCIR(O)
,,Record ID,Time(h:min:s.ms),Voltage(V),Current(mA),Temperature(C),Capacity(mAh),Capacity Density(mAh/g),Energy(mWh),CmpEng(mWh/g),Realtime,Min-T(C),Max-T(C),Avg-T(C),Power(mW),Capacitance_Chg(mAh),Capacitance_DChg(mAh),Engy_Chg(mWh),Engy_DChg(mWh),dQ/dV(mAh/V),dQm/dV(mAh/V.g),DCIR(O)
1,,,,,,,,,,,,,,,,,,,,,,
,1,,,,,,,,,,,,,,,,,,,,,0.015
,,1,0:00:01.0,3.20,1000,25,,,,,2026-04-02 00:00:01,,,,,500,0,750,0,,,
,,2,0:00:02.0,3.22,1000,25.1,,,,,2026-04-02 00:00:02,,,,,1000,0,1500,0,,,
2,,,,,,,,,,,,,,,,,,,,,,
,1,,,,,,,,,,,,,,,,,,,,,0.020
,,1,0:00:01.0,3.15,-500,25.3,,,,,2026-04-02 00:10:01,,,,,0,250,0,375,,,
"""

GENERIC_SPREADSHEET_PREVIEW = """Attachment extraction preview
Original filename: LFP_k1_0_05C_05degC.xlsx
MIME type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Extraction mode: spreadsheet preview

## Sheet: Sheet1
Date_Time\tTest_Time(s)\tStep_Time(s)\tStep_Index\tVoltage(V)\tCurrent(A)\tSurface_Temp(degC)
2019-11-19 15:10:57\t0\t0\t1\t3.186\t0\t7.4
2019-11-19 15:10:58\t1\t1\t1\t3.186\t0\t7.4
[Preview truncated after 50 rows.]
"""

GENERIC_CAPACITY_SUMMARY = """,CycleReorder,Amphr
1159,1,0.025283
2110,2,0.025210
3010,3,0.025101
"""

GENERIC_BIOLOGIC_STYLE = """time/s,control/V/mA,Ecell/V,<I>/mA,Q discharge/mA.h,Q charge/mA.h,control/V,control/mA,cycle number
0,1250.0,4.052,1251,0.0,0.0,4.2,1250.0,1
10,1250.0,4.062,1251,0.0,3.48,4.2,1250.0,1
20,1250.0,4.070,1251,0.0,6.95,4.2,1250.0,1
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class DataAdapterTests(unittest.TestCase):

    @staticmethod
    def _thread_file_value(content: str, **extra_fields: object) -> dict[str, object]:
        return {
            "content": content.splitlines(),
            "created_at": "2026-04-02T13:00:00Z",
            "modified_at": "2026-04-02T13:00:00Z",
            **extra_fields,
        }

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def test_detect_adapter_id_from_text(self) -> None:
        arbin_id, _ = detect_adapter_id_from_text(ARBIN_SAMPLE)
        neware_id, _ = detect_adapter_id_from_text(NEWARE_HIERARCHICAL_SAMPLE)
        self.assertEqual(arbin_id, "arbin_csv_v1")
        self.assertEqual(neware_id, "neware_csv_v1")

    # ------------------------------------------------------------------
    # Arbin
    # ------------------------------------------------------------------

    def test_parse_arbin_export_text_uses_canonical_columns(self) -> None:
        result = parse_raw_export_text(ARBIN_SAMPLE, source_name="/uploads/test-arbin.csv")

        self.assertEqual(result.adapter_id, "arbin_csv_v1")
        self.assertEqual(
            list(result.frame.columns[:5]),
            ["cycle_index", "step_index", "test_time_s", "current_a", "voltage_v"],
        )
        self.assertAlmostEqual(float(result.frame.loc[1, "charge_capacity_ah"]), 0.01)
        self.assertEqual(result.raw_columns[0], "Test_Time")

    # ------------------------------------------------------------------
    # Neware hierarchical
    # ------------------------------------------------------------------

    def test_parse_neware_hierarchical_export_applies_time_and_unit_scaling(self) -> None:
        result = parse_raw_export_text(
            NEWARE_HIERARCHICAL_SAMPLE, source_name="/uploads/test-neware.csv"
        )

        self.assertEqual(result.adapter_id, "neware_csv_v1")
        self.assertEqual(len(result.frame), 3)
        self.assertAlmostEqual(float(result.frame.loc[0, "current_a"]), 1.0)
        self.assertAlmostEqual(float(result.frame.loc[0, "charge_capacity_ah"]), 0.5)
        self.assertAlmostEqual(float(result.frame.loc[2, "discharge_capacity_ah"]), 0.25)
        self.assertAlmostEqual(float(result.frame.loc[0, "step_time_s"]), 1.0)
        self.assertAlmostEqual(float(result.frame.loc[2, "test_time_s"]), 1.0)
        self.assertAlmostEqual(float(result.frame.loc[0, "internal_resistance_ohm"]), 0.015)

    # ------------------------------------------------------------------
    # File parse + tool payload (via _adapter_result_to_payload)
    # ------------------------------------------------------------------

    def test_parse_raw_export_file_and_tool_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample_arbin.csv"
            path.write_text(ARBIN_SAMPLE, encoding="utf-8")

            parse_result = parse_raw_export_file(path)
            self.assertEqual(parse_result.adapter_vendor, "Arbin")

            tool_payload = _adapter_result_to_payload(parse_result, preview_rows=2)

        self.assertEqual(tool_payload["status"], "ok")
        self.assertEqual(tool_payload["adapter_id"], "arbin_csv_v1")
        self.assertEqual(tool_payload["row_count"], 3)
        self.assertEqual(len(tool_payload["preview_rows"]), 2)
        self.assertEqual(
            tool_payload["generated_files"][0]["generated_file_kind"], "parsed_cycler_summary"
        )
        self.assertEqual(
            tool_payload["generated_files"][1]["generated_file_kind"], "parsed_cycler_dataset"
        )
        self.assertIn("sample-arbin-normalized.csv", tool_payload["generated_files"][1]["path"])
        # header + 3 data rows = 4 lines
        self.assertEqual(
            len(tool_payload["generated_files"][1]["content"].strip().splitlines()), 4
        )

    # ------------------------------------------------------------------
    # Generic – spreadsheet preview
    # ------------------------------------------------------------------

    def test_parse_generic_spreadsheet_preview_text(self) -> None:
        result = parse_raw_export_text(
            GENERIC_SPREADSHEET_PREVIEW, source_name="/uploads/sample-preview.xlsx.txt"
        )

        self.assertEqual(result.adapter_id, "generic_battery_tabular_v1")
        self.assertEqual(result.dataset_kind, "raw_timeseries")
        self.assertTrue(result.preview_only)
        self.assertIn("voltage_v", result.frame.columns)
        self.assertIn("current_a", result.frame.columns)
        self.assertAlmostEqual(float(result.frame.loc[0, "voltage_v"]), 3.186)

    # ------------------------------------------------------------------
    # Generic – cycle-level capacity summary
    # ------------------------------------------------------------------

    def test_parse_generic_capacity_summary_text(self) -> None:
        result = parse_raw_export_text(
            GENERIC_CAPACITY_SUMMARY, source_name="/uploads/capacity-summary.csv"
        )

        self.assertEqual(result.adapter_id, "generic_battery_tabular_v1")
        self.assertEqual(result.dataset_kind, "cycle_summary")
        self.assertIn("cycle_index", result.frame.columns)
        self.assertIn("capacity_ah", result.frame.columns)
        self.assertAlmostEqual(float(result.frame.loc[0, "capacity_ah"]), 0.025283)

        payload = _adapter_result_to_payload(result, preview_rows=2)
        self.assertEqual(payload["required_fields"], [])
        self.assertEqual(payload["missing_required_fields"], [])
        self.assertIn("## Inspected Battery Dataset", payload["ui_markdown"])

    # ------------------------------------------------------------------
    # Generic – Biologic-style CSV
    # ------------------------------------------------------------------

    def test_parse_generic_biologic_style_csv(self) -> None:
        result = parse_raw_export_text(
            GENERIC_BIOLOGIC_STYLE, source_name="/uploads/biologic-style.csv"
        )

        self.assertEqual(result.adapter_id, "generic_battery_tabular_v1")
        self.assertEqual(result.dataset_kind, "raw_timeseries")
        self.assertAlmostEqual(float(result.frame.loc[0, "current_a"]), 1.251)
        self.assertAlmostEqual(float(result.frame.loc[1, "charge_capacity_ah"]), 0.00348)

    # ------------------------------------------------------------------
    # Thread-file upload lookup via runtime state
    # ------------------------------------------------------------------

    def test_parse_uploaded_thread_file_uses_runtime_state_files_fallback(self) -> None:
        runtime = SimpleNamespace(
            state={
                "files": {
                    "/uploads/current-thread-arbin.csv": self._thread_file_value(
                        ARBIN_SAMPLE,
                        hidden=True,
                        original_filename="current-thread-arbin.csv",
                    )
                }
            }
        )

        payload = json.loads(
            _parse_raw_cycler_export_impl(
                "/uploads/current-thread-arbin.csv",
                preview_rows=2,
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source_file"], "/uploads/current-thread-arbin.csv")
        self.assertEqual(payload["adapter_id"], "arbin_csv_v1")

    def test_parse_uploaded_thread_file_recovers_after_reupload_with_new_uuid(self) -> None:
        current_thread_path = "/uploads/newuuid-LFP_k1_0_05C_05degC.xlsx.txt"
        runtime = SimpleNamespace(
            state={
                "files": {
                    current_thread_path: self._thread_file_value(
                        GENERIC_SPREADSHEET_PREVIEW,
                        hidden=True,
                        original_filename="LFP_k1_0_05C_05degC.xlsx",
                    )
                }
            }
        )

        payload = json.loads(
            _parse_raw_cycler_export_impl(
                "/uploads/olduuid-LFP_k1_0_05C_05degC.xlsx.txt",
                preview_rows=2,
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source_file"], current_thread_path)
        self.assertEqual(payload["adapter_id"], "generic_battery_tabular_v1")
        self.assertTrue(payload["preview_only"])

    def test_parse_uploaded_attachment_text_without_runtime_file_lookup(self) -> None:
        payload = json.loads(
            _parse_raw_cycler_export_impl(
                "/uploads/missing-preview.xlsx.txt",
                attachment_text=GENERIC_SPREADSHEET_PREVIEW,
                preview_rows=2,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source_file"], "/uploads/missing-preview.xlsx.txt")
        self.assertEqual(payload["adapter_id"], "generic_battery_tabular_v1")
        self.assertEqual(payload["dataset_kind"], "raw_timeseries")
        self.assertTrue(payload["preview_only"])


if __name__ == "__main__":
    unittest.main()
