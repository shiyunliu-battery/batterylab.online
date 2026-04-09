# Workflow Map

This document is the quickest way to see which sub-functions already have a
real workflow behind them, which assets each workflow uses, and where the
remaining scaffold-only areas still exist.

## Active Workflow Overview

| Workflow | Main entry point | Controlled sources | Main output |
| --- | --- | --- | --- |
| Knowledge lookup | `load_battery_knowledge`, `describe_chemistry_profile` | chemistry registry, equipment rules, objective templates | KB-backed constraints and references |
| Method lookup | `list_pdf_test_methods`, `load_pdf_test_method` | method registry, handbook source index, evidence cards | method shortlist, chapter summary, evidence-backed method payload |
| Standard method planning | `plan_standard_test` | method registry, chemistry registry, selected cell context, lab defaults, equipment rules | structured draft protocol with references |
| Objective-driven protocol drafting | `design_battery_protocol` | objective templates, mapped default methods, selected cell context, lab defaults | objective-level draft protocol |
| Imported cell planning | `search_imported_cell_catalog` -> `plan_standard_test` / `design_battery_protocol` | imported cell catalog, formal governance filters | selected-cell-constrained planning |
| Uploaded datasheet draft planning | attachment -> `extract_uploaded_cell_datasheet` -> planning tool | uploaded thread file, OpenAI datasheet extractor, transient selected-cell context | draft planning constrained by uploaded cell limits |
| Uploaded datasheet review and promotion | attachment -> `extract_uploaded_cell_datasheet_to_provisional_asset` / `register_provisional_cell_asset` -> review -> promote | provisional cell asset store, manual cell assets, governance rules | reviewed asset promoted into formal planning surface |
| Equipment/manual lookup | `search_equipment_manual_knowledge`, `load_equipment_manual_knowledge` | equipment manual index and summaries | equipment-backed notes and operating boundaries |
| Knowledge evidence lookup | `search_knowledge_evidence_cards`, `load_knowledge_source` | unified knowledge source index and evidence cards | source-backed handbook or literature summaries |
| Post-test analysis | `run_cycle_data_analysis` | deterministic CSV parser and KPI rules | plots, KPI summary, starter analysis payload |
| Report drafting | `generate_lab_report_markdown` | protocol output, analysis output, report scaffold | markdown report draft |

## Workflow Details

### 1. Knowledge lookup

Use this when you want registry-backed constraints without generating a test
procedure yet.

1. User asks for chemistry, equipment, chamber, or objective constraints.
2. `load_battery_knowledge` loads the matching local registries.
3. The tool returns numeric references, a preflight planning marker, and
   citation-ready references.
4. The answer may summarize the constraints, but should not pretend to be a
   full executable protocol.

Main files:

- [battery_agent/tools.py](../battery_agent/tools.py)
- [data/registries/chemistry_registry.json](../data/registries/chemistry_registry.json)
- [data/kb/equipment_rules.json](../data/kb/equipment_rules.json)
- [data/kb/objective_templates.json](../data/kb/objective_templates.json)

### 2. Method lookup

Use this when you want to inspect the handbook-backed method library itself.

1. `list_pdf_test_methods` returns the curated structured methods plus chapter
   index.
2. `load_pdf_test_method` loads one method or raw chapter.
3. The returned payload includes handbook source information, evidence cards,
   and strict-reference policy.

Main files:

- [battery_agent/methods.py](../battery_agent/methods.py)
- [data/registries/method_registry.json](../data/registries/method_registry.json)
- [data/reference/knowledge/source_index.json](../data/reference/knowledge/source_index.json)
- [data/reference/knowledge/evidence_cards.json](../data/reference/knowledge/evidence_cards.json)

### 3. Standard method planning

Use this when the user already knows the method family, for example `soc_ocv`,
`pulse_hppc`, or `cycle_life`.

```mermaid
flowchart LR
    U["User request"] --> M["plan_standard_test"]
    M --> R["Resolve structured method"]
    R --> C["Merge chemistry / selected cell / uploaded datasheet constraints"]
    C --> E["Merge instrument and chamber rules"]
    E --> P["Return structured draft protocol"]
```

1. The tool resolves a structured method id.
2. Planning context is assembled from one of:
   - approved imported cell
   - uploaded datasheet candidate
   - chemistry registry fallback
3. Instrument rules and optional chamber rules are applied.
4. The tool returns a structured draft with:
   - protocol steps
   - citations
   - warnings
   - deviation review items
   - response policy

Main files:

- [battery_agent/tools.py](../battery_agent/tools.py)
- [battery_agent/methods.py](../battery_agent/methods.py)
- [battery_agent/planning_context.py](../battery_agent/planning_context.py)

### 4. Objective-driven protocol drafting

Use this when the user asks for a test objective, for example SOH ageing, HPPC,
or capacity characterization, but does not name the exact method id.

1. `design_battery_protocol` normalizes the objective.
2. The objective template resolves to a default structured method.
3. The same planning machinery as `plan_standard_test` is used underneath.
4. The final draft is returned with objective framing and review warnings.

Main files:

- [battery_agent/tools.py](../battery_agent/tools.py)
- [data/kb/objective_templates.json](../data/kb/objective_templates.json)

### 5. Uploaded datasheet -> draft planning

This is the main flow for a new user-supplied cell.

1. User uploads a datasheet attachment in chat.
2. Attachment text is extracted and stored as a thread file.
3. `extract_uploaded_cell_datasheet` produces a structured candidate with field
   evidence.
4. If the user chooses draft planning, the planner uses the uploaded cell as a
   transient selected-cell record.
5. Uploaded cell voltage/current limits override chemistry-family defaults when
   those cell-specific values exist.

Important boundary:

- This flow produces a draft planning surface, not a promoted formal asset.

Main files:

- [battery_agent/cell_datasheet_extraction.py](../battery_agent/cell_datasheet_extraction.py)
- [battery_agent/tools.py](../battery_agent/tools.py)
- [battery_agent/planning_context.py](../battery_agent/planning_context.py)

### 6. Uploaded datasheet -> admin review -> promotion

This is the governed path into the formal cell asset layer.

```mermaid
flowchart LR
    A["Uploaded datasheet"] --> B["Structured provisional candidate"]
    B --> C["Admin Review"]
    C --> D["Manual cell asset"]
    D --> E["Formal planning surface"]
```

1. A user uploads a datasheet.
2. The extracted candidate is sent to the provisional cell asset store.
3. A reviewer edits, approves, rejects, or requests changes.
4. Approved records are promoted to `manual_cell_assets.json`.
5. Formal governance decides whether the promoted record becomes
   planning-eligible.

Main files:

- [battery_agent/provisional_cell_assets.py](../battery_agent/provisional_cell_assets.py)
- [data/reference/cell_catalog/provisional_cell_assets.json](../data/reference/cell_catalog/provisional_cell_assets.json)
- [data/reference/cell_catalog/manual_cell_assets.json](../data/reference/cell_catalog/manual_cell_assets.json)

### 7. Imported cell planning

Use this when the cell already exists in the approved imported or manual
catalog.

1. `search_imported_cell_catalog` finds candidates.
2. The chosen `selected_cell_id` is loaded.
3. Planning uses selected-cell metadata first, then chemistry-family fallback if
   required.
4. Output remains a draft protocol, but it is better grounded than
   chemistry-only planning.

Main files:

- [battery_agent/cell_catalog.py](../battery_agent/cell_catalog.py)
- [battery_agent/planning_context.py](../battery_agent/planning_context.py)
- [data/reference/cell_catalog/cell_catalog.json](../data/reference/cell_catalog/cell_catalog.json)

### 8. Lab defaults workflow

This is how the system picks a default cycler, chamber, or EIS instrument
without making the user repeat it every turn.

1. User saves defaults in `Settings -> Lab Defaults`.
2. The frontend sends these defaults with new thread activity.
3. Planning tools read the thread state or hidden context file.
4. Explicit user inputs still override lab defaults.
5. Ambient-compatible plans can keep a default chamber as available context
   without treating it as a hard planning constraint.

Main files:

- [ui/src/app/components/ConfigDialog.tsx](../ui/src/app/components/ConfigDialog.tsx)
- [ui/src/app/lib/config.ts](../ui/src/app/lib/config.ts)
- [battery_agent/tools.py](../battery_agent/tools.py)

### 9. Equipment/manual and knowledge evidence lookup

These flows are complementary evidence flows, not formal protocol release
flows.

1. Search the manual or literature index.
2. Load the chosen source card.
3. Use the returned evidence to complement planning, explain reasoning, or
   support a reviewed deviation.

Main files:

- [data/reference/equipment_manuals/manual_index.json](../data/reference/equipment_manuals/manual_index.json)
- [data/reference/knowledge/source_index.json](../data/reference/knowledge/source_index.json)
- [data/reference/knowledge/evidence_cards.json](../data/reference/knowledge/evidence_cards.json)

### 10. Post-test analysis and report drafting

This is the current post-test path.

1. User supplies a normalized cycle-level CSV.
2. `run_cycle_data_analysis` computes starter KPIs and charts.
3. `generate_lab_report_markdown` turns structured outputs into a markdown draft.

Important boundary:

- This is still starter analysis and currently expects a normalized CSV, not raw
  Arbin/BioLogic/Neware exports.

Main files:

- [battery_agent/tools.py](../battery_agent/tools.py)
- [data/workflows/preprocessing](../data/workflows/preprocessing)
- [data/workflows/reports](../data/workflows/reports)

## Workflow Status

These workflows are already real:

- knowledge lookup
- method lookup
- standard method planning
- objective-driven protocol drafting
- imported cell planning
- uploaded datasheet draft planning
- provisional cell review and promotion
- equipment/manual lookup
- knowledge evidence lookup
- normalized CSV analysis
- report drafting

These areas still exist mostly as scaffold or partial workflow:

- raw instrument datasheet -> approved equipment asset promotion
- raw cycler export adapters for multiple vendor formats
- richer QA/release gates beyond draft protocol review
- ECM-first modeling workflow
- DOE campaign builder
