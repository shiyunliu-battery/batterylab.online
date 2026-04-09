import json
import unittest

from battery_agent.kb import REPO_ROOT
from battery_agent.knowledge import (
    get_method_handbook_source,
    load_method_handbook_evidence_cards,
)
from battery_agent.methods import get_method_payload
from battery_agent.tools import design_battery_protocol, plan_standard_test


class MethodHandbookAssetTests(unittest.TestCase):
    def test_legacy_list_form_evidence_catalog_is_normalized(self) -> None:
        payload = load_method_handbook_evidence_cards()
        card = next(
            item
            for item in payload["cards"]
            if item["card_id"] == "safety_aspects__vibration_scope"
        )

        self.assertEqual(card["evidence_kind"], "handbook_method_scope")
        self.assertEqual(card["methods"], ["safety_aspects__vibration"])
        self.assertIn("protocol_agent", card["system_targets"])
        self.assertIn("linked_reference_markdown", card["citation"])

    def test_pulse_hppc_handbook_source_bundle_exists(self) -> None:
        payload = get_method_handbook_source("battery_understanding_v3_pulse_test")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["source_role"], "primary_protocol_reference")
        self.assertEqual(payload["source"]["method_id"], "pulse_hppc")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 3)
        self.assertIn("Unified Protocol:", payload["summary_markdown"])
        self.assertIn("A. Barai", payload["summary_markdown"])

    def test_method_load_tool_surfaces_handbook_reference_and_cards(self) -> None:
        payload = get_method_payload("pulse_hppc")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["kind"], "structured_method")
        self.assertIsNone(payload["source_pdf"])
        self.assertEqual(
            payload["chapter_file"],
            "data/reference/knowledge/summaries/pulse_hppc.md",
        )
        self.assertEqual(payload["method_source"]["source_id"], "battery_understanding_v3_pulse_test")
        self.assertIn("answer_reference_markdown", payload["method_source"])
        self.assertEqual(
            payload["method_source"]["chapter_file"],
            "data/reference/knowledge/summaries/pulse_hppc.md",
        )
        self.assertGreaterEqual(len(payload["method_evidence_cards"]), 3)
        self.assertEqual(payload["strict_reference_policy"]["mode"], "core_handbook_primary")
        self.assertIn("Strict Method Reference Mode", payload["ui_markdown"])

    def test_standard_method_plan_returns_step_level_citations_and_deviation_policy(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "pulse_hppc",
                    "chemistry": "lfp",
                    "instrument": "biologic_bcs815",
                    "form_factor": "pouch",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["method_reference"]["source_id"], "battery_understanding_v3_pulse_test")
        self.assertEqual(payload["strict_reference_policy"]["mode"], "core_handbook_primary")
        self.assertTrue(payload["deviation_policy"]["review_required"])
        self.assertEqual(payload["planning_mode"], "grounded_protocol_mode")
        self.assertEqual(payload["controlled_planning_state"]["status"], "ready")
        self.assertTrue(payload["response_policy"]["allow_step_level_protocol"])
        self.assertTrue(payload["response_policy"]["references_section_required"])
        self.assertIsNone(payload["source_pdf"])
        self.assertEqual(
            payload["chapter_file"],
            "data/reference/knowledge/summaries/pulse_hppc.md",
        )
        self.assertNotIn("OneDrive", payload["ui_markdown"])
        self.assertEqual(payload["answer_references"][0]["citation_token"], "[1]")
        self.assertIn("battery_understanding_v3_pulse_test", payload["answer_references"][0]["source_id"])
        self.assertEqual(
            payload["answer_citation_map"]["primary_method_reference"],
            "[1]",
        )
        self.assertIn("## References", payload["references_markdown"])
        self.assertIn("[1]", payload["references_markdown"])
        self.assertIn('Battery Lab Assistant, "Objective template - HPPC screening,"', payload["references_markdown"])
        self.assertNotIn("neware", payload["references_markdown"].lower())
        self.assertNotIn("authority/precedence", payload["references_markdown"].lower())
        first_step = payload["protocol_steps"][0]
        self.assertIn("citation", first_step)
        self.assertIn("answer_reference_with_pages_markdown", first_step["citation"])
        self.assertEqual(first_step["step_strictness"], "core_handbook_locked")
        self.assertEqual(first_step["provenance_class"], "handbook_locked")
        self.assertIn("primary_method_reference", first_step["reference_keys"])
        self.assertIn("counts", payload["step_provenance_summary"])

    def test_soc_ocv_source_uses_existing_reference_file(self) -> None:
        payload = get_method_handbook_source("battery_understanding_v3_soc_ocv")
        chapter_file = REPO_ROOT / payload["source"]["chapter_file"]

        self.assertTrue(chapter_file.exists())
        self.assertEqual(
            payload["source"]["chapter_file"],
            "data/reference/knowledge/summaries/soc_ocv.md",
        )

    def test_parallel_pack_ageing_method_payload_loads(self) -> None:
        payload = get_method_payload("parallel_pack_thermal_gradient_ageing")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["kind"], "structured_method")
        self.assertEqual(
            payload["chapter_file"],
            "data/reference/knowledge/summaries/parallel_pack_thermal_gradient_ageing.md",
        )
        self.assertEqual(
            payload["method_source"]["source_id"],
            "battery_understanding_v3_parallel_pack_thermal_gradient_ageing",
        )
        self.assertIn("Parallel-Pack Thermal Gradient Ageing", payload["ui_markdown"])

    def test_objective_planner_carries_handbook_reference_structure(self) -> None:
        payload = json.loads(
            design_battery_protocol.invoke(
                {
                    "objective": "hppc",
                    "chemistry": "lfp",
                    "instrument": "arbin_bt2000",
                    "form_factor": "pouch",
                }
            )
        )

        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["method_reference"]["source_id"], "battery_understanding_v3_pulse_test")
        self.assertEqual(payload["strict_reference_policy"]["mode"], "core_handbook_primary")
        self.assertTrue(payload["deviation_policy"]["review_required"])
        self.assertEqual(payload["planning_mode"], "grounded_protocol_mode")
        self.assertTrue(payload["response_policy"]["allow_step_level_protocol"])
        self.assertTrue(payload["answer_references"])
        self.assertIn("citation", payload["steps"][0])
        self.assertTrue(payload["answer_citation_map"]["objective_template"])
        self.assertIn("Internal planning template", payload["references_markdown"])
        self.assertNotIn("data/kb/", payload["references_markdown"])

    def test_soc_ocv_source_chapter_stays_source_only_while_summary_keeps_review_gate(self) -> None:
        payload = get_method_handbook_source("battery_understanding_v3_soc_ocv")
        chapter_path = (
            REPO_ROOT
            / "data"
            / "reference"
            / "knowledge"
            / "summaries"
            / "soc_ocv.md"
        )
        chapter_text = chapter_path.read_text(encoding="utf-8")

        self.assertNotIn("PLANNER COMPLETION", chapter_text)
        self.assertNotIn("steps 5-7", chapter_text)
        self.assertIn("ECM battery modelling", payload["summary_markdown"])

    def test_calendar_ageing_handbook_extension_loads_with_fallback_summary(self) -> None:
        payload = get_method_handbook_source("battery_understanding_v3_calendar_ageing_test")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["method_id"], "calendar_ageing_test")
        self.assertEqual(payload["source"]["source_role"], "primary_protocol_reference")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 3)
        self.assertIn("calendar ageing", payload["summary_markdown"].lower())
        self.assertIn("roman_ramirez_2022_doe_review", payload["summary_markdown"])

    def test_calendar_ageing_plan_surfaces_campaign_framework_and_rpt_policy(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "calendar_ageing_test",
                    "chemistry": "lfp",
                    "instrument": "arbin_bt2000",
                    "form_factor": "pouch",
                    "method_inputs_json": json.dumps(
                        {
                            "target_soc": 50,
                            "stop_criterion": "80% SOH",
                            "checkpoint_interval": "6 weeks",
                        }
                    ),
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["campaign_framework"]["campaign_type"], "calendar_ageing")
        policy = payload["reference_check_policy"]
        self.assertTrue(policy["baseline_required"])
        self.assertEqual(policy["rpt_cadence_mode"]["default_mode"], "fixed_elapsed_time")
        self.assertEqual(policy["reference_temperature_c"]["nominal"], 25.0)
        self.assertEqual(policy["core_rpt_set"]["bundle_id"], "calendar_core_rpt_25c")
        self.assertEqual(
            policy["rpt_blocks"][0]["source_method_ids"],
            ["standard_cycle", "capacity_test", "pulse_hppc"],
        )
        self.assertEqual(
            policy["checkpoint_templates"][1]["step_bundle"][2]["extension_id"],
            "impedance_extension",
        )
        self.assertIn("Core RPT set", payload["ui_markdown"])
        self.assertIn("Checkpoint templates", payload["ui_markdown"])
        self.assertIn("Reference Check Policy", payload["ui_markdown"])

    def test_cycle_life_objective_plan_surfaces_reference_check_policy(self) -> None:
        payload = json.loads(
            design_battery_protocol.invoke(
                {
                    "objective": "cycle_life",
                    "chemistry": "lfp",
                    "instrument": "arbin_bt2000",
                    "form_factor": "pouch",
                }
            )
        )

        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["campaign_framework"]["campaign_type"], "ageing_cycle_life")
        self.assertEqual(
            payload["reference_check_policy"]["rpt_blocks"][1]["source_method_ids"],
            ["electrochemical_impedance_test"],
        )

    def test_drive_cycle_plan_surfaces_checkpoint_templates_and_cadence(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "ageing_drive_cycle",
                    "chemistry": "lfp",
                    "instrument": "arbin_bt2000",
                    "form_factor": "pouch",
                    "method_inputs_json": json.dumps(
                        {
                            "profile_family": "BEV",
                            "soc_window": "10-90% SOC",
                            "charge_regime": "CC-CV recharge",
                            "stop_criterion": "80% SOH",
                            "block_basis": "cycle_block",
                        }
                    ),
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        policy = payload["reference_check_policy"]
        self.assertEqual(policy["rpt_cadence_mode"]["default_mode"], "fixed_cycle_block")
        self.assertEqual(policy["reference_temperature_c"]["nominal"], 30.0)
        self.assertEqual(
            policy["core_rpt_set"]["source_method_ids"],
            ["standard_cycle", "capacity_test", "pulse_hppc"],
        )
        self.assertEqual(
            policy["checkpoint_templates"][1]["step_bundle"][1]["bundle_id"],
            "drive_cycle_core_rpt",
        )
        self.assertEqual(
            policy["checkpoint_extension_tests"][0]["method_ids"],
            ["dynamic_stress_test", "drive_cycle_test"],
        )
        self.assertIn("RPT cadence mode", payload["ui_markdown"])
        self.assertIn("Checkpoint templates", payload["ui_markdown"])

    def test_ageing_drive_cycle_payload_surfaces_input_contract(self) -> None:
        payload = get_method_payload("ageing_drive_cycle")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["method_status"], "structured_method")
        self.assertEqual(payload["execution_readiness"], "planner_ready_review_required")
        self.assertIn("block_basis", payload["input_contract"]["required_inputs"])
        self.assertEqual(
            payload["input_contract"]["conditional_required_inputs"][0]["required"],
            ["cycle_count"],
        )
        self.assertEqual(
            payload["reference_check_policy"]["rpt_blocks"][1]["source_method_ids"],
            ["dynamic_stress_test", "drive_cycle_test"],
        )

    def test_calendar_ageing_payload_surfaces_target_soc_and_derived_observables(self) -> None:
        payload = get_method_payload("calendar_ageing_test")

        self.assertEqual(payload["status"], "ok")
        self.assertIn("target_soc", payload["input_contract"]["required_inputs"])
        self.assertEqual(
            payload["reference_check_policy"]["reference_temperature_c"]["pre_checkpoint_hold"]["mode"],
            "until_thermal_equilibrium",
        )
        self.assertIn(
            "charge-retention context",
            payload["reference_check_policy"]["core_rpt_set"]["derived_observables"],
        )

    def test_calendar_ageing_plan_uses_storage_block_count_requested_condition(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "calendar_ageing_test",
                    "chemistry": "lfp",
                    "instrument": "arbin_bt2000",
                    "form_factor": "pouch",
                    "method_inputs_json": json.dumps(
                        {
                            "target_soc": 50,
                            "stop_criterion": "80% SOH",
                            "checkpoint_interval": "6 weeks",
                        }
                    ),
                }
            )
        )

        self.assertEqual(payload["requested_conditions"]["run_length_field"], "storage_block_count")
        self.assertEqual(payload["requested_conditions"]["run_length_basis"], "fixed_elapsed_time")
        self.assertEqual(payload["requested_conditions"]["storage_block_count"], 1)
        self.assertNotIn("cycle_count", payload["requested_conditions"])

    def test_constant_voltage_ageing_stays_outline_only(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "constant_voltage_ageing",
                    "chemistry": "lfp",
                    "instrument": "biologic_bcs815",
                    "form_factor": "pouch",
                    "method_inputs_json": json.dumps(
                        {
                            "target_voltage": 4.1,
                            "hold_duration": "120 h",
                            "stop_criterion": "10% resistance growth",
                            "checkpoint_interval": "2 weeks",
                        }
                    ),
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["strict_reference_policy"]["mode"], "outline_only_review_required")
        self.assertFalse(payload["protocol_steps"][0]["source_backed"])
        self.assertTrue(payload["deviation_policy"]["deviation_review_items"])

    def test_constant_voltage_payload_stays_placeholder_but_schema_complete(self) -> None:
        payload = get_method_payload("constant_voltage_ageing")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["method_status"], "draft_placeholder")
        self.assertEqual(payload["execution_readiness"], "not_releaseable")
        self.assertIn("target_voltage", payload["input_contract"]["required_inputs"])
        self.assertIn("hold_duration", payload["input_contract"]["required_inputs"])
        self.assertTrue(payload["human_review_required"])
        self.assertEqual(
            payload["reference_check_policy"]["core_rpt_set"]["bundle_id"],
            "constant_voltage_placeholder_core_rpt",
        )
        self.assertEqual(
            payload["reference_check_policy"]["checkpoint_templates"][1]["step_bundle"][2]["extension_id"],
            "impedance_extension",
        )

    def test_constant_voltage_plan_uses_hold_block_count_requested_condition(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "constant_voltage_ageing",
                    "chemistry": "lfp",
                    "instrument": "biologic_bcs815",
                    "form_factor": "pouch",
                    "method_inputs_json": json.dumps(
                        {
                            "target_voltage": 4.1,
                            "hold_duration": "120 h",
                            "stop_criterion": "10% resistance growth",
                            "checkpoint_interval": "2 weeks",
                        }
                    ),
                }
            )
        )

        self.assertEqual(payload["requested_conditions"]["run_length_field"], "hold_block_count")
        self.assertEqual(payload["requested_conditions"]["run_length_basis"], "fixed_elapsed_time")
        self.assertEqual(payload["requested_conditions"]["hold_block_count"], 1)
        self.assertNotIn("cycle_count", payload["requested_conditions"])

    def test_calendar_ageing_plan_requires_method_specific_inputs(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "calendar_ageing_test",
                    "chemistry": "lfp",
                    "instrument": "arbin_bt2000",
                    "form_factor": "pouch",
                }
            )
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "planning_validation_error")
        self.assertIn("target_soc", payload["message"])
        self.assertIn("checkpoint_interval", payload["message"])


if __name__ == "__main__":
    unittest.main()
