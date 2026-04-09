# Degradation In Parallel-Connected Lithium-Ion Battery Packs Under Thermal Gradients: Literature Note

## Source

- IEEE reference: [M. Naylor Marlow, J. Chen, and B. Wu, "Degradation in parallel-connected lithium-ion battery packs under thermal gradients," *Communications Engineering*, vol. 3, no. 1, p. 2, 2024.](https://www.nature.com/articles/s44172-023-00153-5)
- Stored source id: `naylor_marlow_2024_parallel_pack_thermal_gradients`
- Evidence basis: user-supplied main article PDF plus supplementary-information PDF summarized into page-linked evidence cards rather than storing the raw PDFs inside the repository.

## Why This Source Matters To The System

This source is highly relevant to Battery Lab Assistant when the user is asking about pack-level ageing, thermal gradients in parallel strings, current sharing, or how to combine multiple diagnostics into one degradation study. The main article provides the pack-level mechanistic story, while the supplement contains most of the reusable experimental-process detail. Together they are useful for:

- research-assistant answers about why thermal gradients can accelerate divergence in parallel packs
- protocol planning for pack-level ageing studies with controlled thermal boundaries
- analysis guidance for combining current distribution, HPPC, EIS, OCV fitting, and post-mortem evidence
- report writing where the user needs a mechanistic explanation rather than only a trend summary

## Relation To Existing Literature In The Repository

- Use `roman_ramirez_2022_doe_review` when the question is mainly about DOE family choice, such as screening versus optimization or OA versus D-optimal.
- Use this Naylor-Marlow source when the question is about the battery-domain content of a parallel-pack ageing experiment: how the packs were built, what was measured, what the intermediate diagnostics were, and how the degradation mechanism was interpreted.
- When both are relevant, the intended fusion rule is:
  - `roman_ramirez_2022_doe_review` explains how to structure a DOE for pack-level ageing or thermal-gradient studies.
  - `naylor_marlow_2024_parallel_pack_thermal_gradients` explains what a technically credible battery experiment and diagnostic stack can look like in that domain.
- For OCV-fitting theory in isolation, this paper is useful but still secondary to the Birkl-style half-cell alignment literature cited inside the supplement. If the system later needs generic OCV-fitting guidance, those primary OCV-model papers should also be curated.

## Paper-Level Summary

- The paper studies six surface-cooled 1S2P lithium-ion pouch-cell packs aged under homogeneous and heterogeneous thermal boundary conditions spanning 20-45 C, and shows that thermal gradients can drive divergent current sharing and more damaging pack-level ageing than homogeneous operation at the same mean temperature. See article pp. 1-2 and 5-8.
- The main performance signal is not just static cell-capacity fade. The paper separates dynamic accessible pack capacity from static reference capacity and shows that current heterogeneity and end-of-discharge SOC deficit can make pack-level energy loss look much worse than the underlying cell-capacity loss alone. See article pp. 4 and 8-11.
- A key mechanistic claim is that low-temperature operation accelerates growth in the longer-time-constant resistance associated with cathode charge-transfer processes, while high temperature mainly accelerates LLI and SEI-related growth. That means cathode-related impedance divergence can create a positive-feedback loop in parallel strings under thermal gradients. See article pp. 5-7 and 11-14, plus supplement pp. 19-21.
- The paper is especially valuable because it does not rely on one diagnostic alone. The authors combine branch-current measurement, pack and cell capacity tests, HPPC, EIS, OCV-based degradation-mode fitting, and post-mortem cathode imaging before making mechanistic claims. See article pp. 3 and 11-14, plus supplement pp. 9-20 and 22.

## What The Supplement Adds

- The supplement contains the most reusable experimental process detail: cell screening and pairing, Peltier-based surface-temperature control, shunt-resistor calibration, contact-resistance checks, and temperature-uniformity validation. See supplement pp. 1-6.
- It also gives a reusable pack-ageing workflow: start-of-life cell characterization, modified HPPC across SOC, 2 C pack ageing, disassembly every 125 cycles for repeated single-cell diagnostics, and end-of-life EIS. See article p. 3 and supplement pp. 1-6.
- The OCV-diagnostic section is detailed enough to support future guidance work. It describes half-cell fabrication, p-OCV measurement, full-cell low-rate reference measurements, OCV-model fitting, and how LLI, LAMCa, and LAMAn were estimated and validated. See supplement pp. 9-18.
- The supplement also clarifies the boundaries of the diagnostic interpretation: the OCV model cannot distinguish lithiated versus delithiated active-material loss, post-mortem evidence is qualitative, and some fitted quantities are less reliable where the anode OCV curve is flat. See supplement pp. 14-20.

## Experimental Process, Step By Step

### A. Cell intake and pairing

1. Start from a larger batch of nominally identical cells and measure start-of-life capacity and impedance for each candidate cell.
2. Remove outliers with clearly higher resistance before forming packs.
3. Pair the remaining cells so that each 1S2P pack starts with very small differences in both `R0` and capacity.

Why this matters:
- The authors were deliberately trying to isolate thermal-gradient effects rather than letting large start-of-life mismatch dominate the result.
- This is a good guidance pattern for any pack-comparison study where you want temperature or topology to be the main experimental variable.

Evidence:
- article p. 3
- supp. pp. 1-2

### B. Build and validate the thermal-gradient rig

1. Use a pack fixture that can impose controlled surface temperatures on each cell branch.
2. Calibrate branch-current shunts and busbar resistances rather than relying only on nominal values.
3. Check contact resistance after assembly and again after repeated disassembly/reassembly.
4. Validate temperature-control performance under load and no-load conditions before starting the ageing campaign.

Why this matters:
- The paper makes the fixture and measurement chain part of the experiment, not just background hardware.
- The thermal-gradient claim would be much weaker without explicit validation of temperature control and current measurement.

Evidence:
- article p. 3
- supp. pp. 2-6

### C. Run start-of-life characterization on cells

1. Thermally equilibrate cells at `20 C` before characterization.
2. Measure capacity at `0.1 C`, `1 C`, and `2 C`.
3. Run a modified HPPC sequence:
   - charge at `1 C` with CC-CV to `4.2 V`
   - discharge to `90% SOC` at `0.25 C`
   - rest `60 min`
   - apply `18 s` charge and discharge pulses at `0.2 C`, `1 C`, and `3 C`
   - rest `60 s` between pulses
   - step down another `10% SOC` and repeat until `2.7 V` or 9 pulse blocks

Why this matters:
- This gives both low-rate reference information and pulse-resistance information before the packs are aged.
- The HPPC design is important because later claims about resistance divergence are compared back to these controlled checkpoints.

Evidence:
- article p. 3
- supp. pp. 1-2

### D. Assemble packs and run pack start-of-life checks

1. Assemble the selected cell pairs into `1S2P` packs.
2. Repeat pack-level capacity characterization under a controlled surface temperature of `20 C`.
3. Define the thermal cases before ageing:
   - homogeneous packs at `20.0`, `32.5`, and `45.0 C`
   - heterogeneous packs with mean `32.5 C` and gradients of `+25.0`, `-12.5`, and `-25.0 C`

Why this matters:
- The comparison is not just “cold vs hot”; it also separates homogeneous-temperature ageing from gradient-driven divergence at the same mean temperature.

Evidence:
- article p. 3
- article Table 1 on p. 4

### E. Age the packs in repeated breakpoint blocks

1. Age each pack under a constant-current `2 C` regime referenced to nominal pack capacity.
2. For each ageing block:
   - charge at `1 C` CC-CV to `4.2 V`
   - current cutoff `0.01 C`
   - rest `60 min`
   - continue the constant-current ageing sequence
3. After every `125 cycles`, stop ageing and disassemble the pack.
4. Re-run the single-cell characterization workflow.
5. Reassemble the pack and repeat.
6. Continue until `2000 total 2 C cycles`.

Why this matters:
- This breakpoint structure is probably the clearest reusable process contribution of the paper.
- It turns one long ageing test into a sequence of linked pack and cell snapshots, which is why the later mechanism discussion is much stronger than a simple end-of-life comparison.

Evidence:
- article p. 3
- supp. p. 8

### F. Add end-of-life and offline diagnostics

1. At end-of-life, collect EIS at matched SOC and voltage conditions to verify the observed resistance changes.
2. Use low-rate reference discharge data for OCV-based degradation-mode fitting.
3. Support electrochemical interpretation with post-mortem electrode imaging.

Why this matters:
- The paper avoids over-trusting one diagnostic.
- HPPC localizes resistance changes in the time domain, EIS helps decompose impedance behavior, OCV fitting estimates degradation-mode balance, and post-mortem imaging gives physical plausibility checks.

Evidence:
- article pp. 11-14
- supp. pp. 9-22

## Most Reusable Guidance From The Experimental Process

- Pair cells tightly before pack ageing if the goal is to isolate thermal-gradient or topology effects.
- Treat fixture calibration, shunt calibration, and contact-resistance consistency as part of the experiment design, not as setup trivia.
- Use repeated breakpoint characterization if you want to connect pack-level behaviour back to cell-level mechanisms.
- Keep both dynamic pack metrics and static reference metrics; otherwise you can miss how SOC imbalance is eroding accessible energy.
- If the goal is mechanism attribution, build a multimodal stack instead of relying on only capacity fade or only impedance.

## Evidence Cards Saved From This Source

- `naylor_marlow_2024_parallel_pack_ageing_case`: pack-level thermal-gradient ageing problem framing and divergent versus convergent degradation, article pp. 1-2, 5-8, and 14
- `naylor_marlow_2024_experimental_sequence`: step-by-step experimental sequence from cell pairing through breakpoint ageing and end-of-life diagnostics, article p. 3, article p. 11, and supp. pp. 1-9
- `naylor_marlow_2024_pack_protocol_breakpoints`: reusable pack-ageing and periodic-characterization workflow, article p. 3 and supplement pp. 1-6 and 8
- `naylor_marlow_2024_test_bench_measurement_guidance`: thermal-control fixture, shunt calibration, contact checks, and temperature-validation guidance, article p. 3 and supplement pp. 2-6
- `naylor_marlow_2024_current_split_soc_deficit`: current-distribution heatmaps and SOC-deficit logic for explaining accessible-capacity loss, article pp. 6-11 and supplement pp. 8-9
- `naylor_marlow_2024_cathode_impedance_feedback`: temperature-dependent cathode resistance growth as the driver of divergent ageing, article pp. 5-7 and 11-14 and supplement pp. 19-21
- `naylor_marlow_2024_ocv_model_workflow`: half-cell OCV workflow, fitting equations, and degradation-mode extraction logic, article p. 11 and supplement pp. 9-18
- `naylor_marlow_2024_multimodal_diagnostics_stack`: how HPPC, EIS, OCV fitting, and post-mortem evidence are combined into one degradation argument, article pp. 11-14 and supplement pp. 9-22

## How To Use This In Battery Lab Assistant

- Use the pack-ageing, current-split, and cathode-impedance cards when the user asks why thermal gradients are dangerous in parallel packs or why accessible capacity can collapse faster than static capacity.
- Use the protocol and test-bench cards when the user wants to design a controlled pack-level ageing experiment or asks what measurements should be included at each breakpoint.
- Use the OCV-model and multimodal-diagnostics cards when the user asks how to combine low-rate reference data, HPPC, EIS, and post-mortem evidence into a mechanistic degradation workflow.
- Fuse this source with DOE literature when the user asks not only how such a study was run, but also how to plan a more efficient or more formally designed version of the same study.

## Boundaries

- This is a strong battery-domain case study and methods source, but it is not a universal SOP for every chemistry, form factor, or cooling architecture.
- The experimental hardware is specialized: surface-cooled 1S2P pouch-cell packs with custom Peltier control and branch-current sensing.
- The OCV fitting workflow is powerful for offline diagnosis, but the supplement itself is clear that some degradation modes cannot be uniquely separated from OCV data alone.
