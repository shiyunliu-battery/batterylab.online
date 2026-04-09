import json
import unittest

from battery_agent.kb import REPO_ROOT
from battery_agent.equipment_manuals import get_equipment_manual_asset
from battery_agent.tools import load_equipment_manual_knowledge, search_equipment_manual_knowledge


class EquipmentManualAssetTests(unittest.TestCase):
    def test_manual_index_contains_neware_btsclient_manual(self) -> None:
        path = REPO_ROOT / "data" / "reference" / "equipment_manuals" / "manual_index.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "seeded")
        asset_ids = {item["asset_id"] for item in payload["manuals"]}
        self.assertIn("neware_btsclient8_user_manual", asset_ids)
        self.assertIn("ivium_connecting_electrodes_quick_guide", asset_ids)
        self.assertIn("ivium_quick_reference_guide", asset_ids)
        self.assertIn("ivium_eis_theory_application_note", asset_ids)
        self.assertIn("ivium_eis_setting_up_measurement_note", asset_ids)
        self.assertIn("ivium_eis_equivalent_circuit_fitting_note", asset_ids)
        self.assertIn("ivium_eis_worked_example_note", asset_ids)
        self.assertIn("ivium_compactstat2h_standard_datasheet", asset_ids)
        self.assertIn("iviumstat2h_datasheet", asset_ids)
        self.assertIn("neware_bts4000_100v60a_1ch_datasheet", asset_ids)
        self.assertIn("neware_bts4000_5v6a_8ch_datasheet", asset_ids)
        self.assertIn("neware_ct4008_5v30a_na_datasheet", asset_ids)
        self.assertIn("binder_lit_mk_battery_test_chamber_manual", asset_ids)

    def test_neware_manual_summary_exists_and_states_scope_boundary(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "neware_btsclient8_user_manual.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("What This Manual Can And Cannot Confirm", content)
        self.assertIn("not enough", content.lower())
        self.assertIn("hardware datasheet", content.lower())
        self.assertIn("NDA", content)
        self.assertIn("Excel", content)

    def test_ivium_connection_guide_summary_exists_and_keeps_wiring_scope(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "ivium_connecting_electrodes_quick_guide.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("Structured Wiring Guidance", content)
        self.assertIn("WE", content)
        self.assertIn("CE", content)
        self.assertIn("sense", content.lower())
        self.assertIn("does not provide model-specific electrical limits", content.lower())

    def test_ivium_quick_reference_summary_exists_and_keeps_readiness_scope(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "ivium_quick_reference_guide.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("Performance test", content)
        self.assertIn("serial number", content)
        self.assertIn("firmware", content.lower())
        self.assertIn("does not provide the hardware electrical limits", content.lower())

    def test_ivium_eis_setup_note_summary_exists_and_keeps_measurement_scope(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "ivium_eis_setting_up_measurement_note.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("Constant E", content)
        self.assertIn("PotentialScan", content)
        self.assertIn("AutoCR", content)
        self.assertIn("Cell-4EL", content)

    def test_ivium_eis_fitting_and_example_notes_exist(self) -> None:
        fitting_path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "ivium_eis_equivalent_circuit_fitting_note.md"
        )
        example_path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "ivium_eis_worked_example_note.md"
        )
        fitting = fitting_path.read_text(encoding="utf-8")
        example = example_path.read_text(encoding="utf-8")

        self.assertIn("Warburg", fitting)
        self.assertIn("Gerischer", fitting)
        self.assertIn("Randles", example)
        self.assertIn("SigView", example)

    def test_ivium_compactstat2h_datasheet_summary_exists_and_states_capability_boundary(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "ivium_compactstat2h_standard_datasheet.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("30 mA", content)
        self.assertIn("3 MHz", content)
        self.assertIn("4-electrode", content)
        self.assertIn("1 A", content)
        self.assertIn("not the right default tool for", content.lower())

    def test_iviumstat2h_datasheet_summary_exists_and_states_battery_testing_scope(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "iviumstat2h_datasheet.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("5 A", content)
        self.assertIn("8 MHz", content)
        self.assertIn("10 A", content)
        self.assertIn("CompactStat2.h", content)
        self.assertIn("more battery-capable", content.lower())

    def test_neware_datasheet_summaries_exist_and_capture_channel_power_boundaries(self) -> None:
        high_power = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "neware_bts4000_100v60a_1ch_datasheet.md"
        ).read_text(encoding="utf-8")
        multi_small = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "neware_bts4000_5v6a_8ch_datasheet.md"
        ).read_text(encoding="utf-8")
        mid_current = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "neware_ct4008_5v30a_na_datasheet.md"
        ).read_text(encoding="utf-8")

        self.assertIn("100V", high_power)
        self.assertIn("60A", high_power)
        self.assertIn("6000", high_power)
        self.assertIn("500 ms", high_power)

        self.assertIn("8", multi_small)
        self.assertIn("6A", multi_small)
        self.assertIn("30 W", multi_small)
        self.assertIn("throughput", multi_small.lower())

        self.assertIn("30A", mid_current)
        self.assertIn("150 W", mid_current)
        self.assertIn("5V", mid_current)
        self.assertIn("middle ground", mid_current.lower())

    def test_binder_lit_mk_chamber_summary_exists_and_keeps_battery_safety_scope(self) -> None:
        path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "equipment_manuals"
            / "summaries"
            / "binder_lit_mk_battery_test_chamber_manual.md"
        )
        content = path.read_text(encoding="utf-8")

        self.assertIn("EUCAR", content)
        self.assertIn("18650", content)
        self.assertIn("CO2", content)
        self.assertIn("gas detection", content.lower())
        self.assertIn("-40 °C to +110 °C", content)
        self.assertIn("safety controller", content.lower())
        self.assertIn("not explosion-protected", content.lower())

    def test_equipment_manual_search_can_find_binder_chamber_asset(self) -> None:
        payload = json.loads(
            search_equipment_manual_knowledge.invoke(
                {
                    "query": "thermal chamber gas detection CO2 BINDER",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_count"], 1)
        self.assertEqual(payload["matches"][0]["asset_id"], "binder_lit_mk_battery_test_chamber_manual")
        self.assertIn("answer_reference_markdown", payload["matches"][0])
        self.assertIn("BINDER", payload["matches"][0]["answer_reference_markdown"])
        self.assertNotIn("data/reference/equipment_manuals/", payload["matches"][0]["answer_reference_markdown"])

    def test_equipment_manual_load_tool_returns_summary_markdown(self) -> None:
        payload = json.loads(
            load_equipment_manual_knowledge.invoke(
                {
                    "asset_id": "binder_lit_mk_battery_test_chamber_manual",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertIn("BINDER", payload["manual"]["manufacturer"])
        self.assertIn("EUCAR", payload["summary_markdown"])
        self.assertIn("Equipment Manual: BINDER", payload["ui_markdown"])
        self.assertIn("answer_reference_markdown", payload["manual"])
        self.assertIn("Citation:", payload["ui_markdown"])
        self.assertNotIn("Source file:", payload["ui_markdown"])
        self.assertNotIn("Structured summary path:", payload["ui_markdown"])
        self.assertIn("Supporting pages used above", payload["manual"]["answer_reference_markdown"])

    def test_get_equipment_manual_asset_returns_summary_bundle(self) -> None:
        payload = get_equipment_manual_asset("binder_lit_mk_battery_test_chamber_manual")

        self.assertEqual(payload["status"], "ok")
        self.assertIn("LIT MK 240 / LIT MK 720", payload["manual"]["model"])
        self.assertIn("Defined-load limits", payload["summary_markdown"])
        self.assertIn("answer_reference_markdown", payload["manual"])
        self.assertIn("BINDER", payload["manual"]["answer_reference_markdown"])
        self.assertNotIn("data/reference/equipment_manuals/", payload["manual"]["answer_reference_markdown"])


if __name__ == "__main__":
    unittest.main()
