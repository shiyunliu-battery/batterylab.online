# Dynamic Stress Test (DST) — Handbook Summary

## Primary Planning Role

- Use this chapter as the core executable reference for DST profile replay and transient characterisation.
- The 360 s continuous-profile logic is locked; do not invent alternative automotive profiles without review.
- Scaling-basis choice (power vs current, absolute vs normalised) remains review-controlled.

## Locked Core Elements

- Standard-cycle precharge before the DST run.
- 360 s continuous DST profile; profile must not be truncated or modified without review.
- Repeat until the cell reaches the lower voltage cutoff or the selected SOC range is exhausted.
- Recharge between profile repetitions.
- Temperature at 25 ± 2 °C for baseline; other conditions require review.

## Key Source Facts (pp. 28–30)

- The DST profile was originally defined by the US Department of Energy / USABC for EV cell screening.
- The test captures transient voltage response, energy throughput per profile, and temperature rise under realistic load dynamics.
- Equipment: programmable battery tester capable of dynamic current or power profile replay, temperature sensors.

## Planner Notes

- The scaling basis (e.g., power-normalised to rated capacity vs absolute current) must be declared before the test.
- Back-to-back DST blocks can serve as a lightweight ageing profile if used as part of a drive-cycle ageing campaign.

## Complementary Literature

- None declared for this chapter. Use `roman_ramirez_2022_doe_review` for DOE guidance if running a DST-based ageing matrix.
