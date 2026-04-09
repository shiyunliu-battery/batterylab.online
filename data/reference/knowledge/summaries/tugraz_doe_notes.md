# Design Of Experiments: Course Note

## Source

- IEEE reference: [Institute of Statistics, Graz University of Technology, "Design of Experiments," course notes. [Online]. Available: https://www.stat.tugraz.at/courses/files/DoE.pdf](https://www.stat.tugraz.at/courses/files/DoE.pdf)
- Stored source id: `tugraz_doe_notes`
- Evidence basis: user-supplied PDF summarized into page-linked evidence cards rather than storing the raw PDF inside the repository.

## Why This Source Matters To The System

This source is relevant to Battery Lab Assistant as a statistics and DOE theory foundation. It is not a battery-specific review of the literature, but it explains the mechanics of ANOVA, replication, randomization, blocking, Latin squares, factorial effects, interactions, and confounding. That makes it useful for:

- defining classical DOE concepts in user-facing explanations
- supporting blocked-factorial planning when the lab has nuisance variables such as channel, day, operator, or batch
- explaining why factorial designs are preferable to one-factor-at-a-time studies when interactions may matter
- clarifying what confounding and restricted randomization mean before the system recommends a more specific battery DOE template

## Relation To Existing DOE Battery Literature

- Use this source for general DOE mechanics and terminology: ANOVA, randomization, blocking, Latin squares, factorial effects, interaction, and confounding.
- Use `roman_ramirez_2022_doe_review` as the primary source when the question is battery-specific and requires guidance on design-family choice across charging, thermal, formulation, ageing, or parameter-identification studies.
- When both are relevant, the intended fusion rule is:
  - `tugraz_doe_notes` explains the statistical structure of the design.
  - `roman_ramirez_2022_doe_review` explains why one design family is more suitable for a battery problem than another.
- Do not let this course note override battery-specific evidence for questions such as OA versus D-optimal charging optimization, RSM versus screening in battery applications, or ECM-focused DOE roadmaps.

## Source-Level Summary

- The opening chapters present single-factor experiments as replicated, randomized studies analyzed with ANOVA. The note emphasizes random run order and explicit treatment effects before moving to more complex designs. See pp. 2-5.
- Randomization, blocking, and nuisance factors are treated as core design principles rather than optional analysis details. The note explains that randomization protects against unknown nuisance factors, while blocking removes the effect of known and controllable nuisance factors from treatment comparisons. See pp. 46-52.
- Latin square designs are presented as an extension of blocking when two nuisance sources need to be balanced simultaneously. The note stresses that rows and columns both represent restrictions on randomization and that the model is additive. See pp. 56-59.
- The factorial chapters emphasize that factorial experiments are more efficient than one-factor-at-a-time studies because they reuse all the data and can expose interactions. See pp. 72-79.
- A battery-themed two-factor factorial example is included for material type and operating temperature, which makes this source directly reusable for simple battery DOE explanations even though it is still a teaching example rather than a battery review. See pp. 76-79.
- The later chapters cover `2^k` factorial structures, blocking, and confounding. These sections are useful for lab situations where one full replicate cannot be completed under one batch, one day, or one setup condition, and some higher-order interactions may need to be confounded with blocks. See p. 100 and pp. 131-139.

## Evidence Cards Saved From This Source

- `tugraz_doe_notes_anova_randomization`: single-factor experiments, replication, random run order, and ANOVA framing, pp. 2-5
- `tugraz_doe_notes_blocking_rcbd`: nuisance factors, randomization, blocking, and randomized complete block design, pp. 46-52
- `tugraz_doe_notes_latin_square`: Latin square structure and assumptions for two nuisance factors, pp. 56-59
- `tugraz_doe_notes_factorial_basics`: factorial efficiency, interaction logic, and the battery material x temperature example, pp. 72-79
- `tugraz_doe_notes_2k_blocking_confounding`: `2^k` factorial structure, blocked replicates, and confounding logic, p. 100 and pp. 131-139

## How To Use This In Battery Lab Assistant

- Use the ANOVA, blocking, and factorial cards when the user asks what a DOE concept means or why the system is recommending randomization, blocking, or a factorial matrix.
- Use the blocking and `2^k` cards when the user has practical lab constraints such as different batches, testing days, fixtures, channels, or operators.
- Use the factorial card together with the Roman-Ramirez review when the user needs both classical DOE structure and battery-domain design guidance.
- Use the Latin square card only when two nuisance directions really need balancing and the user has enough experimental discipline to respect the design assumptions.

## Boundaries

- This is a teaching note, not a battery-specific literature review or a lab-specific SOP.
- It does not cover modern battery DOE choices such as Taguchi critique in battery papers, D-optimal charging design, or battery-specific parameter-identification workflows at the same depth as the Roman-Ramirez review.
- It should not be used as the sole evidence source for chemistry-specific limits, equipment constraints, charging policy optimization, or model-identification claims.
