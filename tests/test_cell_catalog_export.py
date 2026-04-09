import csv
import io
import json
import unittest

from battery_agent.cell_catalog import load_cell_catalog
from battery_agent.tools import export_imported_cell_catalog, search_imported_cell_catalog


class CellCatalogExportTests(unittest.TestCase):
    @staticmethod
    def _count_records(field_name: str, expected_value: str) -> int:
        catalog = load_cell_catalog()
        normalized_expected = expected_value.strip().lower()
        return sum(
            1
            for record in catalog.get("cells", [])
            if str(record.get(field_name) or "").strip().lower() == normalized_expected
        )

    def test_search_imported_cell_catalog_reports_filter_match_counts(self) -> None:
        expected_count = self._count_records("project_chemistry_hint", "lfp")

        payload = json.loads(
            search_imported_cell_catalog.invoke(
                {
                    "filter_field": "project_chemistry_hint",
                    "filter_value": "lfp",
                    "limit": 5,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["matched_record_count"], expected_count)
        self.assertEqual(payload["post_distinct_record_count"], expected_count)
        self.assertEqual(payload["returned_record_count"], 5)
        self.assertEqual(payload["record_count"], 5)
        self.assertEqual(payload["applied_filter"]["field"], "project_chemistry_hint")
        self.assertEqual(payload["applied_filter"]["value"], "lfp")
        self.assertIn("Total matches before distinct/limit", payload["ui_markdown"])
        self.assertIn("Exact filter", payload["ui_markdown"])

    def test_export_imported_cell_catalog_csv_is_structured_and_consistent(self) -> None:
        expected_count = self._count_records(
            "positive_electrode_type",
            "LithiumIronPhosphate",
        )

        payload = json.loads(
            export_imported_cell_catalog.invoke(
                {
                    "filter_field": "positive_electrode_type",
                    "filter_value": "LithiumIronPhosphate",
                    "format": "csv",
                    "limit": 200,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["export_format"], "csv")
        self.assertEqual(payload["matched_record_count"], expected_count)
        self.assertEqual(payload["exported_record_count"], expected_count)
        self.assertEqual(len(payload["generated_files"]), 1)
        self.assertIn("Exported cells matching Positive Electrode = LithiumIronPhosphate to CSV.", payload["ui_markdown"])
        self.assertIn("- Rows: 71", payload["ui_markdown"])
        self.assertIn("- File: `lithiumironphosphate-positive-electrode-type-cells.csv`", payload["ui_markdown"])
        self.assertIn("- Filter: Positive Electrode = LithiumIronPhosphate", payload["ui_markdown"])
        self.assertNotIn("Approved records in full active catalog", payload["ui_markdown"])
        self.assertNotIn("/exports/", payload["ui_markdown"])

        generated_file = payload["generated_files"][0]
        self.assertTrue(generated_file["path"].endswith(".csv"))
        csv_rows = list(csv.DictReader(io.StringIO(generated_file["content"])))
        self.assertEqual(len(csv_rows), expected_count)
        self.assertEqual(
            csv_rows[0]["positive_electrode_type"],
            "LithiumIronPhosphate",
        )
        self.assertIn("cell_id", csv_rows[0])
        self.assertIn("nominal_capacity_ah", csv_rows[0])

    def test_export_imported_cell_catalog_txt_is_human_readable(self) -> None:
        payload = json.loads(
            export_imported_cell_catalog.invoke(
                {
                    "filter_field": "project_chemistry_hint",
                    "filter_value": "lfp",
                    "format": "txt",
                    "limit": 3,
                    "columns_json": json.dumps(
                        ["cell_id", "manufacturer", "display_name"]
                    ),
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        generated_file = payload["generated_files"][0]
        self.assertTrue(generated_file["path"].endswith(".txt"))
        self.assertIn("Imported Cell Catalog Export", generated_file["content"])
        self.assertIn("Cell ID", generated_file["content"])
        self.assertIn("Manufacturer", generated_file["content"])
        self.assertNotIn('"records"', generated_file["content"])


if __name__ == "__main__":
    unittest.main()
