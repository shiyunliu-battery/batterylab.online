# Design Of Experiments Applied To Lithium-Ion Batteries: Literature Review Note

## Source

- IEEE reference: [L. A. Roman-Ramirez and J. Marco, "Design of experiments applied to lithium-ion batteries: A literature review," *Applied Energy*, vol. 320, art. no. 119305, 2022.](https://www.sciencedirect.com/science/article/pii/S0306261922006596#s0005)
- Stored source id: `roman_ramirez_2022_doe_review`
- Evidence basis: user-supplied PDF summarized into page-linked evidence cards rather than storing the raw paper inside the repository.

## Why This Source Matters To The System

This review is directly relevant to the DOE layer of Battery Lab Assistant. It does not provide one executable battery protocol, but it does explain how different DOE families should be chosen for screening, optimization, robust design, formulation work, charging studies, thermal studies, and parameter-identification workflows. That makes it useful for:

- DOE template selection and explanation
- research-assistant answers about when to use screening versus optimization
- charging and thermal-design planning discussions
- future ECM or electro-thermal parameter-identification workflows

## Paper-Level Summary

- The paper frames DOE as a structured alternative to one-factor-at-a-time experimentation for lithium-ion batteries, especially when multiple interacting variables matter. The review highlights battery use cases ranging from ageing and capacity studies to formulation, thermal design, charging, and parameterization. See pp. 1-3.
- Screening and optimization should not be mixed together. The review recommends screening first to reduce the factor space, then using response-surface or optimal designs when the real goal is optimization. See pp. 3-4 and p. 15.
- Taguchi and orthogonal arrays are common in the battery literature, but the review argues they are often overused for "optimization" even when they only reveal main effects or robustness trends. See pp. 4, 13-15, and 21.
- Mixture designs are the right fit when the variables are formulation proportions such as active material, conductive additive, and binder fractions. See pp. 4-5 and p. 9.
- DOE is also useful for charging, thermal design, and model parameter identification. For charging, the review argues that D-optimal or RSM designs can outperform orthogonal arrays when interactions or curvature matter. For parameter identification, the review describes evidence that DOE can reduce experimental time while preserving model accuracy. See pp. 12-16 and p. 21.
- The future-opportunity sections are especially useful for roadmap work in this project: manufacturing DOE, split-plot designs for hard-to-change factors, desirability functions for multiple responses, and pack-level ageing studies are all identified as underdeveloped areas. See pp. 20-21.

## Evidence Cards Saved From This Source

- `roman_ramirez_2022_doe_overview`: broad DOE motivation and experiment-design framing, pp. 1-3
- `roman_ramirez_2022_screening_designs`: screening designs, Plackett-Burman, and DSD guidance, p. 3 and pp. 20-21
- `roman_ramirez_2022_rsm_optimization`: RSM, CCD, BBD, and the critique of OA-based "optimization", pp. 3-4, 15, and 21
- `roman_ramirez_2022_taguchi_robust_design`: Taguchi/RPD strengths and limitations, pp. 4, 13-15, and 21
- `roman_ramirez_2022_mixture_formulation`: formulation-focused mixture design guidance, pp. 4-5 and 9
- `roman_ramirez_2022_thermal_design`: thermal-design use cases and DOE response variables, pp. 12 and 14
- `roman_ramirez_2022_charging_design`: DOE for pulse charging and multi-stage CC charging, pp. 12-14 and 21
- `roman_ramirez_2022_parameter_identification`: DOE for model parameter estimation and identifiability, pp. 15-16
- `roman_ramirez_2022_future_opportunities`: manufacturing, blocking, desirability, and pack-level ageing opportunities, pp. 20-21

## How To Use This In Battery Lab Assistant

- Use the overview, screening, and RSM cards when the user is asking which DOE family fits a proposed battery study.
- Use the charging and thermal cards when the user wants DOE-backed experimental design ideas tied to charger settings or thermal-management factors.
- Use the parameter-identification card when the modeling roadmap shifts toward ECM, electro-thermal fitting, or experiment-budget planning.
- Use the future-opportunities card for roadmap answers, especially when the user asks what higher-value DOE assets still need to be built.

## Boundaries

- This is a literature review, so it should not be treated as a lab-specific SOP or as a direct substitute for your equipment manuals and safety rules.
- The paper is strongest for design-choice guidance and critical comparison of DOE families. It is weaker as a source of exact execution settings for any one battery chemistry, instrument, or commercial cell model.
