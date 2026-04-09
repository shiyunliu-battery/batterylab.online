import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import battery_agent.cell_catalog as cell_catalog
import battery_agent.provisional_cell_assets as provisional_assets
from battery_agent.cell_catalog import get_cell_catalog_record, load_cell_catalog
from battery_agent.tools import (
    load_provisional_cell_asset,
    promote_provisional_cell_asset,
    register_provisional_cell_asset,
    review_provisional_cell_asset,
    search_provisional_cell_assets,
)


def _empty_manual_catalog() -> dict:
    return {
        "catalog_version": "manual_assets_v1",
        "generated_at_utc": "2026-03-20T00:00:00+00:00",
        "source_repository": "manual_review_queue",
        "cells": [],
    }


class ProvisionalCellAssetWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        temp_root = Path(self._tempdir.name)
        self.provisional_path = temp_root / "provisional_cell_assets.json"
        self.manual_path = temp_root / "manual_cell_assets.json"
        self.provisional_path.write_text(
            json.dumps(provisional_assets._default_provisional_store(), indent=2) + "\n",
            encoding="utf-8",
        )
        self.manual_path.write_text(
            json.dumps(_empty_manual_catalog(), indent=2) + "\n",
            encoding="utf-8",
        )

        self._patches = [
            patch.object(provisional_assets, "PROVISIONAL_CELL_ASSET_PATH", self.provisional_path),
            patch.object(cell_catalog, "MANUAL_CELL_CATALOG_PATH", self.manual_path),
        ]
        for active_patch in self._patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

        provisional_assets.clear_provisional_cell_asset_cache()
        cell_catalog.clear_cell_catalog_cache()
        self.addCleanup(provisional_assets.clear_provisional_cell_asset_cache)
        self.addCleanup(cell_catalog.clear_cell_catalog_cache)

    def _complete_asset(self) -> dict:
        return {
            "display_name": "ACME LFP 21700 5Ah",
            "manufacturer": "ACME",
            "model": "LFP21700_50E",
            "project_chemistry_hint": "lfp",
            "form_factor": "cylindrical",
            "case_types": ["21700"],
            "electrical": {
                "nominal_capacity_ah": 5.0,
                "nominal_voltage_v": 3.2,
                "charge_voltage_v": 3.65,
                "discharge_cutoff_v": 2.0,
            },
            "currents": {
                "max_continuous_charge_current_a": 5.0,
                "max_continuous_discharge_current_a": 10.0,
            },
            "physical": {
                "mass_g": 70.0,
                "diameter_mm": 21.0,
                "height_mm": 70.0,
            },
            "lifecycle": {
                "cycle_life_cycles": 2000,
            },
            "field_evidence": {
                "nominal_capacity_ah": {
                    "page": 2,
                    "text": "Nominal capacity: 5000 mAh",
                    "confidence": "high",
                }
            },
        }

    def _incomplete_asset(self) -> dict:
        asset = self._complete_asset()
        asset["display_name"] = "ACME LFP 21700 Missing Cycle Life"
        asset["model"] = "LFP21700_MISSING"
        asset["lifecycle"] = {}
        return asset

    def test_register_provisional_asset_stays_planning_ineligible(self) -> None:
        payload = json.loads(
            register_provisional_cell_asset.invoke(
                {
                    "asset_json": json.dumps(self._complete_asset()),
                    "submitted_by": "alice",
                    "source_file": "uploads/acme_lfp_21700.pdf",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        asset = payload["asset"]
        self.assertEqual(asset["review_status"], "draft_extracted")
        self.assertEqual(asset["approval_status"], "unapproved")
        self.assertFalse(asset["eligible_for_planning"])
        self.assertTrue(asset["promotable_if_reviewed"])
        self.assertEqual(asset["source_document"]["path"], "uploads/acme_lfp_21700.pdf")

        search_payload = json.loads(search_provisional_cell_assets.invoke({}))
        self.assertEqual(search_payload["status"], "ok")
        self.assertEqual(search_payload["asset_count"], 1)
        self.assertEqual(search_payload["assets"][0]["review_status"], "draft_extracted")

    def test_register_sanitizes_lone_surrogates_before_persisting(self) -> None:
        asset = self._complete_asset()
        asset["field_evidence"]["nominal_capacity_ah"]["text"] = "Nominal \udc90 capacity: 5000 mAh"

        payload = json.loads(
            register_provisional_cell_asset.invoke(
                {
                    "asset_json": json.dumps(asset),
                    "submitted_by": "alice",
                    "source_file": "uploads/acme_lfp_21700.pdf",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        stored_payload = json.loads(self.provisional_path.read_text(encoding="utf-8"))
        stored_text = stored_payload["assets"][0]["field_evidence"]["nominal_capacity_ah"]["text"]
        self.assertNotIn("\udc90", stored_text)
        self.assertIn("\uFFFD", stored_text)

    def test_review_rejects_promotion_when_required_fields_are_missing(self) -> None:
        register_payload = json.loads(
            register_provisional_cell_asset.invoke(
                {
                    "asset_json": json.dumps(self._incomplete_asset()),
                    "submitted_by": "alice",
                    "submit_for_review": True,
                }
            )
        )

        review_payload = json.loads(
            review_provisional_cell_asset.invoke(
                {
                    "provisional_id": register_payload["asset"]["provisional_id"],
                    "decision": "approve_for_promotion",
                    "actor": "reviewer_bob",
                }
            )
        )

        self.assertEqual(review_payload["status"], "error")
        self.assertEqual(review_payload["error_type"], "provisional_review_validation_error")
        self.assertIn("cycle_life_cycles", review_payload["message"])

    def test_review_can_apply_explicit_waiver_before_promotion(self) -> None:
        register_payload = json.loads(
            register_provisional_cell_asset.invoke(
                {
                    "asset_json": json.dumps(self._incomplete_asset()),
                    "submitted_by": "alice",
                }
            )
        )
        provisional_id = register_payload["asset"]["provisional_id"]

        review_payload = json.loads(
            review_provisional_cell_asset.invoke(
                {
                    "provisional_id": provisional_id,
                    "decision": "approve_for_promotion",
                    "actor": "reviewer_bob",
                    "review_notes_json": json.dumps(
                        ["Cycle life is intentionally waived because the supplier table does not report it."]
                    ),
                    "required_field_waivers_json": json.dumps(["cycle_life_cycles"]),
                }
            )
        )

        self.assertEqual(review_payload["status"], "ok")
        self.assertEqual(review_payload["asset"]["review_status"], "approved_for_promotion")
        self.assertEqual(review_payload["asset"]["waived_missing_required_fields"], ["cycle_life_cycles"])

        promote_payload = json.loads(
            promote_provisional_cell_asset.invoke(
                {
                    "provisional_id": provisional_id,
                    "reviewer": "reviewer_bob",
                    "promotion_notes_json": json.dumps(["Approved as a literature-backed exception."]),
                }
            )
        )

        self.assertEqual(promote_payload["status"], "ok")
        promoted_record = promote_payload["promoted_manual_record"]
        self.assertEqual(promoted_record["required_field_waivers"], ["cycle_life_cycles"])
        promoted_catalog_record = get_cell_catalog_record(promoted_record["cell_id"])
        self.assertEqual(promoted_catalog_record["approval_basis"], "reviewed_provisional_asset")
        self.assertEqual(
            promoted_catalog_record["waived_missing_required_fields"],
            ["cycle_life_cycles"],
        )
        self.assertTrue(promoted_catalog_record["eligible_for_planning"])

    def test_promoted_asset_reaches_formal_manual_surface(self) -> None:
        register_payload = json.loads(
            register_provisional_cell_asset.invoke(
                {
                    "asset_json": json.dumps(self._complete_asset()),
                    "submitted_by": "alice",
                    "submit_for_review": True,
                }
            )
        )
        provisional_id = register_payload["asset"]["provisional_id"]

        review_payload = json.loads(
            review_provisional_cell_asset.invoke(
                {
                    "provisional_id": provisional_id,
                    "decision": "approve_for_promotion",
                    "actor": "reviewer_bob",
                    "review_notes_json": json.dumps(["Checked against the uploaded datasheet PDF."]),
                }
            )
        )
        self.assertEqual(review_payload["status"], "ok")

        promote_payload = json.loads(
            promote_provisional_cell_asset.invoke(
                {
                    "provisional_id": provisional_id,
                    "reviewer": "reviewer_bob",
                }
            )
        )

        self.assertEqual(promote_payload["status"], "ok")
        self.assertEqual(promote_payload["asset"]["review_status"], "promoted_to_manual_asset")
        self.assertEqual(promote_payload["promoted_manual_record"]["cell_id"], "ACME_LFP21700_50E")

        loaded_provisional = json.loads(
            load_provisional_cell_asset.invoke({"provisional_id": provisional_id})
        )
        self.assertEqual(loaded_provisional["status"], "ok")
        self.assertEqual(
            loaded_provisional["asset_summary"]["review_status"],
            "promoted_to_manual_asset",
        )

        catalog = load_cell_catalog()
        self.assertEqual(catalog["manual_asset_count"], 1)
        promoted_record = get_cell_catalog_record("ACME_LFP21700_50E")
        self.assertEqual(promoted_record["approval_status"], "approved")
        self.assertEqual(promoted_record["approval_basis"], "reviewed_provisional_asset")
        self.assertTrue(promoted_record["eligible_for_planning"])


if __name__ == "__main__":
    unittest.main()
