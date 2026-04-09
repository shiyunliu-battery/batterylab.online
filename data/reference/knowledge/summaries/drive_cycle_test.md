# Drive Cycle (Performance) — Handbook Summary

## Primary Planning Role

- Use this chapter as the usage-profile execution reference for drive-cycle performance testing.
- Keep the charge–pause–profile–repeat loop visible even when the profile family is customised.
- The profile family (WLTP, NEDC, USABC, custom BEV/PHEV) is a review-controlled choice.

## Locked Core Elements

- Standard-cycle precharge before the first profile run.
- Drive-cycle profile replay under constant condition until Vmin or selected range exhausted.
- Recharge after each profile repetition.
- Temperature at 25 ± 2 °C for baseline; field-temperature tests require reviewed extension.
- Detailed data logging: current, voltage, temperature at ≥ 1 Hz cadence throughout the profile.

## Key Source Facts (pp. 49–50)

- The chapter describes the drive-cycle performance test as a complement to the capacity test for application-facing energy estimation.
- The test distinguishes the energy delivered under realistic current dynamics from steady-state capacity measurements.
- Equipment: programmable battery tester with profile replay capability, temperature sensors, temperature chamber.

## Planner Notes

- This method is distinct from the ageing drive-cycle method (chapter ageing_effects__drive_cycle): the performance version is a characterisation test, not a life test.
- Regeneration efficiency can be estimated if the profile includes regen phases. Confirm instrument supports bipolar operation at the rated regen current.

## Complementary Literature

- None declared for this chapter. Pair with `roman_ramirez_2022_doe_review` if building a multi-temperature or multi-profile test matrix.
