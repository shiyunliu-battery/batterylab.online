"""Knowledge-base loaders and workspace path helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from battery_agent.registries import (
    get_chemistry_definition,
    get_default_method_for_objective,
    get_method_definition,
    load_chemistry_registry,
    load_method_registry,
)
from battery_agent.workflow_assets import load_workflow_asset_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = REPO_ROOT / "data" / "kb"
SAMPLES_DIR = REPO_ROOT / "data" / "samples"

OBJECTIVE_ALIASES = {
    "performance": "performance",
    "performance_test": "performance",
    "performance_characterization": "performance",
    "rpt": "rpt",
    "reference_performance_test": "rpt",
    "reference_check": "rpt",
    "soh_modeling": "soh_modeling",
    "soh_modelling": "soh_modeling",
    "soh_training": "soh_modeling",
    "calendar_ageing": "calendar_ageing",
    "calendar_aging": "calendar_ageing",
    "calendar_ageing_test": "calendar_ageing",
    "cycle_life_test": "cycle_life",
    "cyclelife": "cycle_life",
    "hppc_screening": "hppc",
    "hybrid_pulse_power_characterization": "hppc",
    "pulse_test": "hppc",
    "pulse_power": "hppc",
    "rate_test": "rate_capability",
    "rate": "rate_capability",
    "capacity": "rate_capability",
    "capacity_test": "rate_capability",
    "capacity_testing": "rate_capability",
    "soc_ocv": "soc_ocv",
    "soc-ocv": "soc_ocv",
    "ocv": "soc_ocv",
    "ocv_curve": "soc_ocv",
    "low_c_rate_cycle": "soc_ocv",
    "slow_discharge_curve": "soc_ocv",
    # EIS
    "eis": "eis",
    "impedance": "eis",
    "impedance_test": "eis",
    "electrochemical_impedance": "eis",
    "electrochemical_impedance_spectroscopy": "eis",
    "electrochemical_impedance_test": "eis",
    # Drive cycle
    "drive_cycle": "drive_cycle",
    "drive_cycle_test": "drive_cycle",
    "wltp": "drive_cycle",
    "nedc": "drive_cycle",
    "bev_cycle": "drive_cycle",
    "phev_cycle": "drive_cycle",
    # Preconditioning
    "preconditioning": "preconditioning",
    "preconditioning_test": "preconditioning",
    "formation": "preconditioning",
    "break_in": "preconditioning",
    # Standard cycle
    "standard_cycle": "standard_cycle",
    "reference_cycle": "standard_cycle",
    # Constant power
    "constant_power": "constant_power_discharge",
    "constant_power_discharge": "constant_power_discharge",
    "ragone": "constant_power_discharge",
    # Dynamic stress test
    "dst": "dynamic_stress_test",
    "dynamic_stress": "dynamic_stress_test",
    "dynamic_stress_test": "dynamic_stress_test",
    # Thermal characterisation
    "thermal_characterisation": "thermal_characterisation",
    "thermal_characterization": "thermal_characterisation",
    "heat_generation": "thermal_characterisation",
    # Thermal impedance
    "thermal_impedance": "thermal_impedance",
    "thermal_impedance_test": "thermal_impedance",
    # Quasi-static thermal
    "quasi_static_thermal": "quasi_static_thermal",
    "quasi_static_thermal_tests": "quasi_static_thermal",
    "swelling": "quasi_static_thermal",
    "dilatometry": "quasi_static_thermal",
    # Ageing drive cycle
    "ageing_drive_cycle": "ageing_drive_cycle",
    "drive_cycle_ageing": "ageing_drive_cycle",
    "bev_ageing": "ageing_drive_cycle",
    # Constant voltage ageing
    "constant_voltage_ageing": "constant_voltage_ageing",
    "cv_ageing": "constant_voltage_ageing",
    "constant_voltage_storage": "constant_voltage_ageing",
}


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_objective_key(value: str) -> str:
    key = _normalize_key(value)
    return OBJECTIVE_ALIASES.get(key, key)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_instrument_rule(rule: Any) -> bool:
    return isinstance(rule, dict) and {
        "label",
        "max_current_a",
        "max_voltage_v",
    }.issubset(rule.keys())


def _resolve_named_rule(query: str, rules: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    key = _normalize_key(query)
    for rule_id, rule in rules.items():
        aliases = {_normalize_key(rule_id)}
        aliases.update(_normalize_key(alias) for alias in rule.get("aliases", []))
        if key in aliases:
            return rule_id, rule
    raise KeyError(query)


def _build_objective_template_from_method(method: dict[str, Any]) -> dict[str, Any]:
    recommended_defaults = method.get("recommended_defaults", {})
    protocol_defaults = method.get("protocol_template", {}).get("defaults", {})
    required_outputs = method.get("required_outputs", {})
    report_focus = list(required_outputs.get("graphs", [])) or list(required_outputs.get("tables", []))
    default_rest_minutes = (
        recommended_defaults.get("rest_minutes")
        or protocol_defaults.get("rest_minutes")
        or 30
    )
    default_log_interval_seconds = 60 if method.get("objective_key") == "soc_ocv" else 10

    return {
        "label": method.get("label", method["id"]),
        "description": method.get("intent", "Structured method fallback generated from the method registry."),
        "default_rest_minutes": default_rest_minutes,
        "default_log_interval_seconds": default_log_interval_seconds,
        "report_focus": report_focus[:3] or ["Method-specific outputs defined in the method registry."],
        "source": "method_registry_fallback",
        "method_id": method["id"],
    }


def _build_objective_template_from_pretest_guidance(
    key: str,
    guidance: dict[str, Any],
) -> dict[str, Any]:
    minimum_modules = list(guidance.get("minimum_modules", []))
    optional_modules = list(guidance.get("optional_modules", []))
    report_focus = minimum_modules[:3] or ["Lab-guidance-backed minimum test package."]

    return {
        "id": key,
        "label": guidance.get("label", key.replace("_", " ").title()),
        "description": guidance.get(
            "description",
            "Objective template synthesized from pretest assistant guidance.",
        ),
        "default_rest_minutes": int(guidance.get("default_rest_minutes", 30)),
        "default_log_interval_seconds": int(guidance.get("default_log_interval_seconds", 10)),
        "report_focus": report_focus,
        "source": "pretest_assistant_guidance",
        "minimum_modules": minimum_modules,
        "optional_modules": optional_modules,
    }


@lru_cache(maxsize=1)
def load_kb() -> dict[str, dict[str, Any]]:
    return {
        "chemistry_profiles": load_chemistry_registry(),
        "equipment_rules": _read_json(KB_DIR / "equipment_rules.json"),
        "objective_templates": _read_json(KB_DIR / "objective_templates.json"),
        "safety_checklists": _read_json(KB_DIR / "safety_checklists.json"),
        "pretest_assistant_guidance": _read_json(KB_DIR / "pretest_assistant_guidance.json"),
        "decision_relation_model": _read_json(KB_DIR / "decision_relation_model.json"),
    }


def get_chemistry_profile(chemistry: str) -> dict[str, Any]:
    return get_chemistry_definition(chemistry)


def get_equipment_rule(instrument: str) -> dict[str, Any]:
    key = _normalize_key(instrument)
    rules = load_kb()["equipment_rules"]
    rule = rules.get(key)
    if not _is_instrument_rule(rule):
        raise KeyError(f"Unknown equipment rule: {instrument}")
    return rule


def list_instrument_rule_keys() -> list[str]:
    rules = load_kb()["equipment_rules"]
    return sorted(key for key, rule in rules.items() if _is_instrument_rule(rule))


def get_thermal_chamber_rule(chamber: str) -> dict[str, Any]:
    chamber_rules = load_kb()["equipment_rules"].get("thermal_chambers", {})
    try:
        _, rule = _resolve_named_rule(chamber, chamber_rules)
    except KeyError as exc:
        raise KeyError(f"Unknown thermal chamber rule: {chamber}") from exc
    return rule


def list_thermal_chamber_rule_keys() -> list[str]:
    chamber_rules = load_kb()["equipment_rules"].get("thermal_chambers", {})
    return sorted(chamber_rules.keys())


def get_objective_template(objective: str) -> dict[str, Any]:
    key = normalize_objective_key(objective)
    kb = load_kb()
    templates = kb["objective_templates"]
    if key not in templates:
        objective_guidance = (
            kb.get("pretest_assistant_guidance", {})
            .get("objective_minimum_packages", {})
            .get(key)
        )
        if isinstance(objective_guidance, dict):
            return _build_objective_template_from_pretest_guidance(key, objective_guidance)
        method = get_default_method_for_objective(key)
        if method is None:
            try:
                method = get_method_definition(objective)
            except KeyError as exc:
                raise KeyError(f"Unknown objective template: {objective}") from exc
        return _build_objective_template_from_method(method)
    return templates[key]


def get_pretest_assistant_guidance() -> dict[str, Any]:
    return load_kb()["pretest_assistant_guidance"]


def get_decision_relation_model() -> dict[str, Any]:
    return load_kb()["decision_relation_model"]


def get_pretest_global_defaults() -> dict[str, Any]:
    return dict(get_pretest_assistant_guidance().get("global_defaults", {}))


def get_pretest_objective_guidance(objective: str) -> dict[str, Any] | None:
    key = normalize_objective_key(objective)
    guidance = (
        get_pretest_assistant_guidance()
        .get("objective_minimum_packages", {})
        .get(key)
    )
    return dict(guidance) if isinstance(guidance, dict) else None


def get_pretest_rpt_playbook() -> dict[str, Any]:
    return dict(get_pretest_assistant_guidance().get("rpt_playbook", {}))


def get_pretest_approved_equipment_defaults() -> dict[str, Any]:
    return dict(get_pretest_assistant_guidance().get("approved_equipment_defaults", {}))


def get_decision_relation_classes() -> dict[str, Any]:
    return dict(get_decision_relation_model().get("relation_classes", {}))


def get_authority_and_precedence_model() -> dict[str, Any]:
    return dict(get_decision_relation_model().get("authority_and_precedence", {}))


def get_requirement_strength_levels() -> list[str]:
    return list(get_decision_relation_model().get("requirement_strength_levels", []))


def get_decision_conflict_representation() -> dict[str, Any]:
    return dict(get_decision_relation_model().get("conflict_representation", {}))


def get_thermocouple_placement_guidance(form_factor: str | None) -> dict[str, Any]:
    guidance = get_pretest_assistant_guidance().get("thermocouple_placement", {})
    default_by_form_factor = guidance.get("default_by_form_factor", {})
    normalized_form_factor = normalize_objective_key(form_factor or "")

    if normalized_form_factor == "pouch":
        placement_key = "pouch"
    elif normalized_form_factor in {"cylindrical", "18650", "21700"}:
        placement_key = "cylindrical"
    elif normalized_form_factor in {"prismatic", "large_format", "large-format"}:
        placement_key = "large_format"
    else:
        placement_key = "general"

    placement_text = default_by_form_factor.get(
        placement_key,
        guidance.get("minimum_requirement"),
    )
    return {
        "minimum_requirement": guidance.get("minimum_requirement"),
        "placement_key": placement_key,
        "placement_text": placement_text,
    }


def chamber_required_for_temperature(target_temperature_c: float) -> bool:
    global_defaults = get_pretest_global_defaults()
    chamber_rule = global_defaults.get("environmental_chamber_required_outside_reference_window", {})
    nominal = float(chamber_rule.get("nominal_temperature_c", 25.0))
    tolerance_c = float(chamber_rule.get("tolerance_c", 2.0))
    return not (nominal - tolerance_c <= target_temperature_c <= nominal + tolerance_c)


def get_safety_checklist(objective: str, thermal_chamber: str | None = None) -> list[str]:
    key = normalize_objective_key(objective)
    checklists = load_kb()["safety_checklists"]
    general = list(checklists.get("general", []))
    specific = list(checklists.get(key, []))
    chamber_specific: list[str] = []
    if thermal_chamber:
        chamber_sections = checklists.get("by_thermal_chamber", {})
        try:
            _, chamber_rule = _resolve_named_rule(thermal_chamber, chamber_sections)
        except KeyError as exc:
            raise KeyError(f"Unknown thermal chamber checklist: {thermal_chamber}") from exc
        chamber_specific.extend(chamber_rule.get("general", []))
        chamber_specific.extend(chamber_rule.get(key, []))
    pretest_defaults = get_pretest_global_defaults()
    reference_temperature_c = pretest_defaults.get("reference_temperature_c")
    if isinstance(reference_temperature_c, (int, float)):
        general.append(
            f"Default lab reference temperature is {float(reference_temperature_c):.1f} C unless an approved test plan declares a reviewed deviation."
        )
    cv_termination = pretest_defaults.get("default_cv_termination_rule", {})
    terminate_when_any = list(cv_termination.get("terminate_when_any", []))
    if terminate_when_any:
        general.append(
            "Default CV termination rule: "
            + "; ".join(str(item) for item in terminate_when_any)
            + "; whichever occurs first."
        )
    chamber_rule = pretest_defaults.get("environmental_chamber_required_outside_reference_window", {})
    if chamber_rule:
        nominal = chamber_rule.get("nominal_temperature_c", 25)
        tolerance_c = chamber_rule.get("tolerance_c", 2)
        general.append(
            f"Any test outside {nominal} +/- {tolerance_c} C must use an environmental chamber."
        )

    merged = general + specific + chamber_specific
    deduped: list[str] = []
    seen: set[str] = set()
    for item in merged:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def resolve_sample_path(csv_path: str) -> Path:
    candidate = Path(csv_path)
    options = []

    if candidate.is_absolute():
        options.append(candidate)
    else:
        options.extend(
            [
                REPO_ROOT / candidate,
                SAMPLES_DIR / candidate,
                SAMPLES_DIR / candidate.name,
            ]
        )

    for option in options:
        if option.exists():
            return option.resolve()

    raise FileNotFoundError(f"Could not find CSV file: {csv_path}")


def list_demo_assets() -> dict[str, Any]:
    kb = load_kb()
    available_objectives = sorted(
        set(kb["objective_templates"].keys())
        | set(kb.get("pretest_assistant_guidance", {}).get("objective_minimum_packages", {}).keys())
    )
    return {
        "repo_root": str(REPO_ROOT),
        "sample_dir": str(SAMPLES_DIR),
        "sample_files": [path.name for path in sorted(SAMPLES_DIR.glob("*")) if path.is_file()],
        "chemistries": sorted(kb["chemistry_profiles"].keys()),
        "instruments": list_instrument_rule_keys(),
        "thermal_chambers": list_thermal_chamber_rule_keys(),
        "objectives": available_objectives,
        "methods": sorted(load_method_registry().keys()),
        "workflow_asset_groups": sorted(load_workflow_asset_registry().keys()),
        "decision_relation_model_version": kb.get("decision_relation_model", {}).get("version"),
    }
