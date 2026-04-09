import json
import importlib
import unittest

from battery_agent.kb import REPO_ROOT
from battery_agent.knowledge import get_literature_source
from battery_agent.tools import (
    load_battery_knowledge,
    load_literature_source,
    search_literature_evidence_cards,
)


class LiteratureAssetTests(unittest.TestCase):
    def test_source_summary_and_card_bundle_exist(self) -> None:
        payload = get_literature_source("roman_ramirez_2022_doe_review")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["source_type"], "journal_article")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 8)
        self.assertIn("Evidence Cards Saved From This Source", payload["summary_markdown"])

    def test_tugraz_source_is_stored_as_theory_foundation(self) -> None:
        payload = get_literature_source("tugraz_doe_notes")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["source_type"], "course_notes")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 5)
        self.assertIn("Relation To Existing DOE Battery Literature", payload["summary_markdown"])
        self.assertIn("roman_ramirez_2022_doe_review", payload["summary_markdown"])

    def test_naylor_source_is_stored_as_parallel_pack_case_study(self) -> None:
        payload = get_literature_source("naylor_marlow_2024_parallel_pack_thermal_gradients")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["source_type"], "journal_article")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 6)
        self.assertIn("What The Supplement Adds", payload["summary_markdown"])
        self.assertIn("roman_ramirez_2022_doe_review", payload["summary_markdown"])

    def test_barai_source_is_stored_as_primary_theory_review(self) -> None:
        payload = get_literature_source("barai_2019_noninvasive_characterisation_review")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["source_type"], "journal_article")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 7)
        self.assertIn("Core Formula And Theory Basis", payload["summary_markdown"])
        self.assertIn("Butler-Volmer", payload["summary_markdown"])
        self.assertIn("electrochemical voltage spectroscopy", payload["summary_markdown"].lower())

    def test_insertion_impedance_source_is_stored_as_supporting_theory_note(self) -> None:
        payload = get_literature_source("study_of_the_insertion_reaction_by_impedance_notes")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source"]["source_type"], "technical_slides")
        self.assertGreaterEqual(len(payload["evidence_cards"]), 4)
        self.assertIn("Warburg", payload["summary_markdown"])
        self.assertIn("bounded diffusion", payload["summary_markdown"].lower())

    def test_search_tool_returns_page_level_citation(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "ECM parameter identification DOE",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_count"], 1)
        self.assertGreaterEqual(payload["matched_source_count"], 1)
        self.assertEqual(payload["matches"][0]["card_id"], "roman_ramirez_2022_parameter_identification")
        self.assertEqual(payload["matches"][0]["citation"]["supporting_pages"], "pp. 15-16")
        self.assertIn(
            "Supporting pages used above: pp. 15-16.",
            payload["matches"][0]["citation"]["answer_reference_with_pages_markdown"],
        )
        self.assertEqual(
            payload["matches"][0]["citation"]["answer_reference_with_pages_markdown"].count("]("),
            1,
        )
        self.assertIn("coverage_note", payload)
        self.assertIn("matched_sources", payload)
        self.assertIn("sciencedirect.com", payload["ui_markdown"])

    def test_search_tool_groups_single_source_results(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "charging optimization OA orthogonal array D-optimal",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["matched_source_count"], 1)
        self.assertEqual(payload["matched_sources"][0]["source_id"], "roman_ramirez_2022_doe_review")
        self.assertLessEqual(payload["matched_count"], 3)
        self.assertIn("source-backed guidance", payload["coverage_note"])
        self.assertIn("### Sources", payload["ui_markdown"])

    def test_search_tool_can_return_theory_source_for_blocking_queries(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "randomized block confounding factorial design",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_source_count"], 1)
        self.assertEqual(payload["matched_sources"][0]["source_id"], "tugraz_doe_notes")
        self.assertTrue(
            any(match["card_id"].startswith("tugraz_doe_notes_") for match in payload["matches"])
        )

    def test_search_tool_can_surface_both_theory_and_battery_sources(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "battery DOE theory randomization blocking factorial",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_source_count"], 2)
        source_ids = {item["source_id"] for item in payload["matched_sources"]}
        self.assertIn("roman_ramirez_2022_doe_review", source_ids)
        self.assertIn("tugraz_doe_notes", source_ids)

    def test_search_tool_can_surface_parallel_pack_case_study_source(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "parallel pack thermal gradient current distribution cathode impedance",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_source_count"], 1)
        self.assertEqual(
            payload["matched_sources"][0]["source_id"],
            "naylor_marlow_2024_parallel_pack_thermal_gradients",
        )
        self.assertTrue(
            any(
                match["card_id"].startswith("naylor_marlow_2024_")
                for match in payload["matches"]
            )
        )

    def test_search_tool_can_surface_barai_method_theory_source(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "non-invasive characterisation incremental capacity differential voltage HPPC EIS theory",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_source_count"], 1)
        self.assertEqual(
            payload["matched_sources"][0]["source_id"],
            "barai_2019_noninvasive_characterisation_review",
        )
        self.assertTrue(
            any(match["card_id"].startswith("barai_2019_") for match in payload["matches"])
        )

    def test_search_tool_surfaces_barai_equation_notes(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "Butler Volmer Arrhenius pulse resistance Nyquist ECM",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["matched_sources"][0]["source_id"],
            "barai_2019_noninvasive_characterisation_review",
        )
        self.assertTrue(
            any(match.get("equation_notes") for match in payload["matches"])
        )
        joined_equation_notes = " ".join(
            " ".join(match.get("equation_notes", [])) for match in payload["matches"]
        )
        self.assertIn("R_pulse", joined_equation_notes)
        self.assertIn("Z(omega)", joined_equation_notes)

    def test_search_tool_can_surface_insertion_impedance_theory_source(self) -> None:
        payload = json.loads(
            search_literature_evidence_cards.invoke(
                {
                    "query": "Warburg bounded diffusion insertion reaction impedance battery",
                    "limit": 3,
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["matched_source_count"], 1)
        self.assertEqual(
            payload["matched_sources"][0]["source_id"],
            "study_of_the_insertion_reaction_by_impedance_notes",
        )
        self.assertTrue(
            any(match["card_id"].startswith("insertion_impedance_") for match in payload["matches"])
        )

    def test_load_tool_surfaces_linked_reference_and_summary(self) -> None:
        payload = json.loads(
            load_literature_source.invoke(
                {
                    "source_id": "roman_ramirez_2022_doe_review",
                }
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertIn("linked_reference_markdown", payload["source"])
        self.assertIn("answer_reference_markdown", payload["source"])
        self.assertIn("Design Of Experiments Applied To Lithium-Ion Batteries", payload["summary_markdown"])

    def test_legacy_module_imports_still_work(self) -> None:
        legacy_literature = importlib.import_module("battery_agent.literature")
        legacy_method_handbook = importlib.import_module("battery_agent.method_handbook")

        self.assertTrue(hasattr(legacy_literature, "get_literature_source"))
        self.assertTrue(hasattr(legacy_method_handbook, "get_method_handbook_source"))

    def test_unknown_doe_objective_returns_handoff_instead_of_error(self) -> None:
        payload = json.loads(
            load_battery_knowledge.invoke(
                {
                    "objective": "charging_optimization",
                }
            )
        )

        self.assertEqual(payload["status"], "not_applicable")
        self.assertEqual(payload["recommended_tool"], "search_knowledge_evidence_cards")
        self.assertEqual(payload["normalized_objective"], "charging_optimization")
        self.assertEqual(payload["trust_level"], "advisory_handoff")

    def test_doe_templates_reference_seeded_literature_cards(self) -> None:
        registry_path = REPO_ROOT / "data" / "workflows" / "doe" / "doe_template_registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        template_ids = {item["id"] for item in registry["templates"]}

        self.assertEqual(registry["status"], "seeded_from_literature")
        self.assertIn("mixture_formulation_v1", template_ids)
        self.assertIn("charging_optimization_v1", template_ids)
        self.assertIn("parameter_identification_design_v1", template_ids)
        self.assertIn("blocked_factorial_v1", template_ids)
        for item in registry["templates"]:
            self.assertTrue(item["evidence_card_ids"])


if __name__ == "__main__":
    unittest.main()
