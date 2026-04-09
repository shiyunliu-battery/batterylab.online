import json
import unittest

from battery_agent.cell_catalog import get_cell_catalog_record, load_cell_catalog, search_cell_catalog
from battery_agent.tools import plan_standard_test


class RegistryGovernanceAndNaIonAssetTests(unittest.TestCase):
    def test_formal_catalog_only_keeps_complete_approved_records(self) -> None:
        catalog = load_cell_catalog()
        record = get_cell_catalog_record("A123_20AH")
        sodium_record = get_cell_catalog_record("Unknown_NFM_18650_NaIon")

        self.assertEqual(catalog["manual_asset_count"], 3)
        self.assertEqual(catalog["record_count"], catalog["approved_record_count"])
        self.assertGreater(catalog["excluded_record_count"], 0)
        self.assertNotIn("unknown", catalog["counts_by_chemistry_hint"])
        self.assertIn("unknown", catalog["all_counts_by_chemistry_hint"])
        self.assertEqual(catalog["counts_by_chemistry_hint"]["sodium_ion"], 3)
        self.assertEqual(record["project_chemistry_hint"], "lfp")
        self.assertEqual(record["approval_status"], "approved")
        self.assertEqual(record["completeness_status"], "complete")
        self.assertTrue(record["eligible_for_planning"])
        self.assertEqual(sodium_record["manufacturer"], "Unknown")
        self.assertEqual(sodium_record["approval_status"], "approved")
        self.assertEqual(sodium_record["completeness_status"], "complete")
        self.assertEqual(sodium_record["confidence_status"], "literature_backed")
        self.assertEqual(sodium_record["approval_basis"], "literature_backed_manual_asset")
        self.assertEqual(sodium_record["waived_missing_required_fields"], ["cycle_life_cycles"])
        self.assertEqual(
            sodium_record["literature_reference"]["doi"],
            "10.1016/j.apenergy.2026.127687",
        )

    def test_literature_backed_sodium_assets_stay_on_formal_search_surface(self) -> None:
        catalog = load_cell_catalog()
        payload = search_cell_catalog("sodium", limit=10)

        self.assertEqual(payload["record_count"], 3)
        self.assertEqual(payload["records"][0]["approval_basis"], "literature_backed_manual_asset")
        self.assertEqual(payload["records"][0]["manufacturer"], "Unknown")
        self.assertIn("sodium_ion", catalog["all_counts_by_chemistry_hint"])
        self.assertIn("sodium_ion", catalog["counts_by_chemistry_hint"])

    def test_literature_backed_selected_cell_can_be_planned(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "pulse_hppc",
                    "selected_cell_id": "Unknown_NFM_18650_NaIon",
                    "instrument": "biologic_bcs815",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["selected_cell_id"], "Unknown_NFM_18650_NaIon")
        self.assertEqual(
            payload["selected_cell_reference"]["chemistry_hint"],
            "sodium_ion",
        )
        self.assertEqual(
            payload["constraint_sources"]["charge_voltage_v"],
            "selected_cell_imported_metadata",
        )
        self.assertEqual(
            payload["selected_cell_reference"]["approval_basis"],
            "literature_backed_manual_asset",
        )
        self.assertEqual(
            payload["selected_cell_reference"]["waived_missing_required_fields"],
            ["cycle_life_cycles"],
        )
        self.assertEqual(
            payload["selected_cell_reference"]["literature_reference"]["doi"],
            "10.1016/j.apenergy.2026.127687",
        )
        self.assertTrue(payload["requires_human_review"])
        self.assertGreater(len(payload["unresolved_registry_constraints"]), 0)

    def test_standard_method_plan_no_longer_surfaces_simulation_fields(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "soc_ocv",
                    "chemistry": "lfp",
                    "instrument": "biologic_bcs815",
                    "form_factor": "pouch",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["trust_level"], "draft_protocol")
        self.assertTrue(payload["requires_human_review"])
        self.assertNotIn("parameter_pack", payload)


if __name__ == "__main__":
    unittest.main()
