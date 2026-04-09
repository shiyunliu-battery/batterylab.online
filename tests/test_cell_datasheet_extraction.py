import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import battery_agent.cell_catalog as cell_catalog
import battery_agent.cell_datasheet_extraction as extraction
import battery_agent.provisional_cell_assets as provisional_assets
import scripts.register_uploaded_cell_datasheet as register_uploaded_cell_datasheet
from battery_agent.tools import (
    _extract_uploaded_cell_datasheet_impl,
    _extract_uploaded_cell_datasheet_to_provisional_asset_impl,
    extract_uploaded_cell_datasheet,
    extract_uploaded_cell_datasheet_to_provisional_asset,
)


def _empty_manual_catalog() -> dict:
    return {
        "catalog_version": "manual_assets_v1",
        "generated_at_utc": "2026-03-20T00:00:00+00:00",
        "source_repository": "manual_review_queue",
        "cells": [],
    }


class _FakeResponses:
    def __init__(self, parsed_payload: extraction.CellDatasheetExtractionResponse) -> None:
        self._parsed_payload = parsed_payload
        self.last_kwargs: dict | None = None

    def parse(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(output_parsed=self._parsed_payload)


class _FakeOpenAIClient:
    def __init__(self, parsed_payload: extraction.CellDatasheetExtractionResponse) -> None:
        self.responses = _FakeResponses(parsed_payload)


class CellDatasheetExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        extraction.clear_cell_datasheet_extraction_client_cache()
        self.addCleanup(extraction.clear_cell_datasheet_extraction_client_cache)

    def test_extraction_model_defaults_to_main_agent_model(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "BATTERY_AGENT_MODEL": "openai:gpt-5.2",
                "BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_MODEL": "",
            },
            clear=False,
        ):
            self.assertEqual(extraction.get_cell_datasheet_extraction_model(), "gpt-5.2")

    def test_extract_cell_datasheet_candidate_from_text_parses_preview_metadata(self) -> None:
        parsed_payload = extraction.CellDatasheetExtractionResponse(
            candidate=extraction.CellDatasheetCandidate(
                display_name="K2 Energy K218650P01",
                manufacturer="K2 Energy Solutions",
                model="K218650P01",
                schema_name="K218650P01",
                project_chemistry_hint="lfp",
                form_factor="cylindrical",
                case_types=["18650"],
                electrical=extraction.ElectricalFields(
                    nominal_capacity_ah=1.25,
                    nominal_voltage_v=3.2,
                    charge_voltage_v=3.65,
                    discharge_cutoff_v=2.5,
                    internal_impedance_mohm=19.0,
                ),
                currents=extraction.CurrentFields(
                    max_continuous_charge_current_a=1.25,
                    max_continuous_discharge_current_a=5.0,
                    pulse_discharge_current_a_30s=12.0,
                ),
                physical=extraction.PhysicalFields(
                    mass_g=40.5,
                    diameter_mm=18.2,
                    height_mm=65.2,
                ),
                lifecycle=extraction.LifecycleFields(cycle_life_cycles=None),
                normalization_notes=[
                    "Used recommended operating conditions for formal planning fields.",
                ],
                suggested_review_notes=[
                    "Cycle life appears as a plot and was left as review-required instead of forcing a numeric cycle count."
                ],
                field_evidence=[
                    extraction.FieldEvidenceItem(
                        field_name="nominal_capacity_ah",
                        text_excerpt="Nominal Capacity @ C/5 (Ah) ....................... 1.25",
                        source_lines=[1],
                        confidence="high",
                        extraction_mode="explicit",
                    ),
                    extraction.FieldEvidenceItem(
                        field_name="nominal_voltage_v",
                        text_excerpt="Average Operating Voltage @ C/5 (V) ............ 3.2",
                        source_lines=[2],
                        confidence="medium",
                        extraction_mode="derived",
                        note="Mapped average operating voltage into nominal_voltage_v because no separate nominal-voltage field was stated.",
                    ),
                ],
                source_document=extraction.SourceDocumentMetadata(
                    original_filename="K218650P.pdf",
                    mime_type="application/pdf",
                    extraction_mode="pdf text extraction (pdfplumber)",
                    detected_pages=1,
                ),
            ),
            extraction_summary=[
                "Recommended operating conditions were used for formal current and voltage fields."
            ],
            missing_or_uncertain_fields=["cycle_life_cycles"],
        )
        fake_client = _FakeOpenAIClient(parsed_payload)
        preview_text = "\n".join(
            [
                "Attachment extraction preview",
                "Original filename: K218650P.pdf",
                "MIME type: application/pdf",
                "Extraction mode: pdf text extraction (pdfplumber)",
                "Detected pages: 1",
                "",
                "Nominal Capacity @ C/5 (Ah) ....................... 1.25",
                "Average Operating Voltage @ C/5 (V) ............ 3.2",
                "Charge Voltage Cutoff (V) ............................ 3.65",
            ]
        )

        with patch.object(extraction, "_get_openai_client", return_value=fake_client), patch.dict(
            "os.environ",
            {
                "BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_MODEL": "gpt-4o",
                "BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_TEMPERATURE": "0.0",
            },
            clear=False,
        ):
            payload = extraction.extract_cell_datasheet_candidate_from_text(
                preview_text,
                thread_file_path="/uploads/k218650p.pdf.txt",
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["model_name"], "gpt-4o")
        self.assertEqual(
            payload["candidate"]["source_document"]["original_filename"],
            "K218650P.pdf",
        )
        self.assertEqual(
            payload["candidate"]["field_evidence"]["nominal_capacity_ah"]["source_lines"],
            [1],
        )
        self.assertEqual(
            payload["candidate"]["field_evidence"]["nominal_voltage_v"]["extraction_mode"],
            "derived",
        )
        self.assertIn("L1:", fake_client.responses.last_kwargs["input"])

    def test_extract_cell_datasheet_candidate_from_text_rejects_metadata_placeholder(self) -> None:
        placeholder_text = json.dumps(
            {
                "kind": "pdf_attachment_placeholder",
                "original_filename": "K218650P.pdf",
                "mime_type": "application/pdf",
            }
        )

        with self.assertRaises(ValueError):
            extraction.extract_cell_datasheet_candidate_from_text(
                placeholder_text,
                thread_file_path="/uploads/k218650p.pdf.upload.json",
            )


class UploadedCellDatasheetToolTests(unittest.TestCase):
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

    def _thread_files(self) -> dict:
        return {
            "/uploads/k218650p.pdf.txt": {
                "content": [
                    "Attachment extraction preview",
                    "Original filename: K218650P.pdf",
                    "MIME type: application/pdf",
                    "Extraction mode: pdf text extraction (pdfplumber)",
                    "Detected pages: 1",
                    "",
                    "Nominal Capacity @ C/5 (Ah) ....................... 1.25",
                    "Average Operating Voltage @ C/5 (V) ............ 3.2",
                ],
                "created_at": "2026-03-20T12:00:00Z",
                "modified_at": "2026-03-20T12:00:00Z",
            }
        }

    def _extraction_payload(self) -> dict:
        return {
            "status": "ok",
            "parser_version": extraction.CELL_DATASHEET_EXTRACTION_PARSER_VERSION,
            "model_name": "gpt-4o",
            "temperature": 0.0,
            "source_document": {
                "original_filename": "K218650P.pdf",
                "mime_type": "application/pdf",
                "extraction_mode": "pdf text extraction (pdfplumber)",
                "detected_pages": 1,
                "thread_file_path": "/uploads/k218650p.pdf.txt",
                "extraction_provider": "openai_responses_api",
                "model_name": "gpt-4o",
            },
            "candidate": {
                "display_name": "K2 Energy K218650P01",
                "manufacturer": "K2 Energy Solutions",
                "model": "K218650P01",
                "schema_name": "K218650P01",
                "project_chemistry_hint": "lfp",
                "form_factor": "cylindrical",
                "case_types": ["18650"],
                "electrical": {
                    "nominal_capacity_ah": 1.25,
                    "nominal_voltage_v": 3.2,
                    "charge_voltage_v": 3.65,
                    "discharge_cutoff_v": 2.5,
                },
                "currents": {
                    "max_continuous_charge_current_a": 1.25,
                    "max_continuous_discharge_current_a": 5.0,
                },
                "physical": {
                    "mass_g": 40.5,
                    "diameter_mm": 18.2,
                    "height_mm": 65.2,
                },
                "lifecycle": {},
                "field_evidence": {
                    "nominal_capacity_ah": {
                        "text": "Nominal Capacity @ C/5 (Ah) ....................... 1.25",
                        "source_lines": [1],
                        "confidence": "high",
                        "extraction_mode": "explicit",
                    }
                },
                "source_document": {
                    "original_filename": "K218650P.pdf",
                    "mime_type": "application/pdf",
                    "extraction_mode": "pdf text extraction (pdfplumber)",
                    "detected_pages": 1,
                    "thread_file_path": "/uploads/k218650p.pdf.txt",
                    "extraction_provider": "openai_responses_api",
                    "model_name": "gpt-4o",
                },
                "normalization_notes": [
                    "Recommended operating conditions were mapped into the formal planning fields."
                ],
                "suggested_review_notes": [
                    "Cycle life appears only as a plot and was left blank."
                ],
            },
            "extraction_summary": [
                "Recommended operating conditions were mapped into formal fields."
            ],
            "missing_or_uncertain_fields": ["cycle_life_cycles"],
            "suggested_review_notes": [
                "Cycle life appears only as a plot and was left blank."
            ],
        }

    def test_extract_uploaded_cell_datasheet_missing_thread_file_returns_error(self) -> None:
        runtime = SimpleNamespace(state={"files": {}})
        payload = json.loads(
            extract_uploaded_cell_datasheet.func(
                file_path="uploads/missing.pdf.txt",
                runtime=runtime,
            )
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "uploaded_thread_file_not_found")

    def test_extract_uploaded_cell_datasheet_missing_injected_state_still_returns_error_payload(self) -> None:
        payload = json.loads(
            _extract_uploaded_cell_datasheet_impl(
                file_path="uploads/missing.pdf.txt",
            )
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "uploaded_thread_file_not_found")

    def test_extract_uploaded_cell_datasheet_falls_back_to_runtime_state_files(self) -> None:
        runtime = SimpleNamespace(state={"files": self._thread_files()})

        with patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value=self._extraction_payload(),
        ):
            payload = json.loads(
                extract_uploaded_cell_datasheet.func(
                    file_path="uploads/k218650p.pdf.txt",
                    runtime=runtime,
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["candidate"]["manufacturer"], "K2 Energy Solutions")

    def test_extract_uploaded_cell_datasheet_to_provisional_asset_registers_asset(self) -> None:
        with patch(
            "battery_agent.tools.extract_cell_datasheet_candidate_from_text",
            return_value=self._extraction_payload(),
        ):
            payload = json.loads(
                _extract_uploaded_cell_datasheet_to_provisional_asset_impl(
                    file_path="uploads/k218650p.pdf.txt",
                    submitted_by="alice",
                    submit_for_review=True,
                    runtime=SimpleNamespace(state={"files": self._thread_files()}),
                )
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["asset"]["review_status"], "submitted_for_review")
        self.assertEqual(
            payload["asset"]["source_document"]["original_filename"],
            "K218650P.pdf",
        )
        self.assertEqual(
            payload["asset"]["parser_version"],
            extraction.CELL_DATASHEET_EXTRACTION_PARSER_VERSION,
        )
        self.assertEqual(payload["extraction"]["model_name"], "gpt-4o")

    def test_register_uploaded_cell_datasheet_script_uses_nested_candidate_payload(self) -> None:
        with patch(
            "scripts.register_uploaded_cell_datasheet.extract_cell_datasheet_candidate_from_text",
            return_value=self._extraction_payload(),
        ):
            result = register_uploaded_cell_datasheet.register_uploaded_cell_datasheet_payload(
                {
                    "file_path": "/uploads/k218650p.pdf.txt",
                    "attachment_text": "\n".join(
                        self._thread_files()["/uploads/k218650p.pdf.txt"]["content"]
                    ),
                    "submitted_by": "alice",
                    "submit_for_review": True,
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["asset"]["display_name"], "K2 Energy K218650P01")
        self.assertEqual(result["asset"]["review_status"], "submitted_for_review")


if __name__ == "__main__":
    unittest.main()
