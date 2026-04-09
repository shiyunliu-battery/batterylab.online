import json
import unittest

from battery_agent.tools import TOOLS, describe_lab_backend_framework, get_demo_assets


class BackendFrameworkScaffoldTests(unittest.TestCase):
    def test_active_tool_surface_excludes_heavy_simulation_tools(self) -> None:
        tool_names = {tool.name for tool in TOOLS}

        self.assertIn("describe_lab_backend_framework", tool_names)
        self.assertIn("extract_uploaded_cell_datasheet", tool_names)
        self.assertIn("extract_uploaded_cell_datasheet_to_provisional_asset", tool_names)
        self.assertIn("parse_raw_cycler_export", tool_names)
        self.assertNotIn("list_available_standards", tool_names)
        self.assertNotIn("preview_method_with_modeling", tool_names)
        self.assertNotIn("simulate_protocol", tool_names)
        self.assertNotIn("simulate_simple_discharge", tool_names)
        self.assertNotIn("simulate_soc_ocv", tool_names)
        self.assertNotIn("simulate_hppc_test_results", tool_names)

    def test_framework_summary_lists_new_asset_groups(self) -> None:
        payload = json.loads(describe_lab_backend_framework.invoke({}))
        asset_ids = {item["id"] for item in payload["workflow_assets"]}

        self.assertEqual(payload["status"], "ok")
        self.assertIn("equipment_manual_index", asset_ids)
        self.assertIn("method_handbook_source_index", asset_ids)
        self.assertIn("method_handbook_evidence_cards", asset_ids)
        self.assertIn("data_adapter_registry", asset_ids)
        self.assertIn("doe_template_registry", asset_ids)
        self.assertNotIn("model preview", payload["ui_markdown"].lower())

    def test_demo_asset_listing_includes_workflow_asset_groups(self) -> None:
        payload = json.loads(get_demo_assets.invoke({}))

        self.assertIn("workflow_asset_groups", payload)
        self.assertIn("equipment_manual_index", payload["workflow_asset_groups"])
        self.assertIn("method_handbook_source_index", payload["workflow_asset_groups"])
        self.assertIn("metric_definition_registry", payload["workflow_asset_groups"])
        self.assertIn("thermal_chambers", payload)
        self.assertIn("binder_lit_mk", payload["thermal_chambers"])
        self.assertNotIn("thermal_chambers", payload["instruments"])


if __name__ == "__main__":
    unittest.main()
