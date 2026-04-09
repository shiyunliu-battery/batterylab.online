# A Comparison Of Methodologies For The Non-Invasive Characterisation Of Commercial Li-Ion Cells: Literature Note

## Source

- IEEE reference: [A. Barai, K. Uddin, M. Dubarry, L. Somerville, A. McGordon, P. Jennings, and I. Bloom, "A comparison of methodologies for the non-invasive characterisation of commercial Li-ion cells," *Progress in Energy and Combustion Science*, vol. 72, pp. 1-31, 2019.](https://www.sciencedirect.com/science/article/pii/S0360128518300996)
- Stored source id: `barai_2019_noninvasive_characterisation_review`
- Evidence basis: user-supplied PDF summarized into page-linked evidence cards rather than storing the raw paper inside the repository.

## Why This Source Matters To The System

This review is one of the strongest theory-and-method sources for Battery Lab Assistant because it compares the major non-invasive electrical characterisation methods that battery engineers repeatedly rely on: capacity tests, GITT and pseudo-OCV, electrochemical voltage spectroscopy, pulse-power tests, EIS, and pulsed multisine tests. It does not only list the methods; it explains the physical basis, the common equations, the equipment requirements, the practical limitations, and the kinds of questions each method can answer.

That makes it useful for:

- method selection and experiment-planning guidance
- explaining the theory behind OCV, EVS, HPPC, and EIS results
- justifying why one test is better suited than another for modelling, diagnosis, or ageing work
- building future protocol templates and analysis modules with a stronger theoretical basis

## Why Treat This As A Primary Theory Source

- It is broader than a single case study and narrower than a generic electrochemistry textbook, which is exactly the right level for this system.
- It links practical test execution to physics, modelling, and degradation analysis.
- It explicitly compares trade-offs in time, equipment, interpretability, and application scope, which is valuable for an agent that must recommend methods under lab constraints.
- It ends with a method-comparison matrix that is directly reusable for system guidance and future workflow design.

## Relation To Existing Literature In The Repository

- Use `barai_2019_noninvasive_characterisation_review` as the default theory source when the user asks what a characterisation method means, why it works, what it measures, what equations support it, or how it compares with another non-invasive method.
- Use `naylor_marlow_2024_parallel_pack_thermal_gradients` when the question is about a specific pack-ageing case study, its diagnostic stack, or how a parallel-pack experiment was actually run.
- Use `roman_ramirez_2022_doe_review` when the question is about DOE family choice rather than measurement theory.
- When both are relevant, the intended fusion rule is:
  - `barai_2019_noninvasive_characterisation_review` explains the measurement physics and method boundaries.
  - the more specific paper explains the chemistry, pack, or workflow context in which those methods were applied.

## Core Formula And Theory Basis

### 1. Capacity depends on kinetics as well as thermodynamics

The review explains that accessible capacity decreases at higher current because overpotential increases and the cell reaches its voltage limit before all stored lithium can be accessed. The review frames this with the Butler-Volmer reaction-rate expression:

\[
i = i_0 \left( e^{\alpha_a F \eta / RT} - e^{-\alpha_c F \eta / RT} \right)
\]

This is used to explain why higher current density increases overpotential and reduces accessible discharge capacity. See pp. 3-4.

The temperature dependence of reaction rate is also described with an Arrhenius-type expression:

\[
A(T) = A_{\mathrm{ref}} \exp\left( \frac{E_A^{act}}{R}\left(\frac{1}{T_{\mathrm{ref}}} - \frac{1}{T}\right)\right)
\]

This underpins why higher temperature generally improves kinetics and reduces impedance. See p. 3.

### 2. OCV is a thermodynamic property, not just a voltage lookup table

For equilibrium electrode potential, the review references the Nernst-style relationship:

\[
E = E^0 - \frac{RT}{ze}\log\left(\frac{a_i^+}{a_i^-}\right)
\]

The main point is not the algebra alone, but that OCV carries information about phase transitions, solid solutions, and electrode stoichiometry. See pp. 6-8.

The paper also stresses that SoC needs careful definition and should not be casually mixed between rated-capacity, nominal-capacity, and thermodynamic meanings. See pp. 7-8.

### 3. Low-rate data can support both OCV and thermal modelling

When low-rate curves are used to infer OCV and thermal behavior, the review highlights the heat-generation split:

\[
\dot Q = I(V - OCV) - I T \frac{\partial OCV}{\partial T}
\]

This equation is used to show that the entropy term tied to \(\partial OCV/\partial T\) can be important and should not always be neglected. See p. 11.

### 4. EVS turns small voltage-shape changes into diagnostic information

The review treats electrochemical voltage spectroscopy as derivative analysis of low-rate voltage curves:

\[
IC = \frac{dQ}{dV}, \qquad DV = \frac{dV}{dQ}
\]

The key theoretical idea is that IC emphasizes phase-transition regions while DV more directly separates positive- and negative-electrode contributions in full-cell analysis. See pp. 12-15.

### 5. Pulse methods produce a time-dependent bulk resistance, not a single pure physical constant

For pulse-power tests, the review uses the familiar bulk definition:

\[
R_{\mathrm{pulse}} = \frac{\Delta V}{\Delta I}
\]

But it also warns that this resistance is an aggregate of multiple timescale contributions and changes with pulse duration, SoC, temperature, and current amplitude. See pp. 16-18.

### 6. EIS measures a frequency-dependent complex impedance

For sinusoidal perturbations, the review writes the impedance in complex form:

\[
Z(\omega) = \frac{V(\omega)}{I(\omega)} = Z_0\left(\cos\phi + i\sin\phi\right)
\]

This is the basis for Nyquist-plot interpretation, ECM fitting, and linking characteristic frequencies to electrochemical timescales. See pp. 18-20.

## Source-Level Summary

- Capacity tests remain the most accessible characterisation method, but the review argues that the chosen rate and temperature must be tied to the intended application. High-rate tests are simple and fast, but they mix kinetic limitations with thermodynamic capacity. See pp. 1-5 and 24.
- OCV-oriented methods form a continuum from full GITT to pseudo-OCV from low-rate cycling. The review treats this as a trade-off between accuracy, time, and modelling needs, rather than insisting on one universal procedure. See pp. 6-11 and 24.
- EVS methods, especially IC and DV, are presented as indispensable non-invasive diagnosis tools because they convert subtle voltage-shape changes into interpretable signatures of LLI, LAM, and resistance-related changes. See pp. 12-15.
- HPPC and related pulse tests are framed as practical and widely available, especially for ECM parameterisation and power capability work, but they only deliver a time-scale-dependent bulk resistance and cannot fully deconvolute internal processes. See pp. 16-18 and 23-24.
- EIS is positioned as the richest non-invasive impedance method, with strong support for dynamic modelling and degradation analysis, but it requires specialised equipment and careful setup. See pp. 18-24.
- The review repeatedly emphasizes that there is no universal test plan. Instead, test choice should be driven by objective, equipment, required data quality, and acceptable test duration. See pp. 22-24.

## Most Reusable Guidance For Battery Lab Assistant

- Do not recommend a test just because it is common; recommend it because its information content matches the user’s objective.
- Separate performance tracking from mechanism diagnosis. Capacity and power retention alone are not enough when the user is asking why a cell degraded.
- Use low-rate or GITT-like methods when the user truly needs thermodynamic information, OCV, EVS, or degradation diagnosis.
- Use HPPC when the user needs practical pulse resistance or ECM-oriented parameters, but be explicit that the reported resistance depends on pulse length and conditions.
- Use EIS when the user needs frequency-resolved dynamics or stronger degradation evidence, and warn about equipment and setup requirements.
- Prefer method combinations when the question spans performance, modelling, and degradation; the review makes it clear that no single non-invasive method answers everything well.

## Evidence Cards Saved From This Source

- `barai_2019_method_selection_framework`: method-comparison logic, trade-off framing, and summary-table guidance, pp. 1-2 and 22-24
- `barai_2019_capacity_test_theory`: capacity-test theory, current/temperature effects, and test-selection cautions, pp. 3-5 and 24
- `barai_2019_ocv_gitt_pseudoocv_foundations`: OCV thermodynamics, SoC definitions, GITT, pseudo-OCV, and associated equations, pp. 6-11
- `barai_2019_evs_foundations`: IC and DV principles, full-cell versus half-cell interpretation, and derivative-based theory, pp. 12-13
- `barai_2019_evs_degradation_modes`: LLI, LAM, and resistance interpretation using EVS, plus the clepsydra analogy and chemistry-specific cautions, pp. 13-15
- `barai_2019_pulse_hppc_theory`: HPPC theory, bulk resistance definition, pulse-duration sensitivity, and ECM use cases, pp. 16-18 and 21
- `barai_2019_eis_ecm_theory`: complex-impedance equations, Nyquist interpretation, ECM fitting, and EIS application boundaries, pp. 18-24

## How To Use This In Battery Lab Assistant

- Use the method-selection and summary-table cards when the user asks which non-invasive test is best for a given objective.
- Use the OCV, EVS, HPPC, and EIS cards when the user asks for theoretical explanations or formulas behind those methods.
- Use the EVS and EIS cards when the user asks how to move from simple performance tracking toward degradation diagnosis.
- Use this review as the default “why this method” literature layer before adding chemistry-specific or case-study-specific sources.

## Boundaries

- This is a Li-ion review, so it should not be treated as a sodium-ion-specific validation source without additional chemistry-specific evidence.
- It is strongest for non-invasive electrical characterisation methods and their theory. It is not a primary source for destructive post-mortem workflows or pack-specific thermal hardware.
- The paper compares methodologies and equations, but lab-specific execution still depends on your cell, instrument, safety constraints, and required accuracy.
