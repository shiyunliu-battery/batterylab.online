import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from battery_agent.tools import (
    _design_battery_protocol_impl,
    _plan_standard_test_impl,
    design_battery_protocol,
    load_battery_knowledge,
    plan_standard_test,
)
from battery_agent.kb import get_safety_checklist


class SelectedCellPlanningTests(unittest.TestCase):
    @staticmethod
    def _uploaded_datasheet_candidate(
        *,
        chemistry_hint: str = "unknown",
        charge_voltage_v: float = 4.2,
        discharge_cutoff_v: float = 2.75,
    ) -> dict:
        return {
            "display_name": "Samsung SDI ICR18650-26F",
            "manufacturer": "Samsung SDI",
            "model": "ICR18650-26F",
            "schema_name": "ICR18650-26F",
            "project_chemistry_hint": chemistry_hint,
            "form_factor": "cylindrical",
            "case_types": ["18650"],
            "electrical": {
                "nominal_capacity_ah": 2.6,
                "nominal_voltage_v": 3.7,
                "charge_voltage_v": charge_voltage_v,
                "discharge_cutoff_v": discharge_cutoff_v,
            },
            "currents": {
                "max_continuous_charge_current_a": 2.6,
                "max_continuous_discharge_current_a": 5.2,
            },
            "physical": {
                "mass_g": 47.0,
                "diameter_mm": 18.4,
                "height_mm": 65.0,
            },
            "lifecycle": {},
            "source_document": {
                "original_filename": "ICR_18650_datasheet.pdf",
                "thread_file_path": "/uploads/icr_18650_datasheet.pdf.txt",
            },
        }

    def test_standard_method_uses_approved_selected_cell_context(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "pulse_hppc",
                    "selected_cell_id": "A123_20AH",
                    "instrument": "biologic_bcs815",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["selected_cell_id"], "A123_20AH")
        self.assertEqual(payload["chemistry_id"], "lfp")
        self.assertEqual(payload["chemistry_label"], "LFP")
        self.assertEqual(payload["requested_conditions"]["form_factor"], "prismatic")
        self.assertEqual(payload["applied_constraints"]["charge_voltage_v"], 3.65)
        self.assertEqual(payload["applied_constraints"]["discharge_cutoff_v"], 2.5)
        self.assertEqual(
            payload["constraint_sources"]["charge_voltage_v"],
            "registry_chemistry_profile",
        )
        self.assertEqual(payload["selected_cell_reference"]["approval_status"], "approved")
        self.assertTrue(payload["selected_cell_reference"]["eligible_for_planning"])
        self.assertIn("approved_for_planning", payload["selected_cell_reference"]["eligibility_tags"])
        self.assertEqual(payload["trust_level"], "draft_protocol")
        self.assertTrue(payload["requires_human_review"])
        self.assertNotIn("parameter_pack", payload)

    def test_selected_cell_flow_uses_approved_default_instrument_with_explicit_provenance(self) -> None:
        payload = json.loads(
            plan_standard_test.invoke(
                {
                    "method_id": "pulse_hppc",
                    "selected_cell_id": "A123_20AH",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["release_status"], "review_required_protocol")
        self.assertEqual(payload["instrument"], "Neware CT-4008-5V30A-NA")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "pretest_guidance_default",
        )
        self.assertTrue(
            any("approved default guidance" in warning for warning in payload["warnings"])
        )
        self.assertEqual(payload["planning_mode"], "grounded_protocol_mode")
        self.assertTrue(payload["response_policy"]["allow_step_level_protocol"])

    def test_objective_planner_uses_selected_cell_metadata(self) -> None:
        payload = json.loads(
            design_battery_protocol.invoke(
                {
                    "objective": "hppc",
                    "selected_cell_id": "A123_20AH",
                    "instrument": "arbin_bt2000",
                }
            )
        )

        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["selected_cell_id"], "A123_20AH")
        self.assertEqual(payload["chemistry"], "LFP")
        self.assertEqual(payload["form_factor"], "prismatic")
        self.assertEqual(payload["trust_level"], "draft_protocol")
        self.assertTrue(payload["requires_human_review"])
        self.assertEqual(payload["selected_cell_reference"]["manufacturer"], "A123")
        self.assertEqual(payload["selected_cell_reference"]["approval_status"], "approved")
        self.assertEqual(payload["applied_constraints"]["charge_voltage_v"], 3.65)
        self.assertEqual(payload["applied_constraints"]["discharge_cutoff_v"], 2.5)
        self.assertIn("A123", payload["protocol_name"])

    def test_standard_method_uses_lab_default_instrument_from_runtime_state(self) -> None:
        runtime = SimpleNamespace(
            state={
                "ui": {
                    "labDefaults": {
                        "defaultInstrumentId": "biologic_bcs815",
                    }
                }
            }
        )

        payload = json.loads(
            _plan_standard_test_impl(
                method_id="pulse_hppc",
                chemistry="lfp",
                form_factor="pouch",
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "settings_lab_defaults",
        )
        self.assertTrue(
            any("biologic_bcs815" in warning for warning in payload["warnings"])
        )

    def test_standard_method_requires_form_factor_when_no_cell_context_exists(self) -> None:
        payload = json.loads(
            _plan_standard_test_impl(
                method_id="pulse_hppc",
                chemistry="lfp",
                instrument="neware_bts4000_5v6a_8ch",
            )
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "planning_validation_error")
        self.assertIn("form_factor", payload["message"])

    def test_objective_planner_uses_lab_default_instrument_and_chamber(self) -> None:
        runtime = SimpleNamespace(
            state={
                "ui": {
                    "labDefaults": {
                        "defaultInstrumentId": "arbin_bt2000",
                        "defaultInstrumentLabel": "Arbin BT2000",
                        "defaultThermalChamberId": "binder_lit_mk",
                        "defaultThermalChamberLabel": "BINDER LIT MK 240 / 720",
                        "defaultEisInstrumentId": "iviumstat2h_datasheet",
                        "defaultEisInstrumentLabel": "Ivium Technologies IviumStat2.h",
                        "defaultEisSetupNotes": "5 A booster installed on rack A",
                    }
                }
            }
        )

        payload = json.loads(
            _design_battery_protocol_impl(
                objective="hppc",
                selected_cell_id="A123_20AH",
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "draft")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "settings_lab_defaults",
        )
        self.assertNotIn("thermal_chamber", payload["lab_default_context"]["applied_fields"])
        self.assertEqual(
            payload["lab_default_context"]["available_fields"]["thermal_chamber"],
            "settings_lab_defaults_available",
        )
        self.assertEqual(
            payload["lab_default_context"]["lab_defaults"]["default_eis_instrument_label"],
            "Ivium Technologies IviumStat2.h",
        )
        self.assertEqual(
            payload["lab_default_context"]["lab_defaults"]["default_eis_instrument_id"],
            "iviumstat2h_datasheet",
        )
        self.assertEqual(
            payload["lab_default_context"]["lab_defaults"]["default_eis_setup_notes"],
            "5 A booster installed on rack A",
        )
        self.assertEqual(payload["instrument"], "Arbin BT2000")
        self.assertIsNone(payload["thermal_chamber"])

    def test_standard_method_tool_wrapper_uses_top_level_lab_default_instrument(self) -> None:
        runtime = SimpleNamespace(
            state={
                "labDefaults": {
                    "defaultInstrumentId": "neware_ct4008_5v30a_na",
                }
            }
        )

        payload = json.loads(
            plan_standard_test.func(
                method_id="pulse_hppc",
                chemistry="lfp",
                form_factor="pouch",
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertIn("Neware CT-4008-5V30A-NA", payload["protocol_name"])
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "settings_lab_defaults",
        )

    def test_load_battery_knowledge_uses_runtime_default_instrument_consistently(self) -> None:
        runtime = SimpleNamespace(
            state={
                "labDefaults": {
                    "defaultInstrumentId": "neware_bts4000_5v6a_8ch",
                    "defaultInstrumentLabel": "Neware BTS4000-5V6A-8CH",
                }
            }
        )

        payload = json.loads(
            load_battery_knowledge.func(
                chemistry="lfp",
                objective="hppc",
                runtime=runtime,
            )
        )

        self.assertEqual(
            payload["pretest_guidance"]["approved_equipment_defaults"]["default_cycler_id"],
            "neware_bts4000_5v6a_8ch",
        )
        self.assertEqual(
            payload["equipment_rule"]["label"],
            "Neware BTS4000-5V6A-8CH",
        )
        self.assertEqual(
            payload["answer_citation_map"]["claim_bindings"]["equipment_defaults"],
            ["[4]", "[1]"],
        )

    def test_load_battery_knowledge_keeps_default_chamber_as_available_context(self) -> None:
        runtime = SimpleNamespace(
            state={
                "labDefaults": {
                    "defaultInstrumentId": "neware_bts4000_5v6a_8ch",
                    "defaultInstrumentLabel": "Neware BTS4000-5V6A-8CH",
                    "defaultThermalChamberId": "binder_lit_mk",
                    "defaultThermalChamberLabel": "BINDER LIT MK 240 / 720",
                }
            }
        )

        payload = json.loads(
            load_battery_knowledge.func(
                chemistry="lfp",
                objective="hppc",
                runtime=runtime,
            )
        )

        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "settings_lab_defaults",
        )
        self.assertNotIn("thermal_chamber", payload["lab_default_context"]["applied_fields"])
        self.assertEqual(
            payload["lab_default_context"]["available_fields"]["thermal_chamber"],
            "settings_lab_defaults_available",
        )
        self.assertTrue(
            any("available context" in warning for warning in payload.get("warnings", []))
        )

    def test_standard_method_uses_hidden_lab_defaults_thread_file_when_state_is_empty(self) -> None:
        runtime = SimpleNamespace(state={"messages": []})

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/context/lab-defaults.json",
                json.dumps(
                    {
                        "labDefaults": {
                            "defaultInstrumentId": "neware_bts4000_5v6a_8ch",
                            "defaultInstrumentLabel": "Neware BTS4000-5V6A-8CH",
                        }
                    }
                ),
            ),
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="pulse_hppc",
                    chemistry="lfp",
                    form_factor="pouch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertIn("Neware BTS4000-5V6A-8CH", payload["protocol_name"])
        self.assertEqual(payload["lab_default_context"]["source"], "thread_file_lab_defaults")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "settings_lab_defaults",
        )

    def test_standard_method_falls_back_to_pretest_guidance_default_instrument(self) -> None:
        payload = json.loads(
            _plan_standard_test_impl(
                method_id="pulse_hppc",
                chemistry="lfp",
                form_factor="pouch",
                target_temperature_c=25.0,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["instrument"], "Neware CT-4008-5V30A-NA")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "pretest_guidance_default",
        )
        self.assertTrue(
            any(
                "approved default guidance" in warning
                for warning in payload["warnings"]
            )
        )
        self.assertIn("# Experiment Plan", payload["ui_markdown"])
        self.assertIn("## Plan Status & Constraints", payload["ui_markdown"])
        self.assertIn("### Controlled Test Object And Locked Limits", payload["ui_markdown"])
        self.assertIn("### Active Safety And Release Constraints", payload["ui_markdown"])
        self.assertIn("## Protocol", payload["ui_markdown"])
        self.assertIn("### Equipment & Setup", payload["ui_markdown"])
        self.assertIn("### Recommended Execution Sequence", payload["ui_markdown"])
        self.assertIn("## Outputs & Basis", payload["ui_markdown"])
        self.assertIn("### Required Outputs For Analysis", payload["ui_markdown"])
        self.assertIn("### Calculation & QC Notes", payload["ui_markdown"])
        self.assertIn("R_t = \\|V_t - V_pre\\| / \\|I_t - I_pre\\|", payload["ui_markdown"])
        self.assertIn("### References", payload["ui_markdown"])
        self.assertIn('[1] G. Mulder', payload["ui_markdown"])
        self.assertIn('Battery Lab Assistant, "Objective template - HPPC screening,"', payload["ui_markdown"])
        self.assertNotIn("### Analysis Plan", payload["ui_markdown"])
        self.assertNotIn("Run This Default Plan", payload["ui_markdown"])

    def test_load_battery_knowledge_falls_back_to_pretest_guidance_defaults(self) -> None:
        payload = json.loads(
            load_battery_knowledge.func(
                objective="hppc",
            )
        )

        self.assertEqual(
            payload["pretest_guidance"]["approved_equipment_defaults"]["default_cycler_id"],
            "neware_ct4008_5v30a_na",
        )
        self.assertEqual(
            payload["equipment_rule"]["label"],
            "Neware CT-4008-5V30A-NA",
        )
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "pretest_guidance_default",
        )
        self.assertTrue(
            any(
                reference["reference_type"] == "built_in_guidance"
                and reference["display_token"].startswith("G")
                for reference in payload["answer_references"]
            )
        )

    def test_standard_method_lookup_error_points_back_to_controlled_knowledge(self) -> None:
        payload = json.loads(
            _plan_standard_test_impl(
                method_id="pulse_hppc",
                instrument="neware_bts4000_5v6a_8ch",
            )
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "planning_lookup_error")
        self.assertEqual(payload["planning_mode"], "advisory_gap_mode")
        self.assertFalse(payload["response_policy"]["allow_step_level_protocol"])
        self.assertTrue(
            any("load_battery_knowledge" in suggestion for suggestion in payload["suggestions"])
        )
        self.assertTrue(
            any("generic pulse/rest/SOC defaults" in suggestion for suggestion in payload["suggestions"])
        )

    def test_standard_method_uses_uploaded_datasheet_candidate_when_registry_subject_is_missing(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this DCR planning request."
                        )
                    }
                ]
            }
        )

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={
                "candidate": self._uploaded_datasheet_candidate(),
            },
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="pulse_hppc",
                    instrument="neware_bts4000_5v6a_8ch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["selected_cell_reference"]["source_kind"],
            "uploaded_cell_datasheet_candidate",
        )
        self.assertEqual(payload["selected_cell_reference"]["approval_status"], "draft_uploaded_datasheet")
        self.assertEqual(payload["applied_constraints"]["charge_voltage_v"], 4.2)
        self.assertEqual(
            payload["constraint_sources"]["charge_voltage_v"],
            "uploaded_cell_datasheet_candidate",
        )
        self.assertEqual(payload["planning_mode"], "grounded_protocol_mode")

    def test_uploaded_datasheet_voltage_window_overrides_registry_family_defaults(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this DCR planning request."
                        )
                    }
                ]
            }
        )

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={
                "candidate": self._uploaded_datasheet_candidate(
                    chemistry_hint="lfp",
                    charge_voltage_v=4.2,
                    discharge_cutoff_v=2.75,
                ),
            },
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="pulse_hppc",
                    chemistry="lfp",
                    instrument="neware_bts4000_5v6a_8ch",
                    form_factor="cylindrical",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["chemistry_id"], "lfp")
        self.assertEqual(payload["applied_constraints"]["charge_voltage_v"], 4.2)
        self.assertEqual(payload["applied_constraints"]["discharge_cutoff_v"], 2.75)
        self.assertEqual(
            payload["constraint_sources"]["charge_voltage_v"],
            "uploaded_cell_datasheet_candidate",
        )

    def test_uploaded_selected_cell_id_falls_back_to_runtime_datasheet_candidate(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this DCR planning request."
                        )
                    }
                ]
            }
        )

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={
                "candidate": self._uploaded_datasheet_candidate(),
            },
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="capacity_test",
                    chemistry="lfp",
                    selected_cell_id="uploaded_ICR18650_26F",
                    instrument="neware_bts4000_5v6a_8ch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["selected_cell_reference"]["source_kind"],
            "uploaded_cell_datasheet_candidate",
        )

    def test_objective_missing_subject_points_back_to_controlled_knowledge(self) -> None:
        payload = json.loads(
            _design_battery_protocol_impl(
                objective="hppc",
                instrument="neware_bts4000_5v6a_8ch",
            )
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "missing_planning_subject")
        self.assertEqual(payload["planning_mode"], "advisory_gap_mode")
        self.assertFalse(payload["response_policy"]["allow_step_level_protocol"])
        self.assertTrue(
            any("load_battery_knowledge" in suggestion for suggestion in payload["suggestions"])
        )

    def test_load_battery_knowledge_returns_preflight_marker_and_references(self) -> None:
        payload = json.loads(
            load_battery_knowledge.invoke(
                {
                    "chemistry": "lfp",
                    "instrument": "neware_bts4000_5v6a_8ch",
                    "objective": "hppc",
                }
            )
        )

        self.assertEqual(payload["planning_mode"], "knowledge_preflight_mode")
        self.assertEqual(payload["controlled_planning_state"]["status"], "preflight_loaded")
        self.assertFalse(payload["response_policy"]["allow_step_level_protocol"])
        self.assertTrue(payload["answer_references"])
        self.assertEqual(payload["answer_references"][0]["citation_token"], "[1]")
        self.assertIn("## References", payload["references_markdown"])
        self.assertIn("[1]", payload["references_markdown"])
        self.assertIn("Internal lab pretest guidance", payload["references_markdown"])
        self.assertIn('Battery Lab Assistant, "Lab pretest guidance,"', payload["references_markdown"])
        self.assertNotIn("data/kb/", payload["references_markdown"])

    def test_load_battery_knowledge_sanitizes_workspace_root_and_hides_internal_asset_reference_ids(self) -> None:
        payload = json.loads(
            load_battery_knowledge.invoke(
                {
                    "chemistry": "lfp",
                    "instrument": "neware_bts4000_5v6a_8ch",
                    "thermal_chamber": "binder_lit_mk",
                    "objective": "hppc",
                }
            )
        )

        self.assertEqual(payload["workspace_root"], "repo_root")
        self.assertNotIn("OneDrive", payload["workspace_root"])
        self.assertIn("Neware BTS4000-5V6A-8CH", payload["references_markdown"])
        self.assertIn('Battery Lab Assistant, "BINDER LIT MK 240 / 720,"', payload["references_markdown"])
        self.assertIn("Planning governance guidance", payload["references_markdown"])
        self.assertIn("Internal planning template", payload["references_markdown"])
        self.assertIn("Internal equipment constraints", payload["references_markdown"])
        self.assertNotIn("data/kb/", payload["references_markdown"])
        self.assertNotIn("### Built-In Guidance", payload["references_markdown"])
        self.assertNotIn("neware_bts4000_5v6a_8ch_datasheet", payload["references_markdown"])
        self.assertNotIn("binder_lit_mk_battery_test_chamber_manual", payload["references_markdown"])
        self.assertNotIn("authority/precedence", payload["references_markdown"])
        self.assertNotIn("(unknown)", payload["references_markdown"])

    def test_load_battery_knowledge_includes_pretest_guidance(self) -> None:
        payload = json.loads(
            load_battery_knowledge.invoke(
                {
                    "instrument": "neware_ct4008_5v30a_na",
                    "objective": "cycle_life",
                }
            )
        )

        self.assertIn("pretest_guidance", payload)
        self.assertEqual(
            payload["pretest_guidance"]["global_defaults"]["surface_temperature_abort_c"],
            60.0,
        )
        self.assertIn("rpt_playbook", payload["pretest_guidance"])

    def test_load_battery_knowledge_uses_registered_rpt_objective_template(self) -> None:
        payload = json.loads(
            load_battery_knowledge.invoke(
                {
                    "instrument": "neware_ct4008_5v30a_na",
                    "objective": "rpt",
                }
            )
        )

        self.assertEqual(payload["objective_template"]["id"], "objective_template_rpt")
        self.assertEqual(payload["objective_template"]["minimum_modules"][0], "reference capacity test")
        self.assertTrue(payload["answer_citation_map"]["objective_template"])

    def test_load_battery_knowledge_includes_decision_graph_semantics(self) -> None:
        payload = json.loads(
            load_battery_knowledge.invoke(
                {
                    "instrument": "neware_ct4008_5v30a_na",
                    "objective": "cycle_life",
                }
            )
        )

        self.assertIn("decision_graph_semantics", payload)
        self.assertIn("relation_classes", payload["decision_graph_semantics"])
        self.assertIn("authority_and_precedence", payload["decision_graph_semantics"])
        self.assertIn("requirement_strength_levels", payload["decision_graph_semantics"])
        self.assertIn("conflict_representation", payload["decision_graph_semantics"])
        self.assertIn("decision_relation_model", payload["answer_citation_map"])

    def test_general_safety_checklist_carries_lab_surface_temperature_abort_sop(self) -> None:
        checklist = get_safety_checklist("hppc")

        self.assertTrue(
            any("surface temperature reaches 60 C" in item for item in checklist)
        )

    def test_safety_checklist_carries_cv_termination_and_chamber_requirement_defaults(self) -> None:
        checklist = get_safety_checklist("cycle_life")

        self.assertTrue(any("Default CV termination rule" in item for item in checklist))
        self.assertTrue(
            any("outside 25.0 +/- 2.0 C must use an environmental chamber" in item for item in checklist)
        )

    def test_cycle_life_plan_uses_lab_default_reference_temperature(self) -> None:
        payload = json.loads(
            _plan_standard_test_impl(
                method_id="cycle_life",
                chemistry="lfp",
                instrument="neware_bts4000_5v6a_8ch",
                form_factor="pouch",
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["reference_check_policy"]["reference_temperature_c"]["nominal"],
            25.0,
        )
        self.assertEqual(
            payload["reference_check_policy"]["reference_temperature_c"]["value_role"],
            "lab_default_sop",
        )
        self.assertEqual(payload["applied_constraints"]["lab_reference_temperature_c"], 25.0)
        self.assertEqual(payload["applied_constraints"]["surface_temperature_abort_c"], 60.0)
        self.assertEqual(payload["applied_constraints"]["cv_termination_current_a"], 0.06)
        self.assertTrue(
            any("lab default RPT reference temperature of 25.0 C" in warning for warning in payload["warnings"])
        )
        self.assertIn("decision_graph_semantics", payload)
        self.assertIn("authority_and_precedence", payload["decision_graph_semantics"])
        self.assertTrue(payload["response_policy"]["must_apply_authority_and_precedence"])
        self.assertTrue(payload["response_policy"]["must_preserve_requirement_strength"])

    def test_pulse_hppc_uses_lab_cv_rule_and_single_temperature_wording(self) -> None:
        payload = json.loads(
            _plan_standard_test_impl(
                method_id="pulse_hppc",
                chemistry="lfp",
                instrument="neware_bts4000_5v6a_8ch",
                form_factor="pouch",
                target_temperature_c=25.0,
            )
        )

        self.assertEqual(payload["status"], "ok")
        step_lookup = {
            step["step_id"]: step["details"]
            for step in payload["protocol_steps"]
        }
        self.assertIn("0.06 A", step_lookup["reference_full_charge"])
        self.assertIn("C/20", step_lookup["reference_full_charge"])
        self.assertIn("120 min", step_lookup["reference_full_charge"])
        self.assertNotIn("temperature sweep", step_lookup["return_to_full_soc"])
        self.assertNotIn("Set the chamber", step_lookup["climate_chamber_acclimation"])
        self.assertIn(
            "Add additional temperatures only when the reviewed plan explicitly defines a multi-temperature matrix.",
            step_lookup["repeat_across_soc_rate_temperature"],
        )

    def test_plan_uses_approved_default_chamber_outside_lab_reference_window(self) -> None:
        payload = json.loads(
            _plan_standard_test_impl(
                method_id="capacity_test",
                chemistry="lfp",
                instrument="neware_bts4000_5v6a_8ch",
                form_factor="pouch",
                target_temperature_c=10.0,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["release_status"], "review_required_protocol")
        self.assertEqual(payload["thermal_chamber"], "BINDER LIT MK 240 / 720")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["thermal_chamber"],
            "pretest_guidance_default",
        )
        self.assertTrue(
            any("Thermal chamber resolved from approved default guidance" in warning for warning in payload["warnings"])
        )
        self.assertIsNone(payload["parameter_request"])

    def test_ambient_standard_method_keeps_default_chamber_as_available_context(self) -> None:
        runtime = SimpleNamespace(
            state={
                "labDefaults": {
                    "defaultInstrumentId": "neware_bts4000_5v6a_8ch",
                    "defaultThermalChamberId": "binder_lit_mk",
                    "defaultThermalChamberLabel": "BINDER LIT MK 240 / 720",
                }
            }
        )

        payload = json.loads(
            plan_standard_test.func(
                method_id="soc_ocv",
                chemistry="lfp",
                form_factor="pouch",
                target_temperature_c=25.0,
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertIsNone(payload["thermal_chamber"])
        self.assertNotIn("thermal_chamber", payload["lab_default_context"]["applied_fields"])
        self.assertEqual(
            payload["lab_default_context"]["available_fields"]["thermal_chamber"],
            "settings_lab_defaults_available",
        )
        self.assertTrue(
            any(
                "available but not applied as a hard constraint" in warning
                for warning in payload["warnings"]
            )
        )
        self.assertFalse(
            any(
                "If the selected thermal chamber is BINDER LIT MK" in warning
                for warning in payload["warnings"]
            )
        )
        self.assertIn("## Plan Status & Constraints", payload["ui_markdown"])
        self.assertIn("### Controlled Test Object And Locked Limits", payload["ui_markdown"])
        self.assertIn("### Review Items Before Release", payload["ui_markdown"])

    def test_objective_tool_wrapper_uses_top_level_lab_default_instrument(self) -> None:
        runtime = SimpleNamespace(
            state={
                "labDefaults": {
                    "defaultInstrumentId": "neware_ct4008_5v30a_na",
                }
            }
        )

        payload = json.loads(
            design_battery_protocol.func(
                objective="cycle_life",
                selected_cell_id="A123_20AH",
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["instrument"], "Neware CT-4008-5V30A-NA")
        self.assertEqual(
            payload["lab_default_context"]["applied_fields"]["instrument"],
            "settings_lab_defaults",
        )

    def test_uploaded_pulse_plan_blocks_until_discharge_allowance_is_confirmed(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this DCR planning request."
                        )
                    }
                ]
            }
        )
        candidate = self._uploaded_datasheet_candidate()
        candidate["currents"].pop("max_continuous_discharge_current_a", None)

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={"candidate": candidate},
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="pulse_hppc",
                    instrument="neware_bts4000_5v6a_8ch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["release_status"], "blocker_aware_draft")
        self.assertTrue(payload["execution_blockers"])
        self.assertIsNotNone(payload["parameter_request"])
        question_keys = [
            question["key"] for question in payload["parameter_request"]["questions"]
        ]
        self.assertIn("max_continuous_discharge_current_a", question_keys)
        self.assertIn("dcir_definition", question_keys)
        self.assertIn("# Experiment Plan", payload["ui_markdown"])
        self.assertIn("## Plan Status & Constraints", payload["ui_markdown"])
        self.assertIn("### Review Items Before Release", payload["ui_markdown"])
        self.assertIn("## Outputs & Basis", payload["ui_markdown"])
        self.assertNotIn("Run This Default Plan", payload["ui_markdown"])

    def test_uploaded_pulse_plan_blocks_until_dcir_definition_is_confirmed(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this DCR planning request."
                        )
                    }
                ]
            }
        )

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={"candidate": self._uploaded_datasheet_candidate()},
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="pulse_hppc",
                    instrument="neware_bts4000_5v6a_8ch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["release_status"], "blocker_aware_draft")
        self.assertIsNotNone(payload["parameter_request"])
        question_keys = [
            question["key"] for question in payload["parameter_request"]["questions"]
        ]
        self.assertIn("dcir_definition", question_keys)

    def test_extracted_uploaded_datasheet_ui_markdown_uses_cell_background_table(self) -> None:
        runtime = SimpleNamespace(state={"messages": []})

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={"candidate": self._uploaded_datasheet_candidate()},
        ):
            from battery_agent.tools import _extract_uploaded_cell_datasheet_impl

            payload = json.loads(
                _extract_uploaded_cell_datasheet_impl(
                    file_path="/uploads/icr_18650_datasheet.pdf.txt",
                    runtime=runtime,
                )
            )

        self.assertIn("## Cell Datasheet:", payload["ui_markdown"])
        self.assertIn("| Field | Value | Notes |", payload["ui_markdown"])
        self.assertIn("Nominal capacity", payload["ui_markdown"])
        self.assertIn("Charge voltage limit", payload["ui_markdown"])

    def test_uploaded_cycle_life_plan_blocks_until_ageing_matrix_is_confirmed(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this ageing planning request."
                        )
                    }
                ]
            }
        )

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={"candidate": self._uploaded_datasheet_candidate()},
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="cycle_life",
                    instrument="neware_bts4000_5v6a_8ch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["release_status"], "blocker_aware_draft")
        self.assertIsNotNone(payload["parameter_request"])
        question_keys = [
            question["key"] for question in payload["parameter_request"]["questions"]
        ]
        self.assertIn("ageing_condition_matrix", question_keys)
        self.assertIn("checkpoint_interval", question_keys)
        self.assertIn("stop_criterion", question_keys)
        self.assertIn("### Controlled Test Object And Locked Limits", payload["ui_markdown"])

    def test_uploaded_pulse_plan_resumes_after_parameter_confirmation(self) -> None:
        runtime = SimpleNamespace(
            state={
                "messages": [
                    {
                        "content": (
                            "Use attached thread file /uploads/icr_18650_datasheet.pdf.txt "
                            "for this DCR planning request."
                        )
                    }
                ]
            }
        )
        candidate = self._uploaded_datasheet_candidate()
        candidate["currents"].pop("max_continuous_discharge_current_a", None)

        with patch(
            "battery_agent.tools._load_uploaded_thread_file",
            return_value=(
                "/uploads/icr_18650_datasheet.pdf.txt",
                "Attachment extraction preview\n\nNominal voltage 3.7 V",
            ),
        ), patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value={"candidate": candidate},
        ), patch(
            "battery_agent.tools._await_parameter_request_answers",
            return_value={
                "max_continuous_discharge_current_a": 5.2,
                "dcir_definition": "Discharge and charge pulses; report R_2s/R_10s/R_18s using delta V over delta I referenced to the pre-pulse rest baseline at each SOC point.",
            },
        ):
            payload = json.loads(
                _plan_standard_test_impl(
                    method_id="pulse_hppc",
                    instrument="neware_bts4000_5v6a_8ch",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["release_status"], "review_required_protocol")
        self.assertFalse(payload["execution_blockers"])
        self.assertIsNone(payload["parameter_request"])
        self.assertEqual(
            payload["selected_cell_reference"]["max_continuous_discharge_current_a"],
            5.2,
        )


if __name__ == "__main__":
    unittest.main()
