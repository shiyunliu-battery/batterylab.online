import unittest

from battery_agent.prompts import MAIN_SYSTEM_PROMPT, PROTOCOL_SUBAGENT_PROMPT


class PromptGuardrailTests(unittest.TestCase):
    def test_main_prompt_requires_controlled_planning_source_before_step_guidance(self) -> None:
        self.assertIn(
            "load at least one controlled planning source",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "call a controlled planning tool in the same turn",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "do not replace the missing tool-backed steps with model-authored defaults",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Let the interrupt/popup collect the answers",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Do not present generic SOC ladders, pulse durations, rest times, current levels, or checkpoint cadences",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "cite them inline using the tool-provided reference tokens",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "reuse those same bibliography entries in the final `References` section",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "format it as `Display Name (cell id: CELL_ID)` on one line",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "treat those as binding decision semantics for planning and review",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "do not dump relation-class inventories, conflict-field lists, or authority-model bullet lists",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "obey the most recent planning-tool policy",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "obey the tool-provided authority and precedence model",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "present them as review gates or lock-before-release items",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "keep the answer compact: state the blocker, list the already-active constraints, and ask only for the exact missing inputs needed to continue",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "do not re-ask a broader objective-selection question",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Bind citations to the source family named in `answer_citation_map` or `claim_bindings`",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "If `response_policy.allow_step_level_protocol` is false, do not output a step-by-step procedure",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "end with a final section titled exactly `## Experiment Plan`",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "compile them into one coherent campaign instead of listing disconnected method summaries",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "explicitly identify which tests generate labels, which generate features, and which generate checkpoint or metadata tables",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "do not use the literal word `handbook`",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "For multi-cell comparison, screening, DCR/power, ageing, or future-analysis requests, give one recommended default campaign",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "The operator/researcher-ready plan should dominate the answer.",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "`Plan Status & Constraints`, `Protocol`, and `Outputs & Basis`",
            MAIN_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Only include `Analysis Plan` when the user explicitly asked for statistics",
            MAIN_SYSTEM_PROMPT,
        )

    def test_protocol_prompt_blocks_generic_fallbacks_from_memory(self) -> None:
        self.assertIn(
            "call at least one controlled planning source before writing a step sequence",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "Do not stop at a preflight-only knowledge load",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "do not invent concrete pulse durations, SOC ladders, rest times, or current setpoints from memory",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "Let the popup/interrupt collect the missing values",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "If the user asks whether you used their knowledge, answer strictly from the tools actually used in the turn.",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "If a planning tool returns `planning_mode=advisory_gap_mode`",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "If a tool provides `answer_references`, use the tool-provided reference tokens",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "reuse those same bibliography entries in the final `References` section",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "format it as `Display Name (cell id: CELL_ID)` on one line",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "preserve authority and precedence, applicability conditions, requirement strength, and review semantics",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "do not echo relation-class lists, conflict-field inventories, or full authority-model bullet lists",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "follow the later planning payload for the active draft",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "do not turn a Settings default thermal chamber into an active requirement in the answer",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "do not ask a broader family-selection question",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "Use the claim-binding citations from `answer_citation_map`",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "keep the answer short: blocker, active constraints already locked, and the exact next inputs needed",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "finish with a final section titled exactly `## Experiment Plan`",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "compile them into one coherent campaign instead of listing method summaries independently",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "baseline characterization, ageing blocks, checkpoints, and end-of-life package",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "do not use the literal word `handbook`",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "For multi-cell campaigns, recommend a concrete default cohort plan instead of only listing options.",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "clear protocol structure, fact-layered constraints, equipment/setup, data package",
            PROTOCOL_SUBAGENT_PROMPT,
        )
        self.assertIn(
            "present the core parameters in a dedicated parameter table and define the resistance metrics explicitly",
            PROTOCOL_SUBAGENT_PROMPT,
        )


if __name__ == "__main__":
    unittest.main()
