"""Battery test method loaders and planners backed by curated knowledge summaries."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from battery_agent.kb import (
    REPO_ROOT,
    get_authority_and_precedence_model,
    get_decision_conflict_representation,
    get_decision_relation_classes,
    get_decision_relation_model,
    get_equipment_rule,
    get_objective_template,
    get_pretest_assistant_guidance,
    get_pretest_global_defaults,
    get_pretest_objective_guidance,
    get_pretest_rpt_playbook,
    get_requirement_strength_levels,
    get_safety_checklist,
    get_thermocouple_placement_guidance,
    get_thermal_chamber_rule,
    chamber_required_for_temperature,
    load_kb,
    normalize_objective_key,
)
from battery_agent.planning_context import (
    build_selected_cell_current_warnings,
    build_selected_cell_reference,
    load_selected_cell_record,
    resolve_chemistry_profile,
    resolve_form_factor,
    resolve_voltage_window,
)
from battery_agent.knowledge import get_method_handbook_source_for_method
from battery_agent.registries import (
    get_method_definition,
    load_method_registry,
    resolve_method_id,
)

KNOWLEDGE_DIR = REPO_ROOT / "data" / "reference" / "knowledge"
CHAPTER_INDEX_PATH = KNOWLEDGE_DIR / "chapter_index.json"
KNOWLEDGE_SUMMARIES_DIR = REPO_ROOT / "data" / "reference" / "knowledge" / "summaries"
SOURCE_PDF = REPO_ROOT / "Test methods for battery understanding_v3_0.pdf"


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_asset_path(path: str | Path | None) -> str | None:
    if path is None:
        return None

    path_obj = Path(path)
    try:
        return path_obj.resolve(strict=False).relative_to(REPO_ROOT.resolve(strict=False)).as_posix()
    except Exception:
        return path_obj.name


def _display_repo_asset_if_exists(path: str | Path | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    if not path_obj.exists():
        return None
    return _display_asset_path(path_obj)


def _sanitize_method_source(source: dict[str, Any] | None) -> dict[str, Any] | None:
    if source is None:
        return None
    sanitized = dict(source)
    if sanitized.get("chapter_file") is not None:
        sanitized["chapter_file"] = _display_asset_path(str(sanitized["chapter_file"]))
    return sanitized


def _resolve_method_reference_file(
    handbook_source: dict[str, Any] | None,
    chapter_id: str | None,
) -> str | None:
    candidates: list[str] = []
    if handbook_source:
        for key in ("chapter_file", "summary_path"):
            value = str(handbook_source.get(key) or "").strip()
            if value:
                candidates.append(value)
    if chapter_id:
        fallback = _display_asset_path(KNOWLEDGE_SUMMARIES_DIR / f"{chapter_id}.md")
        if fallback:
            candidates.append(fallback)

    for candidate in candidates:
        normalized = _display_asset_path(candidate)
        if normalized and (REPO_ROOT / normalized).exists():
            return normalized

    for candidate in candidates:
        normalized = _display_asset_path(candidate)
        if normalized:
            return normalized
    return None


@lru_cache(maxsize=1)
def load_chapter_index() -> list[dict[str, Any]]:
    if not CHAPTER_INDEX_PATH.exists():
        return []
    return _read_json(CHAPTER_INDEX_PATH)


@lru_cache(maxsize=1)
def load_structured_methods() -> dict[str, dict[str, Any]]:
    return load_method_registry()


def _get_method_handbook_bundle(
    *,
    method_id: str | None = None,
    chapter_id: str | None = None,
) -> dict[str, Any] | None:
    try:
        return get_method_handbook_source_for_method(method_id=method_id, chapter_id=chapter_id)
    except KeyError:
        return None


def _build_method_evidence_card_index(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(card["card_id"]): card
        for card in cards
        if isinstance(card, dict) and isinstance(card.get("card_id"), str)
    }


def _bullet_lines(items: list[str] | None) -> str:
    if not items:
        return "- None declared."
    return "\n".join(f"- {item}" for item in items)


def _render_inline_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "none"
    if isinstance(value, dict):
        rendered_parts = [f"{key}={item}" for key, item in value.items()]
        return ", ".join(rendered_parts) or "none"
    return str(value)


def _build_conditional_required_input_lines(
    conditional_required_inputs: list[dict[str, Any]] | None,
) -> str:
    if not conditional_required_inputs:
        return "- None declared."

    rendered: list[str] = []
    for item in conditional_required_inputs:
        if not isinstance(item, dict):
            continue
        when = str(item.get("when") or "a declared condition applies")
        required = ", ".join(item.get("required", [])) or "not declared"
        note = str(item.get("note") or "").strip()
        line = f"- When {when}: require {required}."
        if note:
            line += f" {note}"
        rendered.append(line)

    return "\n".join(rendered) if rendered else "- None declared."


def _build_source_example_default_lines(source_example_defaults: dict[str, Any]) -> str:
    if not isinstance(source_example_defaults, dict) or not source_example_defaults:
        return "- None declared."

    return "\n".join(
        f"- {key.replace('_', ' ')}: {_render_inline_value(value)}"
        for key, value in source_example_defaults.items()
    )


def _build_input_contract_payload(
    method: dict[str, Any],
    *,
    declared_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conditional_required_inputs = [
        dict(item)
        for item in method.get("conditional_required_inputs", [])
        if isinstance(item, dict)
    ]
    payload = {
        "required_inputs": list(method.get("required_inputs", [])),
        "conditional_required_inputs": conditional_required_inputs,
        "optional_inputs": list(method.get("optional_inputs", [])),
        "source_example_defaults": dict(method.get("source_example_defaults", {})),
    }
    if declared_inputs is None:
        return payload

    resolved_required_inputs = [
        field_name
        for field_name in payload["required_inputs"]
        if _is_declared_input_present(declared_inputs.get(field_name))
    ]
    unresolved_required_inputs = [
        field_name
        for field_name in payload["required_inputs"]
        if field_name not in resolved_required_inputs
    ]
    active_conditional_required_inputs: list[dict[str, Any]] = []
    missing_conditional_required_inputs: list[str] = []
    for rule in conditional_required_inputs:
        if not _conditional_rule_matches(rule, declared_inputs=declared_inputs):
            continue
        active_conditional_required_inputs.append(dict(rule))
        for field_name in rule.get("required", []):
            if not _is_declared_input_present(declared_inputs.get(field_name)):
                missing_conditional_required_inputs.append(str(field_name))

    payload.update(
        {
            "resolved_required_inputs": resolved_required_inputs,
            "unresolved_required_inputs": unresolved_required_inputs,
            "active_conditional_required_inputs": active_conditional_required_inputs,
            "missing_conditional_required_inputs": list(
                dict.fromkeys(missing_conditional_required_inputs)
            ),
        }
    )
    return payload


class MissingMethodInputsError(ValueError):
    def __init__(
        self,
        *,
        method_id: str,
        missing_fields: list[str],
        input_contract: dict[str, Any],
        declared_inputs: dict[str, Any],
    ) -> None:
        self.method_id = method_id
        self.missing_fields = list(dict.fromkeys(missing_fields))
        self.input_contract = input_contract
        self.declared_inputs = declared_inputs
        super().__init__(
            f"Method '{method_id}' is missing required planning inputs: "
            + ", ".join(self.missing_fields)
            + ". Review the method input contract and provide the missing fields."
        )


def _is_declared_input_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _normalize_condition_token(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _conditional_rule_matches(
    rule: dict[str, Any],
    *,
    declared_inputs: dict[str, Any],
) -> bool:
    when_clause = str(rule.get("when") or "").strip()
    if not when_clause or "=" not in when_clause:
        return False

    field_name, raw_value_clause = [part.strip() for part in when_clause.split("=", 1)]
    if not field_name:
        return False

    declared_value = declared_inputs.get(field_name)
    if not _is_declared_input_present(declared_value):
        return False

    normalized_declared = _normalize_condition_token(declared_value)
    normalized_options = [
        _normalize_condition_token(option)
        for option in raw_value_clause.split(" or ")
        if str(option).strip()
    ]
    return normalized_declared in normalized_options


def _build_declared_method_inputs(
    *,
    method: dict[str, Any],
    chemistry_profile: dict[str, Any] | None,
    selected_cell_reference: dict[str, Any] | None,
    instrument: str,
    thermal_chamber: str | None,
    effective_form_factor: str | None,
    target_temperature_c: float,
    requested_charge_c_rate: float,
    requested_discharge_c_rate: float,
    run_length_field: str,
    run_length_value: Any,
    method_inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    declared_inputs = {
        str(key): value
        for key, value in (method_inputs or {}).items()
        if isinstance(key, str)
    }
    method_defaults = method.get("protocol_template", {}).get(
        "defaults",
        method.get("recommended_defaults", {}),
    )
    reference_check_policy = method.get("reference_check_policy", {})
    cadence_mode = (
        reference_check_policy.get("rpt_cadence_mode", {}).get("default_mode")
        if isinstance(reference_check_policy.get("rpt_cadence_mode"), dict)
        else None
    )

    declared_inputs.setdefault(
        "chemistry",
        chemistry_profile["id"]
        if chemistry_profile is not None
        else (
            selected_cell_reference.get("chemistry_hint")
            if selected_cell_reference is not None
            else None
        ),
    )
    declared_inputs.setdefault("instrument", instrument)
    declared_inputs.setdefault("thermal_chamber", thermal_chamber)
    declared_inputs.setdefault("form_factor", effective_form_factor)
    declared_inputs.setdefault("target_temperature_c", target_temperature_c)
    declared_inputs.setdefault("charge_c_rate", requested_charge_c_rate)
    declared_inputs.setdefault("discharge_c_rate", requested_discharge_c_rate)
    declared_inputs.setdefault(
        "block_basis",
        method_defaults.get("default_block_basis"),
    )
    declared_inputs.setdefault("rpt_cadence_mode", cadence_mode)
    declared_inputs[run_length_field] = run_length_value
    return declared_inputs


def _validate_declared_method_inputs(
    *,
    method: dict[str, Any],
    declared_inputs: dict[str, Any],
) -> None:
    missing_required = [
        field_name
        for field_name in method.get("required_inputs", [])
        if not _is_declared_input_present(declared_inputs.get(field_name))
    ]

    missing_conditional: list[str] = []
    for rule in method.get("conditional_required_inputs", []):
        if not isinstance(rule, dict):
            continue
        if not _conditional_rule_matches(rule, declared_inputs=declared_inputs):
            continue
        for field_name in rule.get("required", []):
            if not _is_declared_input_present(declared_inputs.get(field_name)):
                missing_conditional.append(str(field_name))

    missing_fields = list(dict.fromkeys([*missing_required, *missing_conditional]))
    if not missing_fields:
        return

    raise MissingMethodInputsError(
        method_id=str(method.get("id") or "unknown"),
        missing_fields=missing_fields,
        input_contract=_build_input_contract_payload(
            method,
            declared_inputs=declared_inputs,
        ),
        declared_inputs=declared_inputs,
    )


def _resolve_planning_run_length(
    *,
    method: dict[str, Any],
    requested_run_length: Any,
) -> dict[str, Any]:
    method_defaults = method.get("protocol_template", {}).get(
        "defaults",
        method.get("recommended_defaults", {}),
    )
    cadence_mode = str(
        method.get("reference_check_policy", {})
        .get("rpt_cadence_mode", {})
        .get("default_mode")
        or ""
    ).strip()

    if "minimum_cycle_count" in method_defaults:
        field_name = str(method_defaults.get("run_length_field") or "cycle_count")
        basis = str(method_defaults.get("default_block_basis") or cadence_mode or "cycle_block")
        minimum_value = int(method_defaults.get("minimum_cycle_count", 1))
    elif "minimum_checkpoint_count" in method_defaults:
        field_name = str(method_defaults.get("run_length_field") or "checkpoint_count")
        basis = str(method_defaults.get("default_block_basis") or cadence_mode or "checkpoint_count")
        minimum_value = int(method_defaults.get("minimum_checkpoint_count", 1))
    else:
        field_name = str(method_defaults.get("run_length_field") or "block_count")
        basis = str(method_defaults.get("default_block_basis") or cadence_mode or "block_count")
        minimum_value = int(method_defaults.get("minimum_block_count", 1))

    requested_value = int(requested_run_length)
    resolved_value = max(requested_value, minimum_value)
    return {
        "field_name": field_name,
        "basis": basis,
        "minimum_value": minimum_value,
        "requested_value": requested_value,
        "resolved_value": resolved_value,
    }


def _build_campaign_framework_markdown(campaign_framework: dict[str, Any]) -> list[str]:
    if not campaign_framework:
        return []

    lines = [
        "### Campaign Framework",
        str(campaign_framework.get("summary") or "Campaign structure guidance is declared in the method registry."),
        "",
        "Design guidance cards:",
        _bullet_lines(list(campaign_framework.get("design_guidance_card_ids", []))),
        "Hard-to-change factors:",
        _bullet_lines(list(campaign_framework.get("hard_to_change_factors", []))),
        "Tailorable factors after review:",
        _bullet_lines(list(campaign_framework.get("tailorable_factors", []))),
        "Recommended campaign sequence:",
        _bullet_lines(list(campaign_framework.get("recommended_sequence", []))),
        "Default breakpoint examples:",
        _bullet_lines(list(campaign_framework.get("default_breakpoint_examples", []))),
        "Stop-criteria options:",
        _bullet_lines(list(campaign_framework.get("stop_criteria_options", []))),
    ]

    replicate_guidance = str(campaign_framework.get("replicate_guidance") or "").strip()
    if replicate_guidance:
        lines.extend(["Replicate guidance:", f"- {replicate_guidance}"])

    return lines


def _format_reference_temperature(reference_temperature: dict[str, Any]) -> str | None:
    if not isinstance(reference_temperature, dict) or not reference_temperature:
        return None

    nominal = reference_temperature.get("nominal")
    if nominal is None:
        return None

    if isinstance(nominal, (int, float)):
        line = f"{float(nominal):.1f} C"
    else:
        line = str(nominal)

    tolerance_c = reference_temperature.get("tolerance_c")
    if isinstance(tolerance_c, (int, float)):
        line += f" +/- {float(tolerance_c):.1f} C"

    pre_checkpoint_hold_hours = reference_temperature.get("pre_checkpoint_hold_hours")
    if isinstance(pre_checkpoint_hold_hours, (int, float)):
        line += f". Pre-checkpoint hold: {float(pre_checkpoint_hold_hours):.1f} h"

    pre_checkpoint_hold = reference_temperature.get("pre_checkpoint_hold")
    if isinstance(pre_checkpoint_hold, dict) and pre_checkpoint_hold:
        hold_parts: list[str] = []
        hold_mode = str(pre_checkpoint_hold.get("mode") or "").strip()
        if hold_mode:
            hold_parts.append(hold_mode)
        typical_hours = pre_checkpoint_hold.get("typical_hours")
        if isinstance(typical_hours, (int, float)):
            hold_parts.append(f"typical {float(typical_hours):.1f} h")
        hold_note = str(pre_checkpoint_hold.get("note") or "").strip()
        if hold_note:
            hold_parts.append(hold_note)
        if hold_parts:
            line += f". Pre-checkpoint hold: {'; '.join(hold_parts)}"

    source_basis = str(reference_temperature.get("source_basis") or "").strip()
    if source_basis:
        line += f". Basis: {source_basis}"

    value_role = str(reference_temperature.get("value_role") or "").strip()
    if value_role:
        line += f". Role: {value_role}"

    review_note = str(reference_temperature.get("review_note") or "").strip()
    if review_note:
        line += f". {review_note}"

    return line


def _build_lab_pretest_guidance_markdown(
    *,
    global_defaults: dict[str, Any],
    thermocouple_guidance: dict[str, Any] | None,
    objective_guidance: dict[str, Any] | None,
    rpt_playbook: dict[str, Any] | None,
) -> list[str]:
    if not global_defaults and not thermocouple_guidance and not objective_guidance and not rpt_playbook:
        return []

    lines = ["### Lab Pretest Guidance"]

    reference_temperature_c = global_defaults.get("reference_temperature_c")
    if isinstance(reference_temperature_c, (int, float)):
        lines.append(f"- Default lab reference temperature: {float(reference_temperature_c):.1f} C")

    surface_temperature_abort_c = global_defaults.get("surface_temperature_abort_c")
    if isinstance(surface_temperature_abort_c, (int, float)):
        lines.append(
            f"- Default cell-surface abort threshold: {float(surface_temperature_abort_c):.1f} C"
        )

    cv_termination_rule = global_defaults.get("default_cv_termination_rule", {})
    terminate_when_any = list(cv_termination_rule.get("terminate_when_any", []))
    if terminate_when_any:
        lines.append(
            "- Default CV termination: "
            + "; ".join(str(item) for item in terminate_when_any)
            + "; whichever occurs first."
        )

    chamber_rule = global_defaults.get("environmental_chamber_required_outside_reference_window", {})
    if chamber_rule:
        nominal = chamber_rule.get("nominal_temperature_c", 25)
        tolerance_c = chamber_rule.get("tolerance_c", 2)
        lines.append(
            f"- Environmental chamber required for tests outside {nominal} +/- {tolerance_c} C"
        )

    if thermocouple_guidance and thermocouple_guidance.get("placement_text"):
        lines.append(
            f"- Default thermocouple placement: {thermocouple_guidance['placement_text']}"
        )

    if objective_guidance:
        minimum_modules = list(objective_guidance.get("minimum_modules", []))
        optional_modules = list(objective_guidance.get("optional_modules", []))
        lines.extend(
            [
                "Minimum objective package:",
                _bullet_lines(minimum_modules),
            ]
        )
        if optional_modules:
            lines.extend(["Optional objective modules:", _bullet_lines(optional_modules)])

    if rpt_playbook:
        lines.extend(
            [
                "Lab RPT playbook:",
                "Baseline RPT:",
                _bullet_lines(list(rpt_playbook.get("baseline_rpt", []))),
                "Intermediate RPT:",
                _bullet_lines(list(rpt_playbook.get("intermediate_rpt", []))),
                "End-of-life RPT:",
                _bullet_lines(list(rpt_playbook.get("end_of_life_rpt", []))),
            ]
        )
    return lines


def _build_decision_graph_semantics_markdown(
    *,
    relation_classes: dict[str, Any] | None,
    authority_and_precedence: dict[str, Any] | None,
    requirement_strength_levels: list[str] | None,
    conflict_representation: dict[str, Any] | None,
) -> list[str]:
    if (
        not relation_classes
        and not authority_and_precedence
        and not requirement_strength_levels
        and not conflict_representation
    ):
        return []

    lines = ["### Decision Graph Semantics"]
    if relation_classes:
        lines.extend(
            [
                "Relation classes:",
                _bullet_lines(
                    [
                        f"{relation_name}: {str(details.get('summary') or '').strip()}"
                        for relation_name, details in relation_classes.items()
                        if isinstance(details, dict)
                    ]
                ),
            ]
        )

    principles = list((authority_and_precedence or {}).get("principles", []))
    if principles:
        lines.extend(["Authority and precedence:", _bullet_lines(principles)])

    if requirement_strength_levels:
        lines.append(
            "Requirement strength levels: "
            + ", ".join(str(item) for item in requirement_strength_levels)
        )

    minimum_fields = list((conflict_representation or {}).get("minimum_fields", []))
    if minimum_fields:
        lines.extend(["Conflict representation fields:", _bullet_lines(minimum_fields)])

    return lines


def _format_step_bundle(step_bundle: list[dict[str, Any]] | None) -> str:
    if not step_bundle:
        return "not declared"

    rendered_steps: list[str] = []
    for step in step_bundle:
        if not isinstance(step, dict):
            continue

        order = step.get("order", "?")
        action = str(step.get("action") or "step").replace("_", " ")
        details = str(step.get("details") or "").strip()
        summary = f"{order}. {action}"
        if details:
            summary += f" - {details}"

        qualifiers: list[str] = []
        method_id = str(step.get("method_id") or "").strip()
        if method_id:
            qualifiers.append(f"method={method_id}")
        bundle_id = str(step.get("bundle_id") or "").strip()
        if bundle_id:
            qualifiers.append(f"bundle={bundle_id}")
        extension_id = str(step.get("extension_id") or "").strip()
        if extension_id:
            qualifiers.append(f"extension={extension_id}")
        strictness = str(step.get("strictness") or "").strip()
        if strictness:
            qualifiers.append(f"strictness={strictness}")

        if qualifiers:
            summary += f" ({'; '.join(qualifiers)})"

        rendered_steps.append(summary)

    return "; ".join(rendered_steps) if rendered_steps else "not declared"


def _build_core_rpt_set_markdown(core_rpt_set: dict[str, Any]) -> list[str]:
    if not isinstance(core_rpt_set, dict) or not core_rpt_set:
        return []

    source_method_ids = list(core_rpt_set.get("source_method_ids", []))
    mandatory_at = list(core_rpt_set.get("mandatory_at", []))
    target_observables = list(core_rpt_set.get("target_observables", []))
    derived_observables = list(core_rpt_set.get("derived_observables", []))
    literature_cards = list(core_rpt_set.get("complementary_literature_card_ids", []))
    lines = [
        "Core RPT set:",
        f"- Bundle id: {core_rpt_set.get('bundle_id', 'not declared')}",
        f"- Label: {core_rpt_set.get('label', 'Unnamed core RPT set')}",
        f"- Summary: {core_rpt_set.get('summary', 'No summary declared.')}",
        f"- Source methods: {', '.join(source_method_ids) or 'not declared'}",
        f"- Mandatory at: {', '.join(mandatory_at) or 'not declared'}",
        "Target observables:",
        _bullet_lines(target_observables),
        f"- Complementary literature cards: {', '.join(literature_cards) or 'none'}",
        f"- Step bundle: {_format_step_bundle(core_rpt_set.get('step_bundle'))}",
    ]
    if derived_observables:
        lines.extend(["Derived observables:", _bullet_lines(derived_observables)])
    return lines


def _build_checkpoint_extension_markdown(
    checkpoint_extension_tests: list[dict[str, Any]] | None,
) -> list[str]:
    if not checkpoint_extension_tests:
        return []

    lines = ["Checkpoint extension tests:"]
    for extension in checkpoint_extension_tests:
        if not isinstance(extension, dict):
            continue
        method_ids = ", ".join(extension.get("method_ids", [])) or "not declared"
        trigger_at = ", ".join(extension.get("trigger_at", [])) or "not declared"
        lines.append(
            "- {label}: {summary} Methods: {methods}. Trigger at: {trigger_at}. Selection rule: {selection_rule}. Step bundle: {step_bundle}".format(
                label=extension.get("label", extension.get("extension_id", "Unnamed extension")),
                summary=extension.get("summary", "No summary declared."),
                methods=method_ids,
                trigger_at=trigger_at,
                selection_rule=extension.get("selection_rule", "not declared"),
                step_bundle=_format_step_bundle(extension.get("step_bundle")),
            )
        )

    return lines


def _build_checkpoint_template_markdown(
    checkpoint_templates: list[dict[str, Any]] | None,
) -> list[str]:
    if not checkpoint_templates:
        return []

    lines = ["Checkpoint templates:"]
    for template in checkpoint_templates:
        if not isinstance(template, dict):
            continue
        bundle_ids = ", ".join(template.get("bundle_ids", [])) or "none"
        extension_ids = ", ".join(template.get("extension_ids", [])) or "none"
        lines.append(
            "- {label}: applies at {applies_at}. Trigger: {trigger_rule}. Bundles: {bundle_ids}. Extensions: {extension_ids}. Step bundle: {step_bundle}".format(
                label=template.get("label", template.get("template_id", "Unnamed checkpoint template")),
                applies_at=template.get("applies_at", "not declared"),
                trigger_rule=template.get("trigger_rule", "not declared"),
                bundle_ids=bundle_ids,
                extension_ids=extension_ids,
                step_bundle=_format_step_bundle(template.get("step_bundle")),
            )
        )

    return lines


def _build_reference_check_policy_markdown(reference_check_policy: dict[str, Any]) -> list[str]:
    if not reference_check_policy:
        return []

    rpt_blocks = reference_check_policy.get("rpt_blocks", [])
    rpt_lines: list[str] = []
    for block in rpt_blocks:
        if not isinstance(block, dict):
            continue
        source_method_ids = ", ".join(block.get("source_method_ids", [])) or "not declared"
        mandatory_at = ", ".join(block.get("mandatory_at", [])) or "not declared"
        literature_cards = ", ".join(block.get("complementary_literature_card_ids", [])) or "none"
        rpt_lines.append(
            "- {label}: {purpose} Source methods: {source_methods}. Mandatory at: {mandatory_at}. "
            "Strictness: {strictness}. Complementary literature cards: {literature_cards}.".format(
                label=block.get("label", block.get("rpt_id", "Unnamed RPT block")),
                purpose=block.get("purpose", "No purpose declared."),
                source_methods=source_method_ids,
                mandatory_at=mandatory_at,
                strictness=block.get("strictness", "not declared"),
                literature_cards=literature_cards,
            )
        )

    baseline_required = "yes" if reference_check_policy.get("baseline_required") else "no"
    intermediate_required = (
        "yes" if reference_check_policy.get("intermediate_checkups_required") else "no"
    )
    reference_temperature_line = _format_reference_temperature(
        reference_check_policy.get("reference_temperature_c", {})
    )
    rpt_cadence_mode = reference_check_policy.get("rpt_cadence_mode", {})
    cadence_default = str(rpt_cadence_mode.get("default_mode") or "not declared")
    cadence_supported = list(rpt_cadence_mode.get("supported_modes", []))
    cadence_selection_rule = str(rpt_cadence_mode.get("selection_rule") or "").strip()
    condition_based_trigger = rpt_cadence_mode.get("condition_based_trigger", {})
    trigger_parts: list[str] = []
    if isinstance(condition_based_trigger, dict) and condition_based_trigger:
        metric = str(condition_based_trigger.get("metric") or "").strip()
        if metric:
            trigger_parts.append(f"metric={metric}")
        example_threshold_percent = condition_based_trigger.get("example_threshold_percent")
        if isinstance(example_threshold_percent, (int, float)):
            trigger_parts.append(f"example threshold={float(example_threshold_percent):.1f}%")
        max_loss_between_checkups_percent = condition_based_trigger.get(
            "max_loss_between_checkups_percent"
        )
        if isinstance(max_loss_between_checkups_percent, (int, float)):
            trigger_parts.append(
                f"max loss between check-ups={float(max_loss_between_checkups_percent):.1f}%"
            )
        action = str(condition_based_trigger.get("action") or "").strip()
        if action:
            trigger_parts.append(f"action={action}")
        note = str(condition_based_trigger.get("note") or "").strip()
        if note:
            trigger_parts.append(note)

    lines = [
        "### Reference Check Policy",
        str(
            reference_check_policy.get("summary")
            or "Reference-performance check-up guidance is declared in the method registry."
        ),
        "",
        f"- Baseline required: {baseline_required}",
        f"- Intermediate check-ups required: {intermediate_required}",
        "Timing basis options:",
        _bullet_lines(list(reference_check_policy.get("timing_basis_options", []))),
        "Default breakpoint examples:",
        _bullet_lines(list(reference_check_policy.get("default_breakpoint_examples", []))),
    ]

    if reference_temperature_line:
        lines.append(f"- Reference temperature: {reference_temperature_line}")

    if isinstance(rpt_cadence_mode, dict) and rpt_cadence_mode:
        lines.extend(
            [
                "RPT cadence mode:",
                f"- Default mode: {cadence_default}",
                f"- Supported modes: {', '.join(cadence_supported) or 'not declared'}",
            ]
        )
        if cadence_selection_rule:
            lines.append(f"- Selection rule: {cadence_selection_rule}")
        if trigger_parts:
            lines.append(f"- Condition-based trigger: {'; '.join(trigger_parts)}")

    lines.extend(_build_core_rpt_set_markdown(reference_check_policy.get("core_rpt_set", {})))
    lines.extend(
        _build_checkpoint_extension_markdown(
            reference_check_policy.get("checkpoint_extension_tests", [])
        )
    )
    lines.extend(
        _build_checkpoint_template_markdown(reference_check_policy.get("checkpoint_templates", []))
    )

    lines.extend(
        [
        "RPT blocks:",
        "\n".join(rpt_lines) or "- None declared.",
        ]
    )

    return lines


def _build_deviation_policy(
    *,
    method: dict[str, Any],
    protocol_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    strict_reference_policy = dict(method.get("strict_reference_policy", {}))
    review_items: list[str] = []

    for step in protocol_steps:
        step_name = str(step.get("name") or "Unnamed step")
        step_strictness = str(step.get("step_strictness") or "unknown")
        if not bool(step.get("source_backed", False)):
            review_items.append(
                f"{step_name}: planner completion or non-source-backed detail must be reviewed before release."
            )
        elif step_strictness in {"tailorable_after_review", "framework_after_review"}:
            review_items.append(
                f"{step_name}: the source reference allows tailoring here, but the chosen narrowing still needs review."
            )

        deviation_note = str(step.get("deviation_note") or "").strip()
        if deviation_note:
            review_items.append(f"{step_name}: {deviation_note}")

    unique_review_items: list[str] = []
    seen: set[str] = set()
    for item in review_items:
        if item in seen:
            continue
        seen.add(item)
        unique_review_items.append(item)

    return {
        "mode": strict_reference_policy.get("mode", "draft_reference"),
        "summary": strict_reference_policy.get(
            "summary",
            "Use the structured method reference as the primary planning reference and surface any deviations for review.",
        ),
        "locked_planning_fields": list(strict_reference_policy.get("locked_planning_fields", [])),
        "tailorable_fields": list(strict_reference_policy.get("tailorable_fields", [])),
        "review_required": bool(strict_reference_policy.get("deviation_review_required", False)),
        "deviation_review_items": unique_review_items,
    }


def _classify_step_provenance(step: dict[str, Any]) -> str:
    if not bool(step.get("source_backed", False)):
        return "planner_completion"

    strictness = str(step.get("step_strictness") or "").strip()
    if strictness == "core_handbook_locked":
        return "handbook_locked"
    if strictness in {"tailorable_after_review", "framework_after_review"}:
        return "handbook_tailorable_after_review"
    return "source_backed_other"


def _build_step_provenance_summary(
    protocol_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    steps: list[dict[str, Any]] = []

    for step in protocol_steps:
        provenance_class = _classify_step_provenance(step)
        counts[provenance_class] = counts.get(provenance_class, 0) + 1
        steps.append(
            {
                "order": step.get("order"),
                "name": step.get("name"),
                "provenance_class": provenance_class,
                "source_backed": bool(step.get("source_backed", False)),
                "step_strictness": step.get("step_strictness"),
                "evidence_card_id": step.get("evidence_card_id"),
                "has_citation": bool(step.get("citation")),
            }
        )

    return {
        "counts": counts,
        "steps": steps,
        "contains_non_source_backed_steps": counts.get("planner_completion", 0) > 0,
    }


def _display_step_strictness_label(strictness: str) -> str:
    mapping = {
        "core_handbook_locked": "core_method_locked",
        "tailorable_after_review": "tailorable_after_review",
        "framework_after_review": "framework_after_review",
        "planner_completion": "planner_completion",
    }
    return mapping.get(strictness, strictness or "unknown")


def _sanitize_user_facing_method_text(value: str) -> str:
    sanitized = value
    replacements = [
        ("Core Handbook Reference", "Core Method Reference"),
        ("Strict Handbook Reference Mode", "Strict Method Reference Mode"),
        ("Handbook Evidence Cards", "Method Evidence Cards"),
        ("Handbook Summary", "Method Summary"),
        ("Core handbook citation", "Core method citation"),
        ("handbook chapter", "source reference"),
        ("handbook method", "structured method reference"),
        ("handbook example defaults", "source-example defaults"),
        ("handbook source-example", "source-example"),
        ("handbook-backed", "source-backed"),
        ("handbook allows tailoring here", "the source reference allows tailoring here"),
        ("Use the handbook as", "Use the source reference as"),
        ("Use the handbook chapter as", "Use the source reference as"),
        ("Treat the handbook", "Treat the source reference"),
    ]
    for old, new in replacements:
        sanitized = sanitized.replace(old, new)
    return sanitized


def _append_answer_reference(
    references: list[dict[str, Any]],
    *,
    key: str,
    source_type: str,
    reference_text: str,
    preferred_for: str,
    source_id: str | None = None,
    reference_type: str | None = None,
    title: str | None = None,
    visibility_note: str | None = None,
) -> None:
    if not reference_text.strip():
        return

    normalized_reference_type = reference_type or (
        "public"
        if source_type == "method_handbook"
        else "user_supplied"
        if source_type in {"uploaded_cell_datasheet_candidate", "imported_cell_record"}
        else "built_in_guidance"
    )
    citation_number = len(references) + 1
    references.append(
        {
            "reference_key": key,
            "citation_number": citation_number,
            "citation_token": f"[{citation_number}]",
            "source_type": source_type,
            "reference_type": normalized_reference_type,
            "source_id": source_id,
            "preferred_for": preferred_for,
            "scope_of_use": preferred_for,
            "title": title or key.replace("_", " ").title(),
            "visibility_note": visibility_note
            or (
                "Public source or method chapter."
                if normalized_reference_type == "public"
                else "User-provided or user-selected source record."
                if normalized_reference_type == "user_supplied"
                else "Built-in system guidance or governed local knowledge."
            ),
            "reference_text": reference_text.strip(),
        }
    )


def _rule_reference_identifier(rule: dict[str, Any]) -> str | None:
    identifier = (
        str(rule.get("source_asset_id") or "").strip()
        or str(rule.get("id") or "").strip()
    )
    return identifier or None


def _sanitize_reference_title(title: str, fallback: str) -> str:
    raw_title = str(title or "").strip()
    if not raw_title:
        return fallback

    raw_title = re.sub(r"\s*\(([A-Za-z0-9._-]{12,})\)\s*$", "", raw_title).strip()
    raw_title = re.sub(
        r"\s*\(([A-Za-z0-9._-]*(?:datasheet|rule|model|asset|profile)[A-Za-z0-9._-]*)\)\s*$",
        "",
        raw_title,
        flags=re.IGNORECASE,
    ).strip()
    return raw_title or fallback


def _build_internal_guidance_reference_text(
    category: str,
    summary: str,
) -> str:
    category_text = str(category or "").strip() or "Internal guidance"
    summary_text = str(summary or "").strip()
    if not summary_text:
        return f"{category_text}."
    return f"{category_text}. {summary_text}"


def _normalize_reference_body_for_bibliography(text: str) -> str:
    normalized = " ".join(str(text or "").strip().split())
    normalized = re.sub(r"^\[[A-Za-z0-9._-]+\]\s*", "", normalized).strip()
    return normalized


def _build_bibliography_entry(reference: dict[str, Any]) -> str:
    citation_token = str(reference.get("citation_token") or "[?]").strip() or "[?]"
    title = str(reference.get("title") or reference.get("reference_key") or "Reference").strip()
    reference_type = str(reference.get("reference_type") or "built_in_guidance").strip()
    reference_text = _normalize_reference_body_for_bibliography(
        str(reference.get("reference_text") or "")
    )

    if reference_type == "public":
        body = reference_text or f'"{title}."'
    elif reference_type == "user_supplied":
        body = (
            f'User-supplied source, "{title}," {reference_text}'
            if reference_text
            else f'User-supplied source, "{title}."'
        )
    else:
        body = (
            f'Battery Lab Assistant, "{title}," {reference_text}'
            if reference_text
            else f'Battery Lab Assistant, "{title}."'
        )

    body = body.strip()
    if body and not body.endswith("."):
        body = f"{body}."
    return f"{citation_token} {body}"


def build_grouped_reference_markdown(
    answer_references: list[dict[str, Any]],
    *,
    include_section_heading: bool = True,
) -> str:
    if not answer_references:
        return ""

    lines: list[str] = ["## References"] if include_section_heading else []
    if lines:
        lines.append("")
    lines.extend(_build_bibliography_entry(reference) for reference in answer_references)
    return "\n".join(lines).strip()


def _build_answer_references(
    *,
    method_source: dict[str, Any] | None,
    objective_template: dict[str, Any] | None,
    chemistry_profile: dict[str, Any] | None,
    selected_cell_reference: dict[str, Any] | None,
    equipment_rule: dict[str, Any],
    thermal_chamber_rule: dict[str, Any] | None,
    include_pretest_guidance: bool = False,
    include_decision_relation_model: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    references: list[dict[str, Any]] = []

    if method_source is not None:
        _append_answer_reference(
            references,
            key="primary_method_reference",
            source_type="method_handbook",
            source_id=str(method_source.get("source_id") or "").strip() or None,
            preferred_for="step-level protocol structure and source-backed method statements",
            reference_type="public",
            title=_sanitize_reference_title(
                str(method_source.get("source_title") or "Method reference").strip(),
                "Method reference",
            ),
            visibility_note="Public structured method reference.",
            reference_text=str(
                method_source.get("answer_reference_markdown")
                or method_source.get("linked_reference_markdown")
                or ""
            ),
        )

    if objective_template is not None:
        _append_answer_reference(
            references,
            key="objective_template",
            source_type="local_objective_template",
            source_id=str(objective_template.get("id") or "").strip() or None,
            preferred_for="objective-level planning intent and report focus from the local registry",
            reference_type="built_in_guidance",
            title=_sanitize_reference_title(
                f"Objective template - {objective_template.get('label', 'Unknown objective')}",
                "Objective template",
            ),
            visibility_note="Built-in governed objective template.",
            reference_text=(
                _build_internal_guidance_reference_text(
                    "Internal planning template",
                    f"{objective_template.get('label', 'Unknown objective')}.",
                )
            ),
        )

    if chemistry_profile is not None:
        _append_answer_reference(
            references,
            key="chemistry_profile",
            source_type="local_registry",
            source_id=str(chemistry_profile.get("id") or "").strip() or None,
            preferred_for="chemistry-backed voltage, rate, and temperature limits from the local registry",
            reference_type="built_in_guidance",
            title=_sanitize_reference_title(
                f"Chemistry registry - {chemistry_profile.get('label', 'Unknown chemistry')}",
                "Chemistry registry",
            ),
            visibility_note="Built-in governed chemistry registry entry.",
            reference_text=(
                _build_internal_guidance_reference_text(
                    "Internal chemistry constraints",
                    f"{chemistry_profile.get('label', 'Unknown chemistry')} cells.",
                )
            ),
        )

    if selected_cell_reference is not None:
        selected_cell_source_kind = selected_cell_reference.get("source_kind")
        selected_cell_source_document = selected_cell_reference.get("source_document", {})
        if selected_cell_source_kind == "uploaded_cell_datasheet_candidate":
            reference_text = (
                "Uploaded cell datasheet: "
                f"{selected_cell_reference.get('display_name') or selected_cell_reference.get('cell_id') or 'unknown cell'}"
            )
            original_filename = selected_cell_source_document.get("original_filename")
            source_details: list[str] = []
            if original_filename:
                source_details.append(f"original file `{original_filename}`")
            if source_details:
                reference_text += " (" + ", ".join(source_details) + ")."
            else:
                reference_text += "."
        else:
            reference_text = (
                "Imported selected cell record: "
                f"{selected_cell_reference.get('display_name') or selected_cell_reference.get('cell_id') or 'unknown cell'}."
            )
        _append_answer_reference(
            references,
            key="selected_cell_reference",
            source_type=(
                "uploaded_cell_datasheet_candidate"
                if selected_cell_source_kind == "uploaded_cell_datasheet_candidate"
                else "imported_cell_record"
            ),
            reference_type="user_supplied",
            title=(
                f"Cell datasheet - {selected_cell_reference.get('display_name') or selected_cell_reference.get('cell_id') or 'unknown cell'}"
                if selected_cell_source_kind == "uploaded_cell_datasheet_candidate"
                else f"Selected cell record - {selected_cell_reference.get('display_name') or selected_cell_reference.get('cell_id') or 'unknown cell'}"
            ),
            visibility_note=(
                "User-supplied datasheet candidate extracted into the thread."
                if selected_cell_source_kind == "uploaded_cell_datasheet_candidate"
                else "User-selected imported cell record carried into planning."
            ),
            source_id=str(selected_cell_reference.get("cell_id") or "").strip() or None,
            preferred_for=(
                "uploaded cell-specific voltage, current, and form-factor constraints from the user-supplied datasheet"
                if selected_cell_source_kind == "uploaded_cell_datasheet_candidate"
                else "selected-cell metadata constraints carried from the imported commercial cell record"
            ),
            reference_text=reference_text,
        )

    equipment_reference_id = _rule_reference_identifier(equipment_rule)
    equipment_reference_text = (
        _build_internal_guidance_reference_text(
            "Internal equipment constraints",
            f"{equipment_rule.get('label', 'Unknown instrument')}.",
        )
    )

    _append_answer_reference(
        references,
        key="equipment_rule",
        source_type="local_equipment_rule",
        reference_type="built_in_guidance",
        title=_sanitize_reference_title(
            str(equipment_rule.get("label") or "Equipment rule").strip(),
            "Equipment rule",
        ),
        visibility_note="Built-in governed equipment rule.",
        source_id=equipment_reference_id,
        preferred_for="instrument limits, channel range, and logging constraints from the local equipment rule",
        reference_text=equipment_reference_text,
    )

    if thermal_chamber_rule is not None:
        thermal_reference_id = _rule_reference_identifier(thermal_chamber_rule)
        thermal_reference_text = (
            _build_internal_guidance_reference_text(
                "Internal thermal chamber constraints",
                f"{thermal_chamber_rule.get('label', 'Unknown chamber')}.",
            )
        )
        _append_answer_reference(
            references,
            key="thermal_chamber_rule",
            source_type="local_thermal_chamber_rule",
            reference_type="built_in_guidance",
            title=_sanitize_reference_title(
                str(thermal_chamber_rule.get("label") or "Thermal chamber rule").strip(),
                "Thermal chamber rule",
            ),
            visibility_note="Built-in governed thermal chamber rule.",
            source_id=thermal_reference_id,
            preferred_for="thermal chamber operating range and hazard-envelope constraints",
            reference_text=thermal_reference_text,
        )

    if include_pretest_guidance:
        _append_answer_reference(
            references,
            key="pretest_guidance",
            source_type="local_pretest_guidance",
            reference_type="built_in_guidance",
            title="Lab pretest guidance",
            visibility_note="Built-in lab SOP and planning guidance.",
            source_id="pretest_assistant_guidance_v0_1",
            preferred_for="lab-wide default SOP constraints, thermocouple placement, and minimum pretest packages",
            reference_text=(
                _build_internal_guidance_reference_text(
                    "Internal lab pretest guidance",
                    "Lab SOP defaults, objective minimum packages, RPT playbook, and approved equipment defaults.",
                )
            ),
        )

    if include_decision_relation_model:
        _append_answer_reference(
            references,
            key="decision_relation_model",
            source_type="local_decision_relation_model",
            reference_type="built_in_guidance",
            title="Planning governance guidance",
            visibility_note="Built-in planning governance guidance.",
            source_id="decision_relation_model_v0_1",
            preferred_for="source precedence and release-review rules for controlled planning",
            reference_text=(
                _build_internal_guidance_reference_text(
                    "Internal planning governance guidance",
                    "Source precedence and release-review rules for controlled planning.",
                )
            ),
        )

    display_prefix = {
        "user_supplied": "U",
        "public": "P",
        "built_in_guidance": "G",
    }
    display_counters: dict[str, int] = {}
    for reference in references:
        reference_type = str(reference.get("reference_type") or "built_in_guidance")
        prefix = display_prefix.get(reference_type, "G")
        display_counters[prefix] = display_counters.get(prefix, 0) + 1
        reference["display_token"] = f"{prefix}{display_counters[prefix]}"

    citation_lookup = {
        reference["reference_key"]: reference["citation_token"]
        for reference in references
    }
    citation_map = {
        "primary_method_reference": citation_lookup.get("primary_method_reference"),
        "objective_template": citation_lookup.get("objective_template"),
        "chemistry_profile": citation_lookup.get("chemistry_profile"),
        "selected_cell_reference": citation_lookup.get("selected_cell_reference"),
        "equipment_rule": citation_lookup.get("equipment_rule"),
        "thermal_chamber_rule": citation_lookup.get("thermal_chamber_rule"),
        "pretest_guidance": citation_lookup.get("pretest_guidance"),
        "decision_relation_model": citation_lookup.get("decision_relation_model"),
        "claim_bindings": {
            "authority_and_precedence": [
                token
                for token in (
                    citation_lookup.get("pretest_guidance"),
                    citation_lookup.get("decision_relation_model"),
                )
                if token
            ],
            "equipment_defaults": [
                token
                for token in (
                    citation_lookup.get("equipment_rule"),
                    citation_lookup.get("thermal_chamber_rule"),
                    citation_lookup.get("pretest_guidance"),
                )
                if token
            ],
            "selected_cell_constraints": [
                token
                for token in (
                    citation_lookup.get("selected_cell_reference"),
                    citation_lookup.get("chemistry_profile"),
                )
                if token
            ],
        },
        "constraint_sources": {
            "registry_chemistry_profile": citation_lookup.get("chemistry_profile"),
            "selected_cell_imported_metadata": citation_lookup.get("selected_cell_reference"),
            "objective_template": citation_lookup.get("objective_template"),
            "equipment_rule": citation_lookup.get("equipment_rule"),
            "thermal_chamber_rule": citation_lookup.get("thermal_chamber_rule"),
            "pretest_assistant_guidance": citation_lookup.get("pretest_guidance"),
            "decision_relation_model": citation_lookup.get("decision_relation_model"),
        },
    }
    references_markdown = build_grouped_reference_markdown(
        references,
        include_section_heading=True,
    )
    return references, citation_map, references_markdown


def _humanize_field_name(field_name: str) -> str:
    text = str(field_name or "").replace("_", " ").strip()
    if not text:
        return "Unspecified field"
    upper_tokens = {"soc", "dcr", "dcir", "rpt", "eol", "cv", "cc"}
    return " ".join(
        token.upper() if token.lower() in upper_tokens else token.capitalize()
        for token in text.split()
    )


def _humanize_table_header(header: str) -> str:
    normalized = str(header or "").strip()
    if not normalized:
        return "Item"

    special_headers = {
        "source_type": "Source",
        "lock_status": "Status",
        "reference_type": "Reference type",
        "primary_response": "Primary response",
        "analysis_unit": "Analysis unit",
        "aggregation_rule": "Aggregation rule",
        "inferential_route": "Inference route",
        "required_report_outputs": "Required report outputs",
        "value/status": "Value / status",
        "required capability": "Required capability",
        "used for": "Used for",
        "critical setting or placement": "Critical setting or placement",
        "definition or rule": "Definition or rule",
        "next_action": "Next action",
    }
    lowered = normalized.lower()
    if lowered in special_headers:
        return special_headers[lowered]
    if "_" in normalized:
        return _humanize_field_name(normalized)
    return normalized


def _markdown_escape(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_markdown_escape(item) for item in value) or "n/a"
    if isinstance(value, dict):
        return ", ".join(f"{key}={_markdown_escape(item)}" for key, item in value.items()) or "n/a"
    text = str(value).replace("\r\n", " ").replace("\n", " ").strip()
    return text.replace("|", "\\|") if text else "n/a"


def _render_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "- None."

    def _humanize_token(value: Any) -> str:
        if value is None:
            return "n/a"
        text = str(value).strip()
        if not text:
            return "n/a"
        mapping = {
            "primary_method_reference": "Primary method reference",
            "selected_cell_reference": "Selected cell reference",
            "pretest_assistant_guidance": "Built-in lab SOP guidance",
            "reference_check_policy": "Reference check policy",
            "registry_review": "Registry review",
            "local_registry": "Built-in chemistry registry",
            "registry_chemistry_profile": "Chemistry registry profile",
            "equipment_rule": "Equipment rule",
            "thermal_chamber_rule": "Thermal chamber rule",
            "requested_conditions": "Requested conditions",
            "controlled_constraints": "Controlled constraints",
            "planner_completion": "Planner completion",
            "user_input_or_method_input": "User input or method input",
            "uploaded_cell_datasheet_candidate": "Uploaded cell datasheet",
            "imported_cell_record": "Imported cell record",
            "user_supplied": "User-supplied",
            "public": "Public",
            "built_in_guidance": "Built-in guidance",
            "fixed": "Fixed",
            "blocked": "Blocked",
            "review_required": "Review required",
            "execution_blocker": "Execution blocker",
            "review_gate": "Review gate",
            "safety_boundary": "Safety boundary",
            "method_core": "Method core",
            "project_choice": "Project choice",
            "statistics_key": "Statistics key",
        }
        if text in mapping:
            return mapping[text]
        return text.replace("_", " ").replace("-", " ").strip().capitalize()

    normalized_headers = [str(header).strip() for header in headers]
    display_headers = [_humanize_table_header(header) for header in normalized_headers]
    header_line = "| " + " | ".join(display_headers) + " |"
    separator_line = "| " + " | ".join("---" for _ in headers) + " |"
    row_lines: list[str] = []
    for row in rows:
        rendered_cells: list[str] = []
        for index, cell in enumerate(row):
            header = normalized_headers[index] if index < len(normalized_headers) else ""
            if header in {"source_type", "lock_status", "type", "severity", "reference_type"}:
                rendered_cells.append(_markdown_escape(_humanize_token(cell)))
            else:
                rendered_cells.append(_markdown_escape(cell))
        row_lines.append("| " + " | ".join(rendered_cells) + " |")
    return "\n".join([header_line, separator_line, *row_lines])


def _simplify_table_rows(rows: list[list[Any]], keep_indices: list[int]) -> list[list[Any]]:
    simplified: list[list[Any]] = []
    for row in rows:
        simplified.append([row[index] if index < len(row) else "" for index in keep_indices])
    return simplified


def _build_release_review_items(
    *,
    grouped_constraint_rows: dict[str, list[list[Any]]],
    pending_confirmation_rows: list[list[Any]],
    warnings: list[str],
) -> list[str]:
    items: list[str] = []

    for row in grouped_constraint_rows.get("Unresolved Hard Constraints", []):
        if not row:
            continue
        label = _markdown_escape(row[0])
        value = _markdown_escape(row[1]) if len(row) > 1 else "n/a"
        note = _markdown_escape(row[4]) if len(row) > 4 and row[4] else ""
        text = f"{label}: {value}"
        if note and note != "n/a":
            text += f". {note}"
        items.append(text)

    for row in pending_confirmation_rows:
        if not row:
            continue
        item = _markdown_escape(row[0])
        reason = _markdown_escape(row[3]) if len(row) > 3 else ""
        next_action = _markdown_escape(row[4]) if len(row) > 4 else ""
        text = item
        if reason and reason != "n/a":
            text += f": {reason}"
        if next_action and next_action != "n/a":
            text += f". Next action: {next_action}"
        items.append(text)

    for warning in warnings:
        warning_text = str(warning).strip()
        if warning_text:
            items.append(warning_text)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def _render_execution_sequence(workflow_rows: list[list[Any]]) -> str:
    if not workflow_rows:
        return "- No execution sequence was generated."

    lines: list[str] = []
    for row in workflow_rows:
        order = row[0] if len(row) > 0 else ""
        step_name = str(row[1] if len(row) > 1 else "Step").strip()
        action = str(row[2] if len(row) > 2 else "").strip()
        note = str(row[5] if len(row) > 5 else "").strip()
        marker = f"{order}." if str(order).strip() else f"{len(lines) + 1}."
        text = action or step_name
        if step_name and action and action.lower() != step_name.lower():
            text = f"{step_name}: {action}"
        if note and note not in {"fixed", "review_required", "blocked"}:
            text += f" ({note})"
        lines.append(f"{marker} {text}")
    return "\n".join(lines)


def _render_output_summary_table(data_outputs: dict[str, list[str]]) -> str:
    rows: list[list[Any]] = []
    category_labels = {
        "raw_data": "Raw data logging",
        "derived_metrics": "Derived outputs",
        "audit_metadata": "Supporting metadata",
    }
    for key, label in category_labels.items():
        items = [str(item).strip() for item in data_outputs.get(key, []) if str(item).strip()]
        if not items:
            continue
        rows.append([label, "; ".join(items)])
    if not rows:
        return "- No outputs were declared."
    return _render_markdown_table(["Output group", "Summary"], rows)


def _chapter_lookup() -> dict[str, dict[str, Any]]:
    return {entry["id"]: entry for entry in load_chapter_index()}


def _resolve_structured_method_id(query: str) -> str | None:
    try:
        return resolve_method_id(query)
    except KeyError:
        return None


def _resolve_chapter_id(query: str) -> str | None:
    key = _normalize_key(query)
    for entry in load_chapter_index():
        if key in {_normalize_key(entry["id"]), _normalize_key(entry["title"])}:
            return entry["id"]
    return None


def resolve_method_or_chapter_id(query: str) -> str:
    structured_id = _resolve_structured_method_id(query)
    if structured_id is not None:
        return structured_id

    chapter_id = _resolve_chapter_id(query)
    if chapter_id is not None:
        return chapter_id

    raise KeyError(f"Unknown test method or chapter: {query}")


def list_method_profiles() -> dict[str, Any]:
    structured_methods = load_structured_methods()
    chapter_index = load_chapter_index()

    return {
        "status": "ok",
        "source_pdf": _display_repo_asset_if_exists(SOURCE_PDF),
        "structured_methods": [
            {
                "id": method_id,
                "label": method["label"],
                "objective_key": method["objective_key"],
                "source_title": method["source_title"],
                "source_pages": method["source_pages"],
                "handbook_source_id": method.get("handbook_source_id"),
                "answer_reference_markdown": (
                    _get_method_handbook_bundle(method_id=method_id, chapter_id=method.get("chapter_id", "")).get("source", {}).get("answer_reference_markdown")
                    if _get_method_handbook_bundle(method_id=method_id, chapter_id=method.get("chapter_id", ""))
                    else None
                ),
                "strict_reference_mode": method.get("strict_reference_policy", {}).get("mode"),
                "campaign_type": method.get("campaign_framework", {}).get("campaign_type"),
                "currently_supported_chemistries": method.get(
                    "currently_supported_chemistries",
                    method.get("supported_chemistries", []),
                ),
                "applicable_chemistry_scope": method.get("applicable_chemistry_scope", []),
                "method_status": method.get("method_status"),
                "execution_readiness": method.get("execution_readiness"),
                "aliases": method.get("aliases", []),
                "ui_renderer": method.get("ui_renderer"),
                "complementary_literature_source_ids": method.get(
                    "complementary_literature_source_ids",
                    [],
                ),
            }
            for method_id, method in structured_methods.items()
        ],
        "chapter_index": [
            {
                "id": entry["id"],
                "title": entry["title"],
                "section": entry.get("section"),
                "start_page": entry["start_page"],
                "end_page": entry["end_page"],
                "level": entry["level"],
            }
            for entry in chapter_index
        ],
    }


def _read_chapter_text(chapter_id: str) -> str | None:
    """Return chapter text from knowledge/summaries/, preferring the synthesised version."""
    from battery_agent.knowledge import load_knowledge_source_index  # local import avoids circular

    source_index = load_knowledge_source_index()
    # Look up by chapter_id or matching stem
    for src in source_index.get("sources", []):
        if src.get("chapter_id") == chapter_id:
            sp = src.get("summary_path")
            if sp:
                p = REPO_ROOT / str(sp)
                if p.exists():
                    return p.read_text(encoding="utf-8")

    # Fallback: try knowledge/summaries/ by filename stem
    fallback = KNOWLEDGE_SUMMARIES_DIR / f"{chapter_id}.md"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")

    return None


def _build_method_markdown(
    method: dict[str, Any],
    raw_text_excerpt: str | None,
    handbook_bundle: dict[str, Any] | None,
) -> str:
    applications = "\n".join(f"- {item}" for item in method.get("applications", []))
    equipment = "\n".join(f"- {item}" for item in method.get("required_equipment", []))
    supported_chemistries = "\n".join(f"- {item}" for item in method.get("supported_chemistries", []))
    required_inputs = "\n".join(f"- {item}" for item in method.get("required_inputs", []))
    conditional_required_inputs = _build_conditional_required_input_lines(
        method.get("conditional_required_inputs", [])
    )
    optional_inputs = "\n".join(f"- {item}" for item in method.get("optional_inputs", []))
    current_support = "\n".join(
        f"- {item}" for item in method.get("currently_supported_chemistries", [])
    )
    applicability_scope = "\n".join(
        f"- {item}" for item in method.get("applicable_chemistry_scope", [])
    )
    outputs = method.get("required_outputs", {})
    graphs = "\n".join(f"- {item}" for item in outputs.get("graphs", []))
    tables = "\n".join(f"- {item}" for item in outputs.get("tables", []))
    notes = "\n".join(f"- {item}" for item in method.get("planner_notes", []))
    source_example_defaults = _build_source_example_default_lines(
        method.get("source_example_defaults", {})
    )
    campaign_framework = method.get("campaign_framework", {})
    reference_check_policy = method.get("reference_check_policy", {})
    handbook_source = handbook_bundle.get("source", {}) if handbook_bundle else {}
    handbook_summary = str(handbook_bundle.get("summary_markdown") or "").strip() if handbook_bundle else ""
    evidence_cards = handbook_bundle.get("evidence_cards", []) if handbook_bundle else []
    evidence_lines = "\n".join(
        f"- {card.get('title')} ({card.get('citation', {}).get('supporting_pages', 'pages unavailable')})"
        for card in evidence_cards
    )
    chapter_file = _resolve_method_reference_file(handbook_source, method.get("chapter_id"))
    strict_reference_policy = method.get("strict_reference_policy", {})
    locked_fields = "\n".join(
        f"- {item}" for item in strict_reference_policy.get("locked_planning_fields", [])
    )
    tailorable_fields = "\n".join(
        f"- {item}" for item in strict_reference_policy.get("tailorable_fields", [])
    )
    complementary_sources = "\n".join(
        f"- {item}" for item in method.get("complementary_literature_source_ids", [])
    )
    source_pages = method.get("source_pages")
    if isinstance(source_pages, list) and source_pages:
        pages_text = f"{source_pages[0]}-{source_pages[-1]}"
    else:
        pages_text = "Not declared"

    sections = [
        f"## {method['label']}",
        "",
        "### Core Method Reference",
        f"- Source id: {handbook_source.get('source_id', method.get('handbook_source_id', 'unknown'))}",
        f"- Citation: {handbook_source.get('answer_reference_markdown', 'Unavailable')}",
        f"- Reference file: {_display_asset_path(chapter_file) or 'unknown'}",
        "",
        "### Strict Method Reference Mode",
        strict_reference_policy.get(
            "summary",
            "Use the source reference as the primary planning reference and surface any deviations for review.",
        ),
        f"- Method status: {method.get('method_status', 'unknown')}",
        f"- Execution readiness: {method.get('execution_readiness', 'unknown')}",
        f"- Human review required: {'yes' if method.get('human_review_required', True) else 'no'}",
        "",
        "Locked planning fields:",
        locked_fields or "- None declared.",
        "Tailorable fields after review:",
        tailorable_fields or "- None declared.",
        "",
        f"- Source reference: {method['source_title']}",
        f"- Pages: {pages_text}",
        f"- Current product chemistry support: {', '.join(method.get('currently_supported_chemistries', [])) or 'Not declared'}",
        f"- UI renderer: {method.get('ui_renderer', 'Not declared')}",
        "",
        "### Intent",
        method.get("intent", ""),
        "",
        "### Applications",
        applications or "- None provided.",
        "",
        "### Required Inputs",
        required_inputs or "- None provided.",
        "",
        "### Conditional Required Inputs",
        conditional_required_inputs,
        "",
        "### Optional Inputs",
        optional_inputs or "- None provided.",
        "",
        "### Required Equipment",
        equipment or "- None provided.",
        "",
        "### Current Chemistry Support",
        current_support or supported_chemistries or "- None provided.",
        "",
        "### Applicability Scope",
        applicability_scope or "- None provided.",
        "",
        "### Expected Outputs",
        "Graphs:",
        graphs or "- None listed.",
        "Tables:",
        tables or "- None listed.",
        "",
        "### Source-Backed Example Values",
        source_example_defaults,
    ]

    campaign_lines = _build_campaign_framework_markdown(campaign_framework)
    if campaign_lines:
        sections.extend(["", *campaign_lines])

    reference_lines = _build_reference_check_policy_markdown(reference_check_policy)
    if reference_lines:
        sections.extend(["", *reference_lines])

    sections.extend(
        [
            "",
            "### Method Evidence Cards",
            evidence_lines or "- None loaded.",
            "",
            "### Complementary Literature Source Ids",
            complementary_sources or "- None declared.",
        ]
    )

    if notes:
        sections.extend(["", "### Planner Notes", notes])

    if handbook_summary:
        sections.extend(["", "### Method Summary", handbook_summary])

    if raw_text_excerpt:
        sections.extend(["", "### Raw PDF Excerpt", raw_text_excerpt.strip()[:2500]])

    return _sanitize_user_facing_method_text("\n".join(sections))


def get_method_payload(method_or_chapter_id: str) -> dict[str, Any]:
    resolved_id = resolve_method_or_chapter_id(method_or_chapter_id)
    structured_methods = load_structured_methods()
    chapter_lookup = _chapter_lookup()

    if resolved_id in structured_methods:
        method = structured_methods[resolved_id]
        chapter_id = str(method.get("chapter_id") or "").strip()
        raw_text = _read_chapter_text(chapter_id)
        raw_text_excerpt = raw_text[:5000] if raw_text else None
        handbook_bundle = _get_method_handbook_bundle(method_id=resolved_id, chapter_id=chapter_id)
        chapter_file = _resolve_method_reference_file(
            handbook_bundle.get("source") if handbook_bundle else None,
            chapter_id,
        )
        return {
            "status": "ok",
            "kind": "structured_method",
            "method_id": resolved_id,
            "source_pdf": _display_repo_asset_if_exists(SOURCE_PDF),
            "chapter_id": chapter_id,
            "chapter_file": chapter_file,
            "raw_text_excerpt": raw_text_excerpt,
            "method_definition": method,
            "structured_method": method,
            "method_source": _sanitize_method_source(handbook_bundle.get("source")) if handbook_bundle else None,
            "method_summary_markdown": handbook_bundle.get("summary_markdown", "") if handbook_bundle else "",
            "method_evidence_cards": handbook_bundle.get("evidence_cards", []) if handbook_bundle else [],
            "strict_reference_policy": method.get("strict_reference_policy", {}),
            "campaign_framework": method.get("campaign_framework", {}),
            "reference_check_policy": method.get("reference_check_policy", {}),
            "currently_supported_chemistries": method.get(
                "currently_supported_chemistries",
                method.get("supported_chemistries", []),
            ),
            "applicable_chemistry_scope": method.get("applicable_chemistry_scope", []),
            "method_status": method.get("method_status"),
            "execution_readiness": method.get("execution_readiness"),
            "human_review_required": method.get("human_review_required", True),
            "input_contract": _build_input_contract_payload(method),
            "complementary_literature_source_ids": method.get(
                "complementary_literature_source_ids",
                [],
            ),
            "ui_markdown": _build_method_markdown(method, raw_text_excerpt, handbook_bundle),
        }

    if resolved_id in chapter_lookup:
        chapter = chapter_lookup[resolved_id]
        raw_text = _read_chapter_text(resolved_id)
        handbook_bundle = _get_method_handbook_bundle(chapter_id=resolved_id)
        chapter_file = _resolve_method_reference_file(
            handbook_bundle.get("source") if handbook_bundle else None,
            resolved_id,
        )
        return {
            "status": "ok",
            "kind": "raw_chapter",
            "chapter": chapter,
            "source_pdf": _display_repo_asset_if_exists(SOURCE_PDF),
            "chapter_file": chapter_file,
            "raw_text_excerpt": raw_text[:5000] if raw_text else None,
            "method_source": _sanitize_method_source(handbook_bundle.get("source")) if handbook_bundle else None,
            "method_summary_markdown": handbook_bundle.get("summary_markdown", "") if handbook_bundle else "",
            "method_evidence_cards": handbook_bundle.get("evidence_cards", []) if handbook_bundle else [],
            "ui_markdown": _sanitize_user_facing_method_text("\n".join(
                [
                    f"## {chapter['title']}",
                    "",
                    f"- Section: {chapter.get('section') or 'Unknown'}",
                    f"- Pages: {chapter['start_page']}-{chapter['end_page']}",
                    (
                        f"- Core method citation: {handbook_bundle.get('source', {}).get('answer_reference_markdown')}"
                        if handbook_bundle
                        else "- Core method citation: unavailable"
                    ),
                    "",
                    "### Raw PDF Excerpt",
                    (raw_text or "No extracted chapter text is available.")[:2500],
                ]
            )),
        }

    raise KeyError(f"Unknown test method or chapter: {method_or_chapter_id}")


def _cap_rate(requested_rate: float, limit: float) -> tuple[float, str | None]:
    applied = min(requested_rate, limit)
    if applied != requested_rate:
        return applied, f"Requested {requested_rate:.2f}C was capped to {applied:.2f}C by the chemistry profile."
    return applied, None


def _cap_rate_by_selected_cell_limit(
    *,
    requested_rate: float,
    nominal_capacity_ah: float | None,
    max_current_a: float | None,
    label: str,
) -> tuple[float, str | None]:
    if nominal_capacity_ah in (None, 0) or max_current_a is None:
        return requested_rate, None

    applied_limit = float(max_current_a) / float(nominal_capacity_ah)
    applied = min(requested_rate, applied_limit)
    if applied != requested_rate:
        return (
            applied,
            f"Requested {requested_rate:.2f}C was capped to {applied:.2f}C by the uploaded/selected cell {label} current limit.",
        )
    return requested_rate, None


def _format_method_steps(
    method: dict[str, Any],
    *,
    charge_c_rate: float,
    discharge_c_rate: float,
    target_temperature_c: float,
    rest_minutes: int,
    charge_voltage_v: float,
    discharge_cutoff_v: float,
    cycle_count: int,
    cv_termination_rule: dict[str, Any] | None = None,
    use_environmental_chamber: bool = False,
    multi_temperature_mode: bool = False,
) -> list[dict[str, Any]]:
    formatted_steps: list[dict[str, Any]] = []
    step_templates = method.get("protocol_template", {}).get("steps", method.get("procedure_steps", []))
    handbook_bundle = _get_method_handbook_bundle(
        method_id=method.get("id"),
        chapter_id=method.get("chapter_id"),
    )
    method_source = handbook_bundle.get("source", {}) if handbook_bundle else {}
    evidence_card_index = _build_method_evidence_card_index(
        handbook_bundle.get("evidence_cards", []) if handbook_bundle else []
    )
    format_args = {
        "charge_c_rate": f"{charge_c_rate:.2f}",
        "discharge_c_rate": f"{discharge_c_rate:.2f}",
        "target_temperature_c": f"{target_temperature_c:.1f}",
        "rest_minutes": rest_minutes,
        "charge_voltage_v": f"{charge_voltage_v:.2f}",
        "discharge_cutoff_v": f"{discharge_cutoff_v:.2f}",
        "cycle_count": cycle_count,
    }
    cv_termination_parts = [
        str(item).strip()
        for item in (cv_termination_rule or {}).get("terminate_when_any", [])
        if str(item).strip()
    ]
    cv_termination_summary = (
        "; ".join(cv_termination_parts) + "; whichever occurs first"
        if cv_termination_parts
        else None
    )

    for index, step in enumerate(step_templates, start=1):
        evidence_card_id = step.get("evidence_card_id")
        evidence_card = (
            evidence_card_index.get(str(evidence_card_id))
            if isinstance(evidence_card_id, str)
            else None
        )
        citation: dict[str, Any] | None = None
        if evidence_card is not None:
            citation = dict(evidence_card.get("citation", {}))
        elif method_source:
            citation = {
                "linked_reference_markdown": method_source.get("linked_reference_markdown"),
                "supporting_pages": (
                    f"pp. {method_source.get('start_page')}-{method_source.get('end_page')}"
                    if method_source.get("start_page") != method_source.get("end_page")
                    else f"p. {method_source.get('start_page')}"
                ),
                "answer_reference_with_pages_markdown": method_source.get(
                    "answer_reference_markdown"
                ),
            }

        rendered_details = step["details"].format(**format_args)
        step_id = step.get("id") or f"{method.get('id', 'method')}_step_{index}"
        if step_id == "climate_chamber_acclimation":
            if use_environmental_chamber:
                rendered_details = (
                    f"Set the chamber to {target_temperature_c:.1f} C and rest for 3 h before the initial full charge."
                )
            else:
                rendered_details = (
                    f"Stabilize the cell at {target_temperature_c:.1f} C in the declared test environment and rest for 3 h before the initial full charge."
                )
        elif step_id == "reference_full_charge" and cv_termination_summary:
            rendered_details = (
                "Charge per datasheet to cut-off voltage and continue CV until the lab SOP termination rule is met "
                f"({cv_termination_summary})."
            )
        elif step_id == "return_to_full_soc":
            repeat_target = (
                "before each additional temperature sweep"
                if multi_temperature_mode
                else "before the SOC staircase"
            )
            if cv_termination_summary:
                rendered_details = (
                    "Recharge with the same CC-CV method "
                    f"{repeat_target}, using the lab SOP CV termination rule ({cv_termination_summary})."
                )
            else:
                rendered_details = f"Recharge with the same CC-CV method {repeat_target}."
        elif step_id == "soc_staircase" and not use_environmental_chamber:
            rendered_details = (
                f"At {target_temperature_c:.1f} C, rest 6 h, then step the cell by 5% DoD (10% SOC) increments with 1 h rests."
            )
        elif step_id == "repeat_across_soc_rate_temperature" and not multi_temperature_mode:
            rendered_details = (
                "Repeat the pulse pair at the selected current rates until 10% SOC. "
                "Add additional temperatures only when the reviewed plan explicitly defines a multi-temperature matrix."
            )
        elif step_id == "slow_recharge_completion" and cv_termination_summary:
            rendered_details = (
                f"Recharge at {charge_c_rate:.2f}C to {charge_voltage_v:.2f} V and complete the CV taper using the lab SOP termination rule "
                f"({cv_termination_summary})."
            )

        formatted_step = {
            "order": index,
            "step_id": step_id,
            "name": step["name"],
            "details": rendered_details,
            "source_backed": step.get("source_backed", True),
            "evidence_card_id": evidence_card_id,
            "step_strictness": step.get(
                "step_strictness",
                "core_handbook_locked" if step.get("source_backed", True) else "planner_completion",
            ),
        }
        formatted_step["provenance_class"] = _classify_step_provenance(formatted_step)
        formatted_step["reference_keys"] = (
            ["primary_method_reference"] if formatted_step["source_backed"] else []
        )
        if citation is not None:
            formatted_step["citation"] = citation
        if evidence_card is not None:
            formatted_step["evidence_title"] = evidence_card.get("title")
        if step.get("deviation_note"):
            formatted_step["deviation_note"] = step["deviation_note"]
        formatted_steps.append(formatted_step)

    return formatted_steps


def render_method_protocol_steps(
    *,
    method: dict[str, Any],
    charge_c_rate: float,
    discharge_c_rate: float,
    target_temperature_c: float,
    rest_minutes: int,
    charge_voltage_v: float,
    discharge_cutoff_v: float,
    cycle_count: int,
) -> list[dict[str, Any]]:
    return _format_method_steps(
        method,
        charge_c_rate=charge_c_rate,
        discharge_c_rate=discharge_c_rate,
        target_temperature_c=target_temperature_c,
        rest_minutes=rest_minutes,
        charge_voltage_v=charge_voltage_v,
        discharge_cutoff_v=discharge_cutoff_v,
        cycle_count=cycle_count,
    )


_METHOD_PARAMETER_LABELS = {
    "pulse_hppc": "DCR/HPPC Parameters",
    "capacity_test": "Reference Capacity Parameters",
    "cycle_life": "Ageing Parameters",
    "calendar_ageing_test": "Ageing Parameters",
    "ageing_drive_cycle": "Ageing Parameters",
    "constant_voltage_ageing": "Ageing Parameters",
}

_AGEING_METHOD_IDS = {
    "cycle_life",
    "calendar_ageing_test",
    "ageing_drive_cycle",
    "constant_voltage_ageing",
}

_PLANNING_INPUT_METADATA: dict[str, dict[str, Any]] = {
    "chemistry": {
        "label": "Chemistry",
        "why_needed": "The simulation preview cannot resolve the governed model context until the chemistry is known.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "chemistry_or_selected_cell": {
        "label": "Chemistry Or Selected Cell",
        "why_needed": "The planner needs either a governed chemistry or a selected cell record before it can lock the protocol constraints.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "time_column": {
        "label": "Time Column",
        "why_needed": "The modeling tool needs the time-series column that represents elapsed test time.",
        "severity": "method_core",
        "input_kind": "text",
        "allowed_units": ["s"],
        "can_use_default": False,
    },
    "current_column": {
        "label": "Current Column",
        "why_needed": "Pulse detection and ECM fitting require the current column from the uploaded table.",
        "severity": "method_core",
        "input_kind": "text",
        "allowed_units": ["A"],
        "can_use_default": False,
    },
    "voltage_column": {
        "label": "Voltage Column",
        "why_needed": "The fitting workflow needs the cell-voltage column from the uploaded table.",
        "severity": "method_core",
        "input_kind": "text",
        "allowed_units": ["V"],
        "can_use_default": False,
    },
    "target_pulse_index": {
        "label": "Target Pulse Index",
        "why_needed": "More than one pulse candidate was detected, so the ECM fit needs the pulse block you want to parameterize.",
        "severity": "project_choice",
        "input_kind": "number",
        "can_use_default": True,
    },
    "current_threshold_a": {
        "label": "Pulse Current Threshold",
        "why_needed": "Pulse detection needs a minimum absolute current threshold to distinguish rests from active pulse segments.",
        "severity": "method_core",
        "input_kind": "number",
        "allowed_units": ["A"],
        "can_use_default": True,
    },
    "instrument": {
        "label": "Instrument",
        "why_needed": "The protocol cannot be finalized until the cycler/channel limits are known.",
        "severity": "safety_boundary",
        "input_kind": "text",
        "can_use_default": False,
    },
    "target_soc": {
        "label": "Target SOC (%)",
        "why_needed": "The storage or hold condition depends on the defined SOC target.",
        "severity": "method_core",
        "input_kind": "number",
        "allowed_units": ["% SOC"],
        "can_use_default": False,
    },
    "checkpoint_interval": {
        "label": "Checkpoint Interval",
        "why_needed": "The checkpoint cadence is needed to lock the reference-test schedule.",
        "severity": "project_choice",
        "input_kind": "text",
        "can_use_default": True,
    },
    "stop_criterion": {
        "label": "Stop Criterion",
        "why_needed": "The ageing or hold plan needs a defined stop rule before release.",
        "severity": "project_choice",
        "input_kind": "text",
        "can_use_default": True,
    },
    "ageing_condition_matrix": {
        "label": "Ageing Condition Matrix",
        "why_needed": "A comparative ageing plan is not executable until each ageing condition is explicitly defined.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "profile_family": {
        "label": "Drive Profile Family",
        "why_needed": "The ageing drive-cycle campaign depends on the selected profile family.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "soc_window": {
        "label": "SOC Window",
        "why_needed": "The stress matrix is not complete until the operating SOC window is defined.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "charge_regime": {
        "label": "Charge Regime",
        "why_needed": "The campaign needs a declared charge regime to define the ageing condition.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "block_basis": {
        "label": "Block Basis",
        "why_needed": "The reference-test cadence and campaign accounting depend on the block basis.",
        "severity": "project_choice",
        "input_kind": "select",
        "options": ["cycle_block", "elapsed_time"],
        "can_use_default": True,
    },
    "cycle_count": {
        "label": "Cycle Count",
        "why_needed": "The requested cycle count defines the active test block or release horizon.",
        "severity": "project_choice",
        "input_kind": "number",
        "can_use_default": True,
    },
    "elapsed_time_block": {
        "label": "Elapsed Time Block",
        "why_needed": "The elapsed-time block is required when the campaign is not cycle-count based.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "target_voltage": {
        "label": "Target Voltage",
        "why_needed": "The constant-voltage hold cannot be defined until the target voltage is set.",
        "severity": "safety_boundary",
        "input_kind": "number",
        "allowed_units": ["V"],
        "can_use_default": False,
    },
    "hold_duration": {
        "label": "Hold Duration",
        "why_needed": "The voltage-hold campaign needs a defined hold duration to be schedulable.",
        "severity": "method_core",
        "input_kind": "text",
        "can_use_default": False,
    },
    "max_continuous_discharge_current_a": {
        "label": "Max Continuous Discharge Current",
        "why_needed": "The pulse amplitude cannot be safely locked until the discharge-current allowance is known.",
        "severity": "safety_boundary",
        "input_kind": "number",
        "allowed_units": ["A"],
        "source_type": "user_supplied",
        "lock_status": "blocked",
        "can_use_default": False,
    },
    "dcir_definition": {
        "label": "DCIR / DCR Definition",
        "why_needed": "A DCIR/DCR plan cannot be released until the resistance definition is locked, including the pulse basis, time basis, SOC coverage, and rest convention.",
        "severity": "method_core",
        "input_kind": "textarea",
        "source_type": "user_supplied",
        "lock_status": "blocked",
        "can_use_default": False,
    },
}


def build_parameter_request_payload(
    *,
    request_id: str,
    method: dict[str, Any],
    release_status: str,
    missing_fields: list[str],
    input_contract: dict[str, Any] | None = None,
    requested_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_example_defaults = (
        dict((input_contract or {}).get("source_example_defaults", {}))
        if isinstance((input_contract or {}).get("source_example_defaults", {}), dict)
        else {}
    )
    requested_conditions = requested_conditions or {}
    ordered_questions: list[dict[str, Any]] = []
    severity_order = {
        "safety_boundary": 0,
        "method_core": 1,
        "statistics_key": 2,
        "project_choice": 3,
    }

    for field_name in list(dict.fromkeys(str(item) for item in missing_fields if str(item).strip())):
        metadata = _PLANNING_INPUT_METADATA.get(field_name, {})
        severity = str(metadata.get("severity") or "method_core")
        ordered_questions.append(
            {
                "key": field_name,
                "label": metadata.get("label") or _humanize_field_name(field_name),
                "why_needed": metadata.get("why_needed")
                or f"{_humanize_field_name(field_name)} is required before release.",
                "severity": severity,
                "input_kind": metadata.get("input_kind") or "text",
                "options": list(metadata.get("options", [])),
                "recommended_value": source_example_defaults.get(field_name),
                "allowed_units": list(metadata.get("allowed_units", [])),
                "source_type": metadata.get("source_type") or "user_input_required",
                "lock_status": metadata.get("lock_status")
                or ("blocked" if severity == "safety_boundary" else "review_required"),
                "can_use_default": bool(metadata.get("can_use_default")),
                "current_value": requested_conditions.get(field_name),
            }
        )

    ordered_questions.sort(
        key=lambda item: (
            severity_order.get(str(item.get("severity") or "method_core"), 99),
            str(item.get("label") or ""),
        )
    )
    return {
        "request_id": request_id,
        "method_id": method.get("id"),
        "method_label": method.get("label"),
        "release_status": release_status,
        "question_order": [question["key"] for question in ordered_questions],
        "remaining_required_count": len(ordered_questions),
        "questions": ordered_questions,
    }


def _source_reference_type(source_type: str) -> str:
    if source_type in {"primary_method_reference", "method_handbook", "public"}:
        return "public"
    if source_type in {"uploaded_cell_datasheet_candidate", "imported_cell_record", "selected_cell_imported_metadata"}:
        return "user_supplied"
    return "built_in_guidance"


def _step_lock_status(step: dict[str, Any]) -> str:
    if not step.get("source_backed", True):
        return "review_required"
    if str(step.get("step_strictness") or "").strip() in {
        "tailorable_after_review",
        "framework_after_review",
    }:
        return "review_required"
    return "fixed"


def _condition_value_lines(condition_rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in condition_rows:
        condition = _markdown_escape(row.get("condition"))
        value = _markdown_escape(row.get("value"))
        lines.append(f"{condition}: {value}")
    return lines


def _build_phase_rows(method_id: str, protocol_steps: list[dict[str, Any]]) -> list[list[Any]]:
    step_names = [str(step.get("name") or "").strip() for step in protocol_steps if str(step.get("name") or "").strip()]
    if method_id == "pulse_hppc":
        return [
            ["Setup and reference charge", "Stabilize the test temperature and return the cell to reference full SOC.", "Selected cell or active test subject", ", ".join(step_names[:2]) or "Reference state"],
            ["SOC staircase and pulse sweep", "Run the SOC staircase and pulse sequence that generate DCR/DCIR metrics.", "Active test subject across the planned SOC ladder", ", ".join(step_names[2:]) or "Pulse traces and resistance metrics"],
        ]
    if method_id in _AGEING_METHOD_IDS:
        return [
            ["Setup and baseline", "Confirm the reference condition and baseline measurements before the stress block.", "Active test cohort or selected subject", ", ".join(step_names[:2]) or "Baseline package"],
            ["Stress block", "Run the ageing or hold condition under the declared operating window.", "Declared condition matrix", ", ".join(step_names[2:4]) or "Ageing block telemetry"],
            ["Checkpoint and close-out", "Run the checkpoint bundle and final stop-rule package.", "Checkpoint cycles or elapsed-time blocks", ", ".join(step_names[4:]) or "Checkpoint and end-of-test outputs"],
        ]
    return [
        ["Setup", "Stabilize temperature, check limits, and prepare the reference state.", "Active test subject", ", ".join(step_names[:2]) or "Set-up and conditioning"],
        ["Main protocol", "Run the structured method sequence at the locked conditions.", "Active test subject", ", ".join(step_names[2:]) or "Primary method outputs"],
    ]


def _build_condition_rows(requested_conditions: dict[str, Any]) -> list[dict[str, Any]]:
    matrix_fields = [
        "temperature_points",
        "temperature_set",
        "temperature_matrix",
        "temperature_sweep",
        "soc_window",
        "profile_family",
        "charge_regime",
        "target_soc",
        "target_voltage",
    ]
    rows: list[dict[str, Any]] = []
    for field_name in matrix_fields:
        value = requested_conditions.get(field_name)
        if not _is_declared_input_present(value):
            continue
        rows.append(
            {
                "condition": _humanize_field_name(field_name),
                "value": value,
                "source_type": "user_input_or_method_input",
                "lock_status": "fixed",
                "note": "",
            }
        )
    return rows


def _build_known_constraint_rows(
    *,
    method_id: str,
    applied_constraints: dict[str, Any],
    constraint_sources: dict[str, str],
    unresolved_registry_constraints: list[str],
    selected_cell_reference: dict[str, Any] | None,
    execution_blockers: list[dict[str, Any]],
) -> list[list[Any]]:
    label_map = {
        "charge_voltage_v": ("Charge Voltage Limit", "V"),
        "discharge_cutoff_v": ("Discharge Cut-off", "V"),
        "selected_cell_nominal_capacity_ah": ("Nominal Capacity", "Ah"),
        "selected_cell_max_continuous_charge_current_a": ("Max Continuous Charge Current", "A"),
        "selected_cell_max_continuous_discharge_current_a": ("Max Continuous Discharge Current", "A"),
        "instrument_max_current_a": ("Instrument Max Current", "A"),
        "instrument_max_voltage_v": ("Instrument Max Voltage", "V"),
        "surface_temperature_abort_c": ("Surface Temperature Abort", "C"),
        "cv_termination_current_a": ("CV Termination Current", "A"),
        "cv_termination_c_rate_fraction": ("CV Termination Fraction", "C fraction"),
        "cv_max_hold_minutes": ("CV Maximum Hold", "min"),
        "lab_reference_temperature_c": ("Reference Temperature", "C"),
        "thermal_chamber_temperature_range_c": ("Thermal Chamber Temperature Range", "C"),
        "thermal_chamber_operating_ambient_range_c": ("Thermal Chamber Ambient Range", "C"),
    }
    critical_missing = {
        blocker.get("item")
        for blocker in execution_blockers
        if blocker.get("item")
    }
    rows: list[list[Any]] = []
    for key, (label, unit) in label_map.items():
        if key not in applied_constraints and key not in constraint_sources:
            continue
        value = applied_constraints.get(key)
        source_type = constraint_sources.get(key, "built_in_guidance")
        lock_status = "fixed"
        note = unit
        if value is None:
            lock_status = "blocked" if key in critical_missing else "review_required"
            note = "Missing in the active planning payload."
        rows.append([label, f"{_markdown_escape(value)}{f' {unit}' if value is not None and unit else ''}", source_type, lock_status, note])

    if selected_cell_reference is not None and method_id == "pulse_hppc":
        discharge_rating = selected_cell_reference.get("max_continuous_discharge_current_a")
        if discharge_rating is None:
            rows.append(
                [
                    "Selected Cell Discharge Allowance",
                    "missing",
                    selected_cell_reference.get("source_kind", "user_supplied"),
                    "blocked",
                    "Pulse amplitude cannot be locked until the discharge-current allowance is provided.",
                ]
            )

    if unresolved_registry_constraints:
        unresolved_text = "; ".join(
            str(item).strip() for item in unresolved_registry_constraints if str(item).strip()
        )
        rows.append(
            [
                "Registry Unresolved Constraints",
                unresolved_text,
                "registry_review",
                "review_required",
                "Carry these items into release review if they affect interpretation.",
            ]
        )
    return rows


def _build_selected_cell_summary_rows(
    selected_cell_reference: dict[str, Any] | None,
) -> list[list[Any]]:
    if not isinstance(selected_cell_reference, dict) or not selected_cell_reference:
        return []

    source_document = (
        selected_cell_reference.get("source_document")
        if isinstance(selected_cell_reference.get("source_document"), dict)
        else {}
    )
    rows = [
        ["Display name", selected_cell_reference.get("display_name"), "selected_cell_reference", "fixed", ""],
        ["Manufacturer", selected_cell_reference.get("manufacturer"), "selected_cell_reference", "fixed", ""],
        ["Model / cell id", selected_cell_reference.get("cell_id") or selected_cell_reference.get("display_name"), "selected_cell_reference", "fixed", ""],
        ["Chemistry hint", selected_cell_reference.get("chemistry_hint"), "selected_cell_reference", "review_required", ""],
        ["Form factor", selected_cell_reference.get("form_factor"), "selected_cell_reference", "fixed", ""],
        ["Nominal capacity", f"{selected_cell_reference.get('nominal_capacity_ah')} Ah" if selected_cell_reference.get("nominal_capacity_ah") is not None else None, "selected_cell_reference", "fixed", ""],
        ["Nominal voltage", f"{selected_cell_reference.get('nominal_voltage_v')} V" if selected_cell_reference.get("nominal_voltage_v") is not None else None, "selected_cell_reference", "fixed", ""],
        ["Charge voltage limit", f"{selected_cell_reference.get('charge_voltage_v')} V" if selected_cell_reference.get("charge_voltage_v") is not None else None, "selected_cell_reference", "fixed", ""],
        ["Discharge cutoff", f"{selected_cell_reference.get('discharge_cutoff_v')} V" if selected_cell_reference.get("discharge_cutoff_v") is not None else None, "selected_cell_reference", "fixed", ""],
        ["Max continuous charge current", f"{selected_cell_reference.get('max_continuous_charge_current_a')} A" if selected_cell_reference.get("max_continuous_charge_current_a") is not None else None, "selected_cell_reference", "fixed", ""],
        ["Max continuous discharge current", f"{selected_cell_reference.get('max_continuous_discharge_current_a')} A" if selected_cell_reference.get("max_continuous_discharge_current_a") is not None else None, "selected_cell_reference", "fixed", ""],
        ["Mass", f"{selected_cell_reference.get('mass_g')} g" if selected_cell_reference.get("mass_g") is not None else None, "selected_cell_reference", "review_required", ""],
        ["Source kind", selected_cell_reference.get("source_kind"), "selected_cell_reference", "fixed", ""],
        ["Original filename", source_document.get("original_filename"), "selected_cell_reference", "review_required", ""],
    ]
    return [row for row in rows if row[1] not in (None, "", "unknown")]


def _build_equipment_setup_rows(
    *,
    equipment_rule: dict[str, Any],
    thermal_chamber_rule: dict[str, Any] | None,
    thermocouple_guidance: dict[str, Any],
    target_temperature_c: float,
) -> list[list[Any]]:
    rows = [
        [
            equipment_rule.get("label", "Unknown instrument"),
            f"Up to {_markdown_escape(equipment_rule.get('max_current_a'))} A / {_markdown_escape(equipment_rule.get('max_voltage_v'))} V",
            "Protocol execution and logging",
            "Use the declared channel limits and sampling capability for release planning.",
            "equipment_rule",
            "fixed",
        ],
        [
            "Thermocouple",
            thermocouple_guidance.get("placement_text") or "Attach per lab SOP",
            "Surface temperature monitoring",
            thermocouple_guidance.get("placement_note") or "Use the governed placement guidance for the active form factor.",
            "pretest_assistant_guidance",
            "fixed",
        ],
    ]
    if thermal_chamber_rule is not None:
        rows.append(
            [
                thermal_chamber_rule.get("label", "Thermal chamber"),
                _markdown_escape(thermal_chamber_rule.get("temperature_range_c")),
                "Temperature control",
                "Confirm the chamber range and hazard envelope before release.",
                "thermal_chamber_rule",
                "fixed",
            ]
        )
    else:
        rows.append(
            [
                "Ambient-compatible environment",
                f"Hold {target_temperature_c:.1f} C in the declared test environment",
                "Temperature stabilization",
                "A chamber becomes mandatory outside the lab reference window.",
                "pretest_assistant_guidance",
                "fixed",
            ]
        )
    return rows


def _format_c_rate_value(value: Any) -> str:
    try:
        return f"{float(value):.2f}C"
    except (TypeError, ValueError):
        return str(value)


def _format_c_rate_current_basis(
    c_rate: Any,
    reference_capacity_ah: Any,
) -> str:
    try:
        c_rate_value = float(c_rate)
    except (TypeError, ValueError):
        return str(c_rate)

    if reference_capacity_ah not in (None, ""):
        try:
            capacity_value = float(reference_capacity_ah)
        except (TypeError, ValueError):
            capacity_value = None
        else:
            if capacity_value > 0:
                return (
                    f"{c_rate_value:.2f}C "
                    f"({c_rate_value:.2f} x {capacity_value:.3g} Ah = {c_rate_value * capacity_value:.2f} A)"
                )

    return f"{c_rate_value:.2f}C (I = {c_rate_value:.2f} x Q_ref in A)"


def _lookup_step(protocol_steps: list[dict[str, Any]], step_id: str) -> dict[str, Any]:
    for step in protocol_steps:
        if str(step.get("step_id") or "").strip() == step_id:
            return step
    return {}


def _step_details(protocol_steps: list[dict[str, Any]], step_id: str) -> str:
    return str(_lookup_step(protocol_steps, step_id).get("details") or "").strip()


def _extract_first_match(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value, flags=re.IGNORECASE)
    if not match:
        return None
    return str(match.group(1)).strip()


def _build_pulse_hppc_parameter_rows(
    *,
    requested_conditions: dict[str, Any],
    protocol_steps: list[dict[str, Any]],
    charge_voltage_v: float,
    discharge_cutoff_v: float,
    selected_cell_reference: dict[str, Any] | None,
    analysis_outputs: dict[str, list[str]] | None,
) -> list[list[Any]]:
    nominal_capacity_ah = (
        selected_cell_reference.get("nominal_capacity_ah")
        if isinstance(selected_cell_reference, dict)
        else None
    )
    acclimation_details = _step_details(protocol_steps, "climate_chamber_acclimation")
    reference_charge_details = _step_details(protocol_steps, "reference_full_charge")
    reference_discharge_details = _step_details(protocol_steps, "reference_capacity_discharge")
    staircase_details = _step_details(protocol_steps, "soc_staircase")
    discharge_pulse_details = _step_details(protocol_steps, "discharge_pulse")
    charge_pulse_details = _step_details(protocol_steps, "charge_pulse")

    acclimation_time = (
        _extract_first_match(r"rest for ([0-9.]+\s*h)", acclimation_details)
        or acclimation_details
        or "Confirm from released method step"
    )
    reference_discharge_rate = (
        _extract_first_match(r"discharge at ([0-9.]+C)", reference_discharge_details)
        or _format_c_rate_value(requested_conditions.get("discharge_c_rate"))
    )
    rest_before_staircase = (
        _extract_first_match(r"rest ([0-9.]+\s*h)", staircase_details)
        or staircase_details
        or "Confirm from released method step"
    )
    soc_spacing = (
        _extract_first_match(r"step the cell by (.+?) increments", staircase_details)
        or staircase_details
        or "Confirm from released method step"
    )
    rest_per_soc_point = (
        _extract_first_match(r"with ([0-9.]+\s*h) rests", staircase_details)
        or staircase_details
        or "Confirm from released method step"
    )
    pulse_duration = (
        _extract_first_match(r"for ([0-9.]+\s*s)", discharge_pulse_details)
        or _extract_first_match(r"for ([0-9.]+\s*s)", charge_pulse_details)
        or "Confirm from released method step"
    )
    recovery_duration = (
        _extract_first_match(r"followed by a ([0-9.]+\s*s) rest", discharge_pulse_details)
        or _extract_first_match(r"followed by a ([0-9.]+\s*s) rest", charge_pulse_details)
        or "Confirm from released method step"
    )
    derived_metrics = [
        str(item).strip()
        for item in (
            (analysis_outputs or {}).get("tables", [])
            + (analysis_outputs or {}).get("graphs", [])
        )
        if str(item).strip()
    ]
    reported_metrics = [
        item
        for item in derived_metrics
        if item.startswith("R_") or "Power capability map" in item
    ] or ["R_2s, R_10s, and R_18s"]

    rows: list[list[Any]] = [
        [
            "Test temperature",
            f"{_markdown_escape(requested_conditions.get('target_temperature_c'))} C",
            "requested_conditions",
            "fixed",
            "Release basis for the active pulse campaign.",
        ],
        [
            "Acclimation time",
            acclimation_time,
            "primary_method_reference",
            "fixed",
            "Pre-pulse temperature stabilization hold.",
        ],
        [
            "Charge protocol",
            reference_charge_details or "CC-CV to the declared upper voltage limit.",
            "primary_method_reference",
            "fixed",
            "Carry the active CV termination rule into the tester program.",
        ],
        [
            "Reference discharge rate",
            reference_discharge_rate,
            "primary_method_reference",
            "fixed",
            "Reference discharge that defines usable capacity before the SOC ladder.",
        ],
        [
            "Rest before staircase",
            rest_before_staircase,
            "primary_method_reference",
            "fixed",
            "Pre-staircase stabilization hold.",
        ],
        [
            "SOC spacing",
            soc_spacing,
            "primary_method_reference",
            "fixed",
            "Use the released SOC or DoD wording consistently in the tester and report.",
        ],
        [
            "Rest per SOC point",
            rest_per_soc_point,
            "primary_method_reference",
            "fixed",
            "Apply before each paired pulse block.",
        ],
        [
            "Discharge pulse current",
            _format_c_rate_current_basis(
                requested_conditions.get("discharge_c_rate"),
                nominal_capacity_ah,
            ),
            "primary_method_reference",
            "fixed",
            "Pulse basis: discharge C-rate on Q_ref.",
        ],
        [
            "Charge pulse current",
            _format_c_rate_current_basis(
                requested_conditions.get("charge_c_rate"),
                nominal_capacity_ah,
            ),
            "primary_method_reference",
            "fixed",
            "Pulse basis: charge C-rate on Q_ref.",
        ],
        [
            "Pulse duration",
            pulse_duration,
            "primary_method_reference",
            "fixed",
            "Apply per pulse direction unless a reviewed deviation overrides it.",
        ],
        [
            "Recovery duration",
            recovery_duration,
            "primary_method_reference",
            "fixed",
            "Immediate post-pulse recovery hold.",
        ],
        [
            "Lower / upper cut-offs",
            f"{discharge_cutoff_v:.2f} V / {charge_voltage_v:.2f} V",
            "controlled_constraints",
            "fixed",
            "Stop the pulse when the active voltage limit is reached.",
        ],
        [
            "Reported metrics",
            ", ".join(reported_metrics),
            "primary_method_reference",
            "fixed",
            "Emit resistance metrics with their time basis in the output package.",
        ],
    ]
    return rows


def _build_protocol_parameter_rows(
    *,
    method: dict[str, Any],
    requested_conditions: dict[str, Any],
    protocol_steps: list[dict[str, Any]],
    charge_voltage_v: float,
    discharge_cutoff_v: float,
    selected_cell_reference: dict[str, Any] | None,
    analysis_outputs: dict[str, list[str]] | None,
) -> list[list[Any]]:
    method_id = str(method.get("id") or "")
    if method_id == "pulse_hppc":
        return _build_pulse_hppc_parameter_rows(
            requested_conditions=requested_conditions,
            protocol_steps=protocol_steps,
            charge_voltage_v=charge_voltage_v,
            discharge_cutoff_v=discharge_cutoff_v,
            selected_cell_reference=selected_cell_reference,
            analysis_outputs=analysis_outputs,
        )

    rows: list[list[Any]] = [
        [
            "Target Temperature",
            f"{_markdown_escape(requested_conditions.get('target_temperature_c'))} C",
            "requested_conditions",
            "fixed",
            "",
        ],
        [
            "Charge Rate",
            f"{_markdown_escape(requested_conditions.get('charge_c_rate'))} C",
            "requested_conditions",
            "fixed",
            "",
        ],
        [
            "Discharge Rate",
            f"{_markdown_escape(requested_conditions.get('discharge_c_rate'))} C",
            "requested_conditions",
            "fixed",
            "",
        ],
        [
            "Voltage Window",
            f"{charge_voltage_v:.2f} V to {discharge_cutoff_v:.2f} V",
            "controlled_constraints",
            "fixed",
            "",
        ],
    ]
    run_length_field = requested_conditions.get("run_length_field")
    if _is_declared_input_present(run_length_field):
        run_length_label = _humanize_field_name(str(run_length_field))
        rows.append(
            [
                run_length_label,
                _markdown_escape(requested_conditions.get(str(run_length_field))),
                "requested_conditions",
                "fixed",
                f"Basis: {_markdown_escape(requested_conditions.get('run_length_basis'))}",
            ]
        )
    return rows


def _build_workflow_step_rows(protocol_steps: list[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for step in protocol_steps:
        rows.append(
            [
                step.get("order"),
                step.get("name", "Protocol step"),
                step.get("details", "n/a"),
                "primary_method_reference"
                if step.get("source_backed", True)
                else "planner_completion",
                _step_lock_status(step),
                _display_step_strictness_label(str(step.get("step_strictness") or "")),
            ]
        )
    return rows


def _build_calculation_qc_rows(
    *,
    method: dict[str, Any],
    requested_conditions: dict[str, Any],
    selected_cell_reference: dict[str, Any] | None,
) -> list[list[Any]]:
    method_id = str(method.get("id") or "")
    if method_id != "pulse_hppc":
        return []

    nominal_capacity_ah = (
        selected_cell_reference.get("nominal_capacity_ah")
        if isinstance(selected_cell_reference, dict)
        else None
    )
    discharge_current_basis = _format_c_rate_current_basis(
        requested_conditions.get("discharge_c_rate"),
        nominal_capacity_ah,
    )
    charge_current_basis = _format_c_rate_current_basis(
        requested_conditions.get("charge_c_rate"),
        nominal_capacity_ah,
    )
    return [
        [
            "Resistance definition",
            "R_t = |V_t - V_pre| / |I_t - I_pre| at t = 2 s, 10 s, and 18 s.",
            "built_in_guidance",
            "review_required",
            "Store pulse direction separately and report resistance as a positive magnitude.",
        ],
        [
            "Pre-pulse baseline",
            "Use the final stable pre-pulse rest samples immediately before pulse start for V_pre and I_pre.",
            "built_in_guidance",
            "review_required",
            "If multiple samples exist in the final idle window, use their mean and report the achieved sample interval.",
        ],
        [
            "Pulse current basis",
            f"Discharge: {discharge_current_basis}; charge: {charge_current_basis}.",
            "built_in_guidance",
            "review_required",
            "Implement current setpoints in A in the tester program, even when the released plan is written in C-rate.",
        ],
        [
            "Pulse-level calculation rule",
            "Compute R_2s, R_10s, and R_18s for each pulse independently before any SOC-level summary.",
            "built_in_guidance",
            "review_required",
            "Do not mix charge and discharge pulses in the same resistance aggregate.",
        ],
        [
            "Aggregation rule",
            "Summarize per cell x SOC x pulse direction with the released aggregation rule and report n pulses.",
            "built_in_guidance",
            "review_required",
            "Use the same aggregation route for all resistance time bases in the campaign.",
        ],
        [
            "Early cutoff handling",
            "If a pulse ends early at a voltage limit, mark any later R_t metric as missing and flag the pulse as truncated.",
            "built_in_guidance",
            "review_required",
            "Do not extrapolate R_18s beyond the achieved pulse duration.",
        ],
        [
            "Power capability map basis",
            "State the resistance basis, pulse direction, and active voltage window before deriving any power map.",
            "built_in_guidance",
            "review_required",
            "Do not release a power capability map without its time basis and voltage constraints.",
        ],
        [
            "Transient sampling validity",
            "Target 10-20 ms pulse sampling only when the tester and DAQ path can achieve it; otherwise record the achieved interval.",
            "built_in_guidance",
            "review_required",
            "Carry the achieved sample interval into the QC note for pulse-derived metrics.",
        ],
    ]


def _build_checkpoint_rule_rows(
    *,
    requested_conditions: dict[str, Any],
    reference_check_policy: dict[str, Any],
    safety_checklist: list[str],
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    if reference_check_policy:
        cadence_mode = (
            reference_check_policy.get("rpt_cadence_mode", {}).get("default_mode")
            if isinstance(reference_check_policy.get("rpt_cadence_mode"), dict)
            else None
        )
        if cadence_mode:
            rows.append(
                [
                    "RPT cadence mode",
                    cadence_mode,
                    "reference_check_policy",
                    "review_required",
                    "Confirm the cadence mode before release when the campaign matrix changes.",
                ]
            )
        core_rpt_set = reference_check_policy.get("core_rpt_set", {})
        if core_rpt_set:
            rows.append(
                [
                    "Core RPT set",
                    _markdown_escape(core_rpt_set.get("source_method_ids") or core_rpt_set.get("bundle_id")),
                    "reference_check_policy",
                    "fixed",
                    _markdown_escape(core_rpt_set.get("summary") or ""),
                ]
            )
        checkpoint_templates = reference_check_policy.get("checkpoint_templates", [])
        if checkpoint_templates:
            template_names = []
            for template in checkpoint_templates:
                trigger = template.get("trigger") or template.get("checkpoint_label")
                template_names.append(_markdown_escape(trigger))
            rows.append(
                [
                    "Checkpoint templates",
                    ", ".join(template_names),
                    "reference_check_policy",
                    "review_required",
                    "Review trigger timing and bundle order before release.",
                ]
            )
        reference_temperature = _format_reference_temperature(
            reference_check_policy.get("reference_temperature_c", {})
        )
        if reference_temperature:
            rows.append(
                [
                    "Reference Check Policy",
                    reference_temperature,
                    "reference_check_policy",
                    "fixed",
                    "Reference temperature and pre-checkpoint hold guidance.",
                ]
            )
    if _is_declared_input_present(requested_conditions.get("checkpoint_interval")):
        rows.append(
            [
                "Requested checkpoint interval",
                requested_conditions.get("checkpoint_interval"),
                "requested_conditions",
                "fixed",
                "",
            ]
        )
    if _is_declared_input_present(requested_conditions.get("stop_criterion")):
        rows.append(
            [
                "Stop criterion",
                requested_conditions.get("stop_criterion"),
                "requested_conditions",
                "review_required",
                "Human release review still required before execution.",
            ]
        )
    abort_items = [
        item for item in safety_checklist if "abort" in item.lower() or "whichever occurs first" in item.lower()
    ]
    if abort_items:
        rows.append(
            [
                "Abort and stop rules",
                "; ".join(abort_items),
                "pretest_assistant_guidance",
                "fixed",
                "",
            ]
        )
    return rows


def _build_data_output_payload(
    *,
    data_acquisition: list[str],
    analysis_outputs: dict[str, list[str]],
) -> dict[str, list[str]]:
    raw_data = list(dict.fromkeys(item for item in data_acquisition if str(item).strip()))
    raw_data = [
        (
            "Pulse segments: target 10 to 20 ms sampling only when the tester path can achieve it; "
            "otherwise log the achieved fastest supported interval and carry it into QC notes."
            if str(item).strip()
            == "Pulse segments: measure every 10 to 20 ms if possible, or at the fastest tester-supported sampling rate."
            else str(item).strip()
        )
        for item in raw_data
    ]
    derived_metrics = list(
        dict.fromkeys(
            [
                *[str(item).strip() for item in analysis_outputs.get("tables", []) if str(item).strip()],
                *[str(item).strip() for item in analysis_outputs.get("graphs", []) if str(item).strip()],
            ]
        )
    )
    audit_metadata = [
        "cell_id / subject identifier",
        "instrument and channel identifier",
        "thermal environment identifier",
        "thermocouple placement / sensor identifier",
        "operator notes and anomaly flags",
    ]
    return {
        "raw_data": raw_data,
        "derived_metrics": derived_metrics,
        "audit_metadata": audit_metadata,
    }


def _build_references_section_markdown(answer_references: list[dict[str, Any]]) -> list[str]:
    markdown = build_grouped_reference_markdown(
        answer_references,
        include_section_heading=True,
    )
    return markdown.splitlines() if markdown else []


def _build_experiment_plan_markdown(
    *,
    release_status: str,
    method: dict[str, Any],
    selected_cell_reference: dict[str, Any] | None,
    known_constraint_rows: list[list[Any]],
    equipment_setup_rows: list[list[Any]],
    phase_rows: list[list[Any]],
    condition_rows: list[dict[str, Any]],
    parameter_table_title: str,
    parameter_rows: list[list[Any]],
    checkpoint_rule_rows: list[list[Any]],
    data_outputs: dict[str, list[str]],
    pending_confirmation_rows: list[list[Any]],
    analysis_plan_rows: list[list[Any]],
    answer_references: list[dict[str, Any]],
    warnings: list[str],
    workflow_rows: list[list[Any]],
    calculation_qc_rows: list[list[Any]],
) -> str:
    grouped_constraint_rows: dict[str, list[list[Any]]] = {
        "Fixed Facts": [],
        "Provisional Defaults": [],
        "Internal SOP Constraints": [],
        "Unresolved Hard Constraints": [],
    }
    for row in known_constraint_rows:
        if len(row) < 4:
            grouped_constraint_rows["Fixed Facts"].append(row)
            continue
        source_type = str(row[2] or "")
        lock_status = str(row[3] or "")
        if lock_status == "blocked" or source_type == "registry_review":
            grouped_constraint_rows["Unresolved Hard Constraints"].append(row)
        elif source_type in {
            "pretest_assistant_guidance",
            "reference_check_policy",
        }:
            grouped_constraint_rows["Internal SOP Constraints"].append(row)
        elif source_type.startswith("registry_") or source_type in {
            "local_registry",
            "registry_chemistry_profile",
        }:
            grouped_constraint_rows["Provisional Defaults"].append(row)
        else:
            grouped_constraint_rows["Fixed Facts"].append(row)

    cell_summary_rows = _build_selected_cell_summary_rows(selected_cell_reference)
    locked_limit_rows: list[list[Any]] = []
    locked_limit_rows.extend(_simplify_table_rows(cell_summary_rows, [0, 1, 4]))
    locked_limit_rows.extend(
        _simplify_table_rows(grouped_constraint_rows.get("Fixed Facts", []), [0, 1, 4])
    )
    locked_limit_rows.extend(
        _simplify_table_rows(grouped_constraint_rows.get("Provisional Defaults", []), [0, 1, 4])
    )

    safety_rows: list[list[Any]] = []
    safety_rows.extend(
        _simplify_table_rows(grouped_constraint_rows.get("Internal SOP Constraints", []), [0, 1, 4])
    )
    safety_rows.extend(_simplify_table_rows(checkpoint_rule_rows, [0, 1, 4]))

    review_items = _build_release_review_items(
        grouped_constraint_rows=grouped_constraint_rows,
        pending_confirmation_rows=pending_confirmation_rows,
        warnings=warnings,
    )

    plan_status_sections: list[str] = [
        "## Plan Status & Constraints",
        "",
        "### Objective",
        str(method.get("intent") or "Structured protocol draft for the selected objective and method reference.").strip(),
    ]
    if locked_limit_rows:
        plan_status_sections.extend(
            [
                "",
                "### Controlled Test Object And Locked Limits",
                _render_markdown_table(["Item", "Value", "Notes"], locked_limit_rows),
            ]
        )
    if safety_rows:
        plan_status_sections.extend(
            [
                "",
                "### Active Safety And Release Constraints",
                _render_markdown_table(["Item", "Value", "Notes"], safety_rows),
            ]
        )
    if review_items:
        plan_status_sections.extend(
            [
                "",
                "### Review Items Before Release",
                _bullet_lines(review_items),
            ]
        )

    lines = [
        "# Experiment Plan",
        "",
        f"Status: {release_status}",
        "",
        *plan_status_sections,
    ]

    lines.extend(
        [
            "",
            "## Protocol",
            "### Equipment & Setup",
        ]
    )
    lines.extend(
        [
            _render_markdown_table(
                ["Equipment", "Required capability", "Used for", "Critical setting or placement"],
                _simplify_table_rows(equipment_setup_rows, [0, 1, 2, 3]),
            ),
        ]
    )
    if condition_rows:
        lines.extend(
            [
                "",
                "### Condition Matrix",
                _render_markdown_table(
                    ["Condition", "Value", "Notes"],
                    [
                        [
                            row.get("condition"),
                            row.get("value"),
                            row.get("note"),
                        ]
                        for row in condition_rows
                    ],
                ),
            ]
        )
    lines.extend(
        [
            "",
            f"### {parameter_table_title}",
            _render_markdown_table(
                ["Parameter", "Value", "Notes"],
                _simplify_table_rows(parameter_rows, [0, 1, 4]),
            ),
            "",
            "### Recommended Execution Sequence",
            _render_execution_sequence(workflow_rows),
        ]
    )

    lines.extend(
        [
            "",
            "## Outputs & Basis",
            "### Required Outputs For Analysis",
            _render_output_summary_table(data_outputs),
        ]
    )
    if calculation_qc_rows:
        lines.extend(
            [
                "",
                "### Calculation & QC Notes",
                _render_markdown_table(
                    ["Item", "Definition or rule", "Notes"],
                    _simplify_table_rows(calculation_qc_rows, [0, 1, 4]),
                ),
            ]
        )
    if analysis_plan_rows:
        lines.extend(
            [
                "",
                "### Analysis Plan",
                _render_markdown_table(
                    [
                        "primary_response",
                        "analysis_unit",
                        "aggregation_rule",
                        "inferential_route",
                        "required_report_outputs",
                    ],
                    analysis_plan_rows,
                ),
            ]
        )
    if warnings:
        lines.extend(["", "### Notes", _bullet_lines(warnings)])
    reference_lines = build_grouped_reference_markdown(
        answer_references,
        include_section_heading=False,
    ).splitlines()
    if reference_lines:
        lines.extend(["", "### References", *reference_lines])
    return "\n".join(lines).strip()


def _build_release_controls(
    *,
    method: dict[str, Any],
    selected_cell_reference: dict[str, Any] | None,
    unresolved_registry_constraints: list[str],
    deviation_policy: dict[str, Any],
    requested_conditions: dict[str, Any],
    input_contract: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[list[Any]], dict[str, Any] | None]:
    execution_blockers: list[dict[str, Any]] = []
    review_gates: list[dict[str, Any]] = []

    method_id = str(method.get("id") or "")
    if method_id == "pulse_hppc" and selected_cell_reference is not None:
        if selected_cell_reference.get("max_continuous_discharge_current_a") is None:
            execution_blockers.append(
                {
                    "item": "selected_cell_max_continuous_discharge_current_a",
                    "severity": "safety_boundary",
                    "type": "execution_blocker",
                    "reason": "The selected cell does not declare a continuous discharge-current allowance, so the pulse amplitude cannot be safely locked.",
                    "next_action": "Provide the cell discharge-current limit or a reviewed pulse-current allowance.",
                    "missing_field": "max_continuous_discharge_current_a",
                }
            )
        if (
            selected_cell_reference.get("source_kind") == "uploaded_cell_datasheet_candidate"
            and not _is_declared_input_present(requested_conditions.get("dcir_definition"))
        ):
            execution_blockers.append(
                {
                    "item": "dcir_definition",
                    "severity": "method_core",
                    "type": "execution_blocker",
                    "reason": "The uploaded datasheet does not define the DCIR/DCR resistance convention, so the pulse definition must be confirmed before the plan can be released.",
                    "next_action": "Provide the DCIR/DCR definition in the parameter request popup, including pulse basis, time basis, SOC coverage, and rest convention.",
                    "missing_field": "dcir_definition",
                }
            )

    if (
        method_id == "cycle_life"
        and selected_cell_reference is not None
        and selected_cell_reference.get("source_kind") == "uploaded_cell_datasheet_candidate"
    ):
        missing_ageing_fields: list[tuple[str, str, str]] = []
        if not _is_declared_input_present(requested_conditions.get("ageing_condition_matrix")):
            missing_ageing_fields.append(
                (
                    "ageing_condition_matrix",
                    "ageing_condition_matrix",
                    "The uploaded datasheet does not define a project-specific ageing condition matrix, so the comparative ageing conditions must be supplied before release.",
                )
            )
        if not _is_declared_input_present(requested_conditions.get("checkpoint_interval")):
            missing_ageing_fields.append(
                (
                    "checkpoint_interval",
                    "checkpoint_interval",
                    "The checkpoint cadence must be declared before the ageing plan can be released.",
                )
            )
        if not _is_declared_input_present(requested_conditions.get("stop_criterion")):
            missing_ageing_fields.append(
                (
                    "stop_criterion",
                    "stop_criterion",
                    "The ageing stop criterion must be declared before release.",
                )
            )
        for item_name, missing_field, reason in missing_ageing_fields:
            execution_blockers.append(
                {
                    "item": item_name,
                    "severity": "method_core",
                    "type": "execution_blocker",
                    "reason": reason,
                    "next_action": "Provide the missing value in the parameter request popup before the plan is released.",
                    "missing_field": missing_field,
                }
            )

    if unresolved_registry_constraints:
        review_gates.append(
            {
                "item": "registry_constraints",
                "severity": "review_gate",
                "type": "review_gate",
                "reason": "; ".join(str(item).strip() for item in unresolved_registry_constraints if str(item).strip()),
                "next_action": "Confirm these registry-level gaps do not change the released protocol limits.",
            }
        )

    deviation_items = list(deviation_policy.get("deviation_review_items", []))
    if deviation_items:
        review_gates.append(
            {
                "item": "deviation_review_items",
                "severity": "review_gate",
                "type": "review_gate",
                "reason": "; ".join(str(item).strip() for item in deviation_items if str(item).strip()),
                "next_action": "Review and approve any tailorable or planner-completed steps before release.",
            }
        )

    if method.get("human_review_required", True):
        review_gates.append(
            {
                "item": "human_review",
                "severity": "review_gate",
                "type": "review_gate",
                "reason": "This controlled method still requires human release review before execution.",
                "next_action": "Confirm the released protocol, sign-off owner, and final stop-rule wording.",
            }
        )

    pending_confirmation_rows = [
        [
            item.get("item"),
            item.get("severity"),
            item.get("type"),
            item.get("reason"),
            item.get("next_action"),
        ]
        for item in [*execution_blockers, *review_gates]
    ]

    if execution_blockers:
        release_status = "blocker_aware_draft"
    elif review_gates:
        release_status = "review_required_protocol"
    elif not input_contract.get("unresolved_required_inputs") and not input_contract.get(
        "missing_conditional_required_inputs"
    ):
        release_status = "runnable_protocol"
    else:
        release_status = "non_runnable_fact_only"

    parameter_request = None
    missing_request_fields = [
        str(item.get("missing_field") or "").strip()
        for item in execution_blockers
        if str(item.get("missing_field") or "").strip()
    ]
    if missing_request_fields:
        parameter_request = build_parameter_request_payload(
            request_id=f"{method_id or 'method'}::{'-'.join(sorted(missing_request_fields))}",
            method=method,
            release_status=release_status,
            missing_fields=missing_request_fields,
            input_contract=input_contract,
            requested_conditions=requested_conditions,
        )

    return (
        release_status,
        execution_blockers,
        review_gates,
        pending_confirmation_rows,
        parameter_request,
    )


def _build_ui_markdown(
    *,
    method: dict[str, Any],
    release_status: str,
    selected_cell_reference: dict[str, Any] | None,
    applied_constraints: dict[str, Any],
    requested_conditions: dict[str, Any],
    equipment_rule: dict[str, Any],
    thermal_chamber_rule: dict[str, Any] | None,
    protocol_steps: list[dict[str, Any]],
    data_acquisition: list[str],
    warnings: list[str],
    analysis_outputs: dict[str, list[str]],
    constraint_sources: dict[str, str],
    unresolved_registry_constraints: list[str],
    reference_check_policy: dict[str, Any],
    answer_references: list[dict[str, Any]],
    safety_checklist: list[str],
    pending_confirmation_rows: list[list[Any]],
    execution_blockers: list[dict[str, Any]],
    lab_pretest_guidance: dict[str, Any] | None,
) -> str:
    thermocouple_guidance = (
        dict((lab_pretest_guidance or {}).get("thermocouple_guidance", {}))
        if isinstance((lab_pretest_guidance or {}).get("thermocouple_guidance", {}), dict)
        else {}
    )
    phase_rows = _build_phase_rows(str(method.get("id") or ""), protocol_steps)
    condition_rows = _build_condition_rows(requested_conditions)
    known_constraint_rows = _build_known_constraint_rows(
        method_id=str(method.get("id") or ""),
        applied_constraints=applied_constraints,
        constraint_sources=constraint_sources,
        unresolved_registry_constraints=unresolved_registry_constraints,
        selected_cell_reference=selected_cell_reference,
        execution_blockers=execution_blockers,
    )
    equipment_setup_rows = _build_equipment_setup_rows(
        equipment_rule=equipment_rule,
        thermal_chamber_rule=thermal_chamber_rule,
        thermocouple_guidance=thermocouple_guidance,
        target_temperature_c=float(requested_conditions.get("target_temperature_c", 25.0)),
    )
    parameter_rows = _build_protocol_parameter_rows(
        method=method,
        requested_conditions=requested_conditions,
        protocol_steps=protocol_steps,
        charge_voltage_v=float(applied_constraints.get("charge_voltage_v")),
        discharge_cutoff_v=float(applied_constraints.get("discharge_cutoff_v")),
        selected_cell_reference=selected_cell_reference,
        analysis_outputs=analysis_outputs,
    )
    workflow_rows = _build_workflow_step_rows(protocol_steps)
    checkpoint_rule_rows = _build_checkpoint_rule_rows(
        requested_conditions=requested_conditions,
        reference_check_policy=reference_check_policy,
        safety_checklist=safety_checklist,
    )
    data_outputs = _build_data_output_payload(
        data_acquisition=data_acquisition,
        analysis_outputs=analysis_outputs,
    )
    analysis_plan_rows: list[list[Any]] = []
    if requested_conditions.get("sample_count") or requested_conditions.get("cell_count"):
        analysis_plan_rows.append(
            [
                "Primary response from declared condition matrix",
                "cell-level",
                "per-cell summary at each active checkpoint",
                "compare conditions after confirming distributional assumptions",
                "condition summary table, outlier rule, checkpoint trend plot",
            ]
        )
    calculation_qc_rows = _build_calculation_qc_rows(
        method=method,
        requested_conditions=requested_conditions,
        selected_cell_reference=selected_cell_reference,
    )
    return _sanitize_user_facing_method_text(
        _build_experiment_plan_markdown(
            release_status=release_status,
            method=method,
            selected_cell_reference=selected_cell_reference,
            known_constraint_rows=known_constraint_rows,
            equipment_setup_rows=equipment_setup_rows,
            phase_rows=phase_rows,
            condition_rows=condition_rows,
            parameter_table_title=_METHOD_PARAMETER_LABELS.get(
                str(method.get("id") or ""),
                "Method Parameters",
            ),
            parameter_rows=parameter_rows,
            checkpoint_rule_rows=checkpoint_rule_rows,
            data_outputs=data_outputs,
            pending_confirmation_rows=pending_confirmation_rows,
            analysis_plan_rows=analysis_plan_rows,
            answer_references=answer_references,
            warnings=warnings,
            workflow_rows=workflow_rows,
            calculation_qc_rows=calculation_qc_rows,
        )
    )


def plan_method_protocol(
    *,
    method_id: str,
    chemistry: str | None,
    instrument: str | None,
    thermal_chamber: str | None,
    target_temperature_c: float,
    charge_c_rate: float,
    discharge_c_rate: float,
    form_factor: str | None,
    cycle_count: int,
    operator_notes: str,
    selected_cell_id: str | None = None,
    transient_selected_cell_record: dict[str, Any] | None = None,
    method_inputs: dict[str, Any] | None = None,
    approved_equipment_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_method_id = _resolve_structured_method_id(method_id)
    if resolved_method_id is None:
        raise KeyError(f"Unknown structured method: {method_id}")

    if instrument is None or not instrument.strip():
        raise KeyError("Instrument information is required to finalize the protocol.")

    method = get_method_definition(resolved_method_id)
    handbook_bundle = _get_method_handbook_bundle(
        method_id=resolved_method_id,
        chapter_id=method.get("chapter_id"),
    )
    selected_cell_record = transient_selected_cell_record or load_selected_cell_record(selected_cell_id)
    chemistry_profile, chemistry_warnings = resolve_chemistry_profile(
        chemistry=chemistry,
        selected_cell_record=selected_cell_record,
    )
    if chemistry_profile is None and selected_cell_record is None:
        raise KeyError("Provide a chemistry or selected cell to plan the method.")

    equipment_rule = get_equipment_rule(instrument)
    thermal_chamber_rule = (
        get_thermal_chamber_rule(thermal_chamber)
        if thermal_chamber is not None and thermal_chamber.strip()
        else None
    )
    effective_form_factor, form_factor_warnings = resolve_form_factor(
        form_factor=form_factor,
        selected_cell_record=selected_cell_record,
    )
    selected_cell_reference = build_selected_cell_reference(selected_cell_record)
    supported_chemistries = method.get(
        "currently_supported_chemistries",
        method.get("supported_chemistries", []),
    )
    if chemistry_profile is not None and supported_chemistries and chemistry_profile["id"] not in supported_chemistries:
        raise ValueError(
            f"Method '{resolved_method_id}' does not currently support chemistry '{chemistry_profile['id']}'."
        )

    objective_key = normalize_objective_key(method["objective_key"])
    objective_template = None
    if objective_key in load_kb()["objective_templates"]:
        objective_template = get_objective_template(objective_key)
    pretest_guidance = get_pretest_assistant_guidance()
    pretest_global_defaults = get_pretest_global_defaults()
    objective_guidance = get_pretest_objective_guidance(objective_key)
    decision_relation_model = get_decision_relation_model()
    decision_relation_classes = get_decision_relation_classes()
    authority_and_precedence = get_authority_and_precedence_model()
    requirement_strength_levels = get_requirement_strength_levels()
    conflict_representation = get_decision_conflict_representation()
    thermocouple_guidance = get_thermocouple_placement_guidance(effective_form_factor)
    rpt_playbook = (
        get_pretest_rpt_playbook()
        if resolved_method_id == "cycle_life" or objective_key in {"cycle_life", "rpt", "soh_modeling", "calendar_ageing"}
        else {}
    )

    warnings: list[str] = [*chemistry_warnings, *form_factor_warnings]
    unresolved_registry_constraints: list[str] = []

    selected_cell_source_kind = (
        selected_cell_record.get("source_kind") if selected_cell_record is not None else None
    )
    prefer_selected_cell_constraints = selected_cell_record is not None and (
        selected_cell_source_kind == "uploaded_cell_datasheet_candidate"
    )

    if chemistry_profile is not None:
        temp_min, temp_max = chemistry_profile["recommended_temperature_range_c"]
        if not temp_min <= target_temperature_c <= temp_max:
            warnings.append(
                f"Requested temperature {target_temperature_c:.1f} C is outside the chemistry guidance [{temp_min}, {temp_max}] C."
            )
    else:
        unresolved_registry_constraints.extend(
            [
                "Chemistry-specific temperature window is unresolved until the selected cell maps to a controlled registry chemistry.",
                "Chemistry-specific charge C-rate cap is unresolved until the selected cell maps to a controlled registry chemistry.",
                "Chemistry-specific discharge C-rate cap is unresolved until the selected cell maps to a controlled registry chemistry.",
            ]
        )
        warnings.append(
            "Selected cell chemistry is not mapped to a controlled registry profile. Keep chemistry-specific safety limits open for review."
        )

    if thermal_chamber_rule is not None:
        chamber_temp_min, chamber_temp_max = thermal_chamber_rule["temperature_range_c"]
        if not chamber_temp_min <= target_temperature_c <= chamber_temp_max:
            warnings.append(
                f"Requested temperature {target_temperature_c:.1f} C is outside the thermal chamber envelope [{chamber_temp_min}, {chamber_temp_max}] C."
            )
        warnings.append(
            "If the selected thermal chamber is BINDER LIT MK and the planned work could escalate to EUCAR 4-6, confirm individual-cell-only scope and the defined-load rule before release."
        )
    elif chamber_required_for_temperature(target_temperature_c):
        raise ValueError(
            "Lab pretest SOP requires an environmental chamber for any test outside 25 +/- 2 C."
        )

    requested_charge = charge_c_rate
    requested_discharge = discharge_c_rate
    normalized_method_inputs = {
        str(key): value
        for key, value in (method_inputs or {}).items()
        if isinstance(key, str)
    }

    method_defaults = method.get("protocol_template", {}).get("defaults", method.get("recommended_defaults", {}))
    fixed_rate = method_defaults.get("fixed_c_rate")
    if fixed_rate is not None:
        charge_c_rate = float(fixed_rate)
        discharge_c_rate = float(fixed_rate)
        if requested_charge != charge_c_rate or requested_discharge != discharge_c_rate:
            warnings.append(
                f"{method['label']} uses a fixed slow rate of {charge_c_rate:.2f}C from the source reference."
            )

    if selected_cell_record is not None:
        selected_cell_electrical = selected_cell_record.get("electrical", {})
        selected_cell_currents = selected_cell_record.get("currents", {})
        selected_cell_nominal_capacity_ah = selected_cell_electrical.get("nominal_capacity_ah")
        charge_c_rate, charge_warning = _cap_rate_by_selected_cell_limit(
            requested_rate=charge_c_rate,
            nominal_capacity_ah=(
                float(selected_cell_nominal_capacity_ah)
                if selected_cell_nominal_capacity_ah not in (None, 0)
                else None
            ),
            max_current_a=selected_cell_currents.get("max_continuous_charge_current_a"),
            label="continuous-charge",
        )
        discharge_c_rate, discharge_warning = _cap_rate_by_selected_cell_limit(
            requested_rate=discharge_c_rate,
            nominal_capacity_ah=(
                float(selected_cell_nominal_capacity_ah)
                if selected_cell_nominal_capacity_ah not in (None, 0)
                else None
            ),
            max_current_a=selected_cell_currents.get("max_continuous_discharge_current_a"),
            label="continuous-discharge",
        )
        if charge_warning:
            warnings.append(charge_warning)
        if discharge_warning:
            warnings.append(discharge_warning)
    elif chemistry_profile is not None:
        charge_c_rate, charge_warning = _cap_rate(
            charge_c_rate,
            chemistry_profile["max_recommended_charge_c_rate"],
        )
        discharge_c_rate, discharge_warning = _cap_rate(
            discharge_c_rate,
            chemistry_profile["max_recommended_discharge_c_rate"],
        )

        if charge_warning:
            warnings.append(charge_warning)
        if discharge_warning:
            warnings.append(discharge_warning)

    logging_hint = objective_template["default_log_interval_seconds"] if objective_template else None
    if logging_hint is not None and logging_hint < equipment_rule["min_sampling_seconds"]:
        warnings.append(
            f"Instrument minimum sampling interval is {equipment_rule['min_sampling_seconds']} s, slower than the starter objective template."
        )

    run_length_field = str(method_defaults.get("run_length_field") or "cycle_count")
    run_length = _resolve_planning_run_length(
        method=method,
        requested_run_length=normalized_method_inputs.get(run_length_field, cycle_count),
    )
    rest_minutes = int(method_defaults.get("rest_minutes", 60))
    requested_run_length_field = run_length["field_name"]
    requested_run_length_basis = run_length["basis"]
    requested_run_length_value: Any = run_length["resolved_value"]

    if run_length["field_name"] != "cycle_count" and _is_declared_input_present(
        normalized_method_inputs.get(run_length["field_name"])
    ):
        requested_run_length_value = normalized_method_inputs[run_length["field_name"]]

    block_basis = str(
        normalized_method_inputs.get("block_basis")
        or method_defaults.get("default_block_basis")
        or ""
    ).strip()
    if block_basis == "elapsed_time" and _is_declared_input_present(
        normalized_method_inputs.get("elapsed_time_block")
    ):
        requested_run_length_field = "elapsed_time_block"
        requested_run_length_basis = "elapsed_time"
        requested_run_length_value = normalized_method_inputs["elapsed_time_block"]

    declared_inputs = _build_declared_method_inputs(
        method=method,
        chemistry_profile=chemistry_profile,
        selected_cell_reference=selected_cell_reference,
        instrument=instrument,
        thermal_chamber=thermal_chamber,
        effective_form_factor=effective_form_factor,
        target_temperature_c=target_temperature_c,
        requested_charge_c_rate=requested_charge,
        requested_discharge_c_rate=requested_discharge,
        run_length_field=requested_run_length_field,
        run_length_value=requested_run_length_value,
        method_inputs=normalized_method_inputs,
    )
    _validate_declared_method_inputs(
        method=method,
        declared_inputs=declared_inputs,
    )
    input_contract = _build_input_contract_payload(
        method,
        declared_inputs=declared_inputs,
    )

    cycle_count = int(run_length["resolved_value"])
    if run_length["resolved_value"] > run_length["requested_value"]:
        warnings.append(
            f"{method['label']} uses a minimum {run_length['field_name'].replace('_', ' ')} of "
            f"{run_length['minimum_value']} from the controlled method registry."
        )
    charge_voltage_v, discharge_cutoff_v, voltage_source = resolve_voltage_window(
        chemistry_profile=chemistry_profile,
        selected_cell_record=selected_cell_record,
        prefer_selected_cell_constraints=prefer_selected_cell_constraints,
    )
    warnings.extend(
        build_selected_cell_current_warnings(
            selected_cell_record=selected_cell_record,
            charge_c_rate=charge_c_rate,
            discharge_c_rate=discharge_c_rate,
        )
    )

    protocol_steps = _format_method_steps(
        method,
        charge_c_rate=charge_c_rate,
        discharge_c_rate=discharge_c_rate,
        target_temperature_c=target_temperature_c,
        rest_minutes=rest_minutes,
        charge_voltage_v=charge_voltage_v,
        discharge_cutoff_v=discharge_cutoff_v,
        cycle_count=cycle_count,
        cv_termination_rule=pretest_global_defaults.get("default_cv_termination_rule", {}),
        use_environmental_chamber=thermal_chamber_rule is not None
        or chamber_required_for_temperature(target_temperature_c),
        multi_temperature_mode=bool(
            normalized_method_inputs.get("temperature_points")
            or normalized_method_inputs.get("temperature_set")
            or normalized_method_inputs.get("temperature_matrix")
            or normalized_method_inputs.get("temperature_sweep")
        ),
    )
    deviation_policy = _build_deviation_policy(
        method=method,
        protocol_steps=protocol_steps,
    )

    data_acquisition = list(method.get("data_acquisition", []))
    analysis_outputs = method.get("required_outputs", {})
    approvals_required = [
        "Confirm voltage window against the cell or pack datasheet.",
        "Confirm current headroom, channel range, and thermocouple allocation.",
        "Confirm stop conditions, naming convention, and release authority.",
    ]
    if thermal_chamber_rule is not None:
        approvals_required.append(
            "Confirm chamber hazard envelope, gas detection readiness, and defined-load assumptions."
        )
    safety_checklist = get_safety_checklist(objective_key, thermal_chamber=thermal_chamber)
    cv_termination_rule = pretest_global_defaults.get("default_cv_termination_rule", {})
    terminate_when_any = list(cv_termination_rule.get("terminate_when_any", []))
    if terminate_when_any:
        safety_checklist.append(
            "Apply the lab default CV termination rule: "
            + "; ".join(str(item) for item in terminate_when_any)
            + "; whichever occurs first unless an approved test plan overrides it."
        )
    if thermocouple_guidance.get("placement_text"):
        safety_checklist.append(
            f"Attach the thermocouple according to the lab default placement for `{effective_form_factor}`: {thermocouple_guidance['placement_text']}"
        )
    if chamber_required_for_temperature(target_temperature_c):
        safety_checklist.append(
            "Use an environmental chamber because the requested temperature is outside 25 +/- 2 C."
        )
    deduped_safety_checklist: list[str] = []
    seen_safety_items: set[str] = set()
    for item in safety_checklist:
        if item in seen_safety_items:
            continue
        seen_safety_items.add(item)
        deduped_safety_checklist.append(item)
    safety_checklist = deduped_safety_checklist

    effective_reference_check_policy = json.loads(json.dumps(method.get("reference_check_policy", {})))
    if effective_reference_check_policy and resolved_method_id == "cycle_life":
        effective_reference_check_policy["reference_temperature_c"] = {
            "nominal": float(
                pretest_global_defaults.get("reference_temperature_c", 25.0)
            ),
            "tolerance_c": float(
                pretest_global_defaults.get(
                    "environmental_chamber_required_outside_reference_window",
                    {},
                ).get("tolerance_c", 2.0)
            ),
            "value_role": "lab_default_sop",
            "source_basis": "pretest_assistant_guidance.global_defaults",
            "review_note": "This lab default replaces the source-example reference temperature unless a reviewed deviation is approved."
        }
        warnings.append(
            "Using the lab default RPT reference temperature of 25.0 C in place of the source-example default."
        )

    method_source = handbook_bundle.get("source") if handbook_bundle else None
    chapter_file = _resolve_method_reference_file(method_source, method.get("chapter_id"))
    method_evidence_cards = handbook_bundle.get("evidence_cards", []) if handbook_bundle else []
    applied_constraints: dict[str, Any] = {
        "charge_voltage_v": charge_voltage_v,
        "discharge_cutoff_v": discharge_cutoff_v,
        "instrument_max_current_a": equipment_rule["max_current_a"],
        "instrument_max_voltage_v": equipment_rule["max_voltage_v"],
        "surface_temperature_abort_c": float(pretest_global_defaults.get("surface_temperature_abort_c", 60.0)),
        "cv_termination_current_a": 0.06,
        "cv_termination_c_rate_fraction": 0.05,
        "cv_max_hold_minutes": 120,
    }
    constraint_sources = {
        "charge_voltage_v": voltage_source,
        "discharge_cutoff_v": voltage_source,
        "instrument_max_current_a": "equipment_rule",
        "instrument_max_voltage_v": "equipment_rule",
        "surface_temperature_abort_c": "pretest_assistant_guidance",
        "cv_termination_current_a": "pretest_assistant_guidance",
        "cv_termination_c_rate_fraction": "pretest_assistant_guidance",
        "cv_max_hold_minutes": "pretest_assistant_guidance",
    }
    if resolved_method_id == "cycle_life":
        applied_constraints["lab_reference_temperature_c"] = float(
            pretest_global_defaults.get("reference_temperature_c", 25.0)
        )
        constraint_sources["lab_reference_temperature_c"] = "pretest_assistant_guidance"

    if chemistry_profile is not None and not prefer_selected_cell_constraints:
        applied_constraints["max_recommended_charge_c_rate"] = chemistry_profile[
            "max_recommended_charge_c_rate"
        ]
        applied_constraints["max_recommended_discharge_c_rate"] = chemistry_profile[
            "max_recommended_discharge_c_rate"
        ]
        constraint_sources["max_recommended_charge_c_rate"] = "registry_chemistry_profile"
        constraint_sources["max_recommended_discharge_c_rate"] = "registry_chemistry_profile"
    if selected_cell_reference is not None:
        selected_cell_constraint_source = (
            "uploaded_cell_datasheet_candidate"
            if selected_cell_reference.get("source_kind") == "uploaded_cell_datasheet_candidate"
            else "selected_cell_imported_metadata"
        )
        applied_constraints["selected_cell_nominal_capacity_ah"] = selected_cell_reference.get(
            "nominal_capacity_ah"
        )
        applied_constraints["selected_cell_max_continuous_charge_current_a"] = selected_cell_reference.get(
            "max_continuous_charge_current_a"
        )
        applied_constraints["selected_cell_max_continuous_discharge_current_a"] = selected_cell_reference.get(
            "max_continuous_discharge_current_a"
        )
        constraint_sources["selected_cell_nominal_capacity_ah"] = selected_cell_constraint_source
        constraint_sources["selected_cell_max_continuous_charge_current_a"] = selected_cell_constraint_source
        constraint_sources["selected_cell_max_continuous_discharge_current_a"] = (
            selected_cell_constraint_source
        )

    if thermal_chamber_rule is not None:
        applied_constraints["thermal_chamber_temperature_range_c"] = thermal_chamber_rule[
            "temperature_range_c"
        ]
        applied_constraints["thermal_chamber_operating_ambient_range_c"] = thermal_chamber_rule[
            "operating_ambient_range_c"
        ]
        applied_constraints["thermal_chamber_defined_load_without_operator_inertization"] = (
            thermal_chamber_rule["defined_load_without_operator_inertization"]
        )
        constraint_sources["thermal_chamber_temperature_range_c"] = "thermal_chamber_rule"
        constraint_sources["thermal_chamber_operating_ambient_range_c"] = "thermal_chamber_rule"
        constraint_sources["thermal_chamber_defined_load_without_operator_inertization"] = (
            "thermal_chamber_rule"
        )

    answer_references, answer_citation_map, references_markdown = _build_answer_references(
        method_source=method_source,
        objective_template=objective_template,
        chemistry_profile=chemistry_profile,
        selected_cell_reference=selected_cell_reference,
        equipment_rule=equipment_rule,
        thermal_chamber_rule=thermal_chamber_rule,
        include_pretest_guidance=True,
        include_decision_relation_model=True,
    )
    (
        release_status,
        execution_blockers,
        review_gates,
        pending_confirmation_rows,
        parameter_request,
    ) = _build_release_controls(
        method=method,
        selected_cell_reference=selected_cell_reference,
        unresolved_registry_constraints=unresolved_registry_constraints,
        deviation_policy=deviation_policy,
        requested_conditions={
            "target_temperature_c": target_temperature_c,
            "charge_c_rate": requested_charge,
            "discharge_c_rate": requested_discharge,
            "run_length_field": requested_run_length_field,
            "run_length_basis": requested_run_length_basis,
            "run_length_value": requested_run_length_value,
            requested_run_length_field: requested_run_length_value,
            "form_factor": effective_form_factor,
            "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
            **normalized_method_inputs,
        },
        input_contract=input_contract,
    )
    for blocker in execution_blockers:
        blocker_reason = str(blocker.get("reason") or "").strip()
        if blocker_reason and blocker_reason not in warnings:
            warnings.append(blocker_reason)
    step_provenance_summary = _build_step_provenance_summary(protocol_steps)
    controlled_planning_state = {
        "status": "blocked" if execution_blockers else "ready",
        "planning_mode": "grounded_protocol_mode",
        "must_call_controlled_source_before_step_guidance": True,
        "satisfied_by": [
            "plan_method_protocol",
            "method_handbook" if method_source is not None else "method_registry",
            "equipment_rule",
            "chemistry_profile" if chemistry_profile is not None else "selected_cell_reference"
            if selected_cell_reference is not None
            else "none",
            "thermal_chamber_rule" if thermal_chamber_rule is not None else "none",
        ],
    }
    response_policy = {
        "planning_mode": "grounded_protocol_mode",
        "allow_step_level_protocol": not bool(execution_blockers),
        "allow_generic_placeholders": False,
        "must_request_missing_inputs": bool(parameter_request),
        "must_state_blockers_before_release": True,
        "must_distinguish_tool_backed_and_planner_completion": True,
        "must_use_numeric_citations": bool(answer_references),
        "references_section_required": bool(answer_references),
        "citation_style": "numeric_brackets",
        "must_preserve_relation_class_semantics": True,
        "must_apply_authority_and_precedence": True,
        "must_preserve_requirement_strength": True,
        "must_keep_review_and_release_semantics_explicit": True,
    }
    known_constraint_rows = _build_known_constraint_rows(
        method_id=resolved_method_id,
        applied_constraints=applied_constraints,
        constraint_sources=constraint_sources,
        unresolved_registry_constraints=unresolved_registry_constraints,
        selected_cell_reference=selected_cell_reference,
        execution_blockers=execution_blockers,
    )
    equipment_setup_rows = _build_equipment_setup_rows(
        equipment_rule=equipment_rule,
        thermal_chamber_rule=thermal_chamber_rule,
        thermocouple_guidance=thermocouple_guidance,
        target_temperature_c=target_temperature_c,
    )
    condition_rows = _build_condition_rows(
        {
            "target_temperature_c": target_temperature_c,
            "charge_c_rate": requested_charge,
            "discharge_c_rate": requested_discharge,
            "run_length_field": requested_run_length_field,
            "run_length_basis": requested_run_length_basis,
            "run_length_value": requested_run_length_value,
            requested_run_length_field: requested_run_length_value,
            "form_factor": effective_form_factor,
            "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
            **normalized_method_inputs,
        }
    )
    parameter_rows = _build_protocol_parameter_rows(
        method=method,
        requested_conditions={
            "target_temperature_c": target_temperature_c,
            "charge_c_rate": requested_charge,
            "discharge_c_rate": requested_discharge,
            "run_length_field": requested_run_length_field,
            "run_length_basis": requested_run_length_basis,
            "run_length_value": requested_run_length_value,
            requested_run_length_field: requested_run_length_value,
            "form_factor": effective_form_factor,
            "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
            **normalized_method_inputs,
        },
        protocol_steps=protocol_steps,
        charge_voltage_v=charge_voltage_v,
        discharge_cutoff_v=discharge_cutoff_v,
        selected_cell_reference=selected_cell_reference,
        analysis_outputs=analysis_outputs,
    )
    checkpoint_rule_rows = _build_checkpoint_rule_rows(
        requested_conditions={
            "target_temperature_c": target_temperature_c,
            "charge_c_rate": requested_charge,
            "discharge_c_rate": requested_discharge,
            "run_length_field": requested_run_length_field,
            "run_length_basis": requested_run_length_basis,
            "run_length_value": requested_run_length_value,
            requested_run_length_field: requested_run_length_value,
            "form_factor": effective_form_factor,
            "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
            **normalized_method_inputs,
        },
        reference_check_policy=effective_reference_check_policy,
        safety_checklist=safety_checklist,
    )
    data_output_payload = _build_data_output_payload(
        data_acquisition=data_acquisition,
        analysis_outputs=analysis_outputs,
    )
    analysis_plan_rows: list[list[Any]] = []
    if normalized_method_inputs.get("sample_count") or normalized_method_inputs.get("cell_count"):
        analysis_plan_rows.append(
            [
                "Primary response from declared condition matrix",
                "cell-level",
                "per-cell summary at each active checkpoint",
                "compare conditions after confirming distributional assumptions",
                "condition summary table, outlier rule, checkpoint trend plot",
            ]
        )
    workflow_rows = _build_workflow_step_rows(protocol_steps)
    calculation_qc_rows = _build_calculation_qc_rows(
        method=method,
        requested_conditions={
            "target_temperature_c": target_temperature_c,
            "charge_c_rate": requested_charge,
            "discharge_c_rate": requested_discharge,
            "run_length_field": requested_run_length_field,
            "run_length_basis": requested_run_length_basis,
            "run_length_value": requested_run_length_value,
            requested_run_length_field: requested_run_length_value,
            "form_factor": effective_form_factor,
            "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
            **normalized_method_inputs,
        },
        selected_cell_reference=selected_cell_reference,
    )

    planning_target_label = (
        selected_cell_reference.get("display_name")
        if selected_cell_reference is not None and selected_cell_reference.get("display_name")
        else chemistry_profile["label"]
        if chemistry_profile is not None
        else "unmapped selected cell"
    )
    return {
        "status": "ok",
        "release_status": release_status,
        "protocol_name": f"{method['label']} - {planning_target_label} - {equipment_rule['label']}",
        "method_id": resolved_method_id,
        "method_label": method["label"],
        "source_pdf": _display_repo_asset_if_exists(SOURCE_PDF),
        "chapter_file": chapter_file,
        "method_reference": {
            "source_title": method["source_title"],
            "source_pages": method["source_pages"],
            "objective_key": objective_key,
            "source_id": method_source.get("source_id") if method_source else method.get("handbook_source_id"),
            "answer_reference_markdown": (
                method_source.get("answer_reference_markdown") if method_source else None
            ),
            "source_role": method_source.get("source_role") if method_source else None,
            "complementary_literature_source_ids": method.get(
                "complementary_literature_source_ids",
                [],
            ),
        },
        "strict_reference_policy": method.get("strict_reference_policy", {}),
        "campaign_framework": method.get("campaign_framework", {}),
        "reference_check_policy": effective_reference_check_policy,
        "lab_pretest_guidance": {
            "global_defaults": pretest_global_defaults,
            "thermocouple_guidance": thermocouple_guidance,
            "objective_guidance": objective_guidance,
            "rpt_playbook": rpt_playbook,
            "approved_equipment_defaults": approved_equipment_defaults
            or pretest_guidance.get("approved_equipment_defaults", {}),
        },
        "decision_graph_semantics": {
            "version": decision_relation_model.get("version"),
            "relation_classes": decision_relation_classes,
            "authority_and_precedence": authority_and_precedence,
            "requirement_strength_levels": requirement_strength_levels,
            "conflict_representation": conflict_representation,
        },
        "currently_supported_chemistries": method.get(
            "currently_supported_chemistries",
            method.get("supported_chemistries", []),
        ),
        "applicable_chemistry_scope": method.get("applicable_chemistry_scope", []),
        "method_status": method.get("method_status"),
        "execution_readiness": method.get("execution_readiness"),
        "human_review_required": method.get("human_review_required", True),
        "input_contract": input_contract,
        "deviation_policy": deviation_policy,
        "method_evidence_cards": method_evidence_cards,
        "answer_references": answer_references,
        "answer_citation_map": answer_citation_map,
        "references_markdown": references_markdown,
        "step_provenance_summary": step_provenance_summary,
        "planning_mode": "grounded_protocol_mode",
        "controlled_planning_state": controlled_planning_state,
        "response_policy": response_policy,
        "requested_conditions": {
            "target_temperature_c": target_temperature_c,
            "charge_c_rate": requested_charge,
            "discharge_c_rate": requested_discharge,
            "run_length_field": requested_run_length_field,
            "run_length_basis": requested_run_length_basis,
            "run_length_value": requested_run_length_value,
            requested_run_length_field: requested_run_length_value,
            "form_factor": effective_form_factor,
            "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
            **normalized_method_inputs,
        },
        "chemistry_id": chemistry_profile["id"] if chemistry_profile is not None else None,
        "chemistry_label": chemistry_profile["label"] if chemistry_profile is not None else "unknown",
        "instrument": equipment_rule["label"],
        "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
        "selected_cell_id": selected_cell_reference.get("cell_id") if selected_cell_reference else None,
        "selected_cell_reference": selected_cell_reference,
        "applied_constraints": applied_constraints,
        "constraint_sources": constraint_sources,
        "unresolved_registry_constraints": unresolved_registry_constraints,
        "execution_blockers": execution_blockers,
        "review_gates": review_gates,
        "pending_confirmations": pending_confirmation_rows,
        "parameter_request": parameter_request,
        "known_constraints": known_constraint_rows,
        "equipment_setup": equipment_setup_rows,
        "protocol_tables": {
            "phase_table": _build_phase_rows(resolved_method_id, protocol_steps),
            "condition_matrix": condition_rows,
            "parameter_tables": [
                {
                    "title": _METHOD_PARAMETER_LABELS.get(
                        resolved_method_id,
                        "Method Parameters",
                    ),
                    "rows": parameter_rows,
                }
            ],
            "workflow_steps": workflow_rows,
            "checkpoint_stop_rules": checkpoint_rule_rows,
        },
        "data_outputs": data_output_payload,
        "outputs_basis": {
            "raw_data_logging": data_output_payload.get("raw_data", []),
            "derived_outputs": data_output_payload.get("derived_metrics", []),
            "audit_metadata": data_output_payload.get("audit_metadata", []),
            "calculation_qc_notes": calculation_qc_rows,
            "references": answer_references,
        },
        "analysis_plan": analysis_plan_rows,
        "protocol_steps": protocol_steps,
        "data_acquisition": data_acquisition,
        "required_outputs": analysis_outputs,
        "warnings": warnings,
        "safety_checklist": safety_checklist,
        "approvals_required": approvals_required,
        "operator_notes": operator_notes,
        "trust_level": "draft_protocol",
        "requires_human_review": True,
        "ui_markdown": _build_ui_markdown(
            method=method,
            release_status=release_status,
            selected_cell_reference=selected_cell_reference,
            applied_constraints=applied_constraints,
            requested_conditions={
                "target_temperature_c": target_temperature_c,
                "charge_c_rate": requested_charge,
                "discharge_c_rate": requested_discharge,
                "run_length_field": requested_run_length_field,
                "run_length_basis": requested_run_length_basis,
                "run_length_value": requested_run_length_value,
                requested_run_length_field: requested_run_length_value,
                "form_factor": effective_form_factor,
                "thermal_chamber": thermal_chamber_rule["label"] if thermal_chamber_rule is not None else None,
                **normalized_method_inputs,
            },
            equipment_rule=equipment_rule,
            thermal_chamber_rule=thermal_chamber_rule,
            protocol_steps=protocol_steps,
            data_acquisition=data_acquisition,
            warnings=warnings,
            analysis_outputs=analysis_outputs,
            constraint_sources=constraint_sources,
            unresolved_registry_constraints=unresolved_registry_constraints,
            reference_check_policy=effective_reference_check_policy,
            answer_references=answer_references,
            safety_checklist=safety_checklist,
            pending_confirmation_rows=pending_confirmation_rows,
            execution_blockers=execution_blockers,
            lab_pretest_guidance={
                "global_defaults": pretest_global_defaults,
                "thermocouple_guidance": thermocouple_guidance,
                "objective_guidance": objective_guidance,
                "rpt_playbook": rpt_playbook,
            },
        ),
        "metadata": {
            "form_factor": effective_form_factor,
            "selected_cell_id": selected_cell_reference.get("cell_id") if selected_cell_reference else None,
            "chemistry_registry_id": chemistry_profile["id"] if chemistry_profile is not None else None,
            "thermal_chamber_rule_id": thermal_chamber if thermal_chamber_rule is not None else None,
        },
    }
