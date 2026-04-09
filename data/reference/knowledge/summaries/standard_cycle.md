# Standard Cycle — Handbook Summary

## Primary Planning Role

- The standard cycle is the reference block used inside all other methods (RPTs, baselines, slow-curve entry state).
- It defines the reference capacity C₁ and the C/25 tail capacity used for SOH tracking.
- Treat it as the entry-state setter, not a standalone characterisation method.

## Locked Core Elements

- Discharge at 1C (or It-rate from datasheet) to Vmin — continuous CC.
- CV discharge tail at Vmin until current reaches C/25.
- 30 min rest.
- CC-CV recharge per manufacturer spec with C/25 cut-off current.
- 30 min rest.
- Second discharge (1C CC + CV tail) to obtain the C/25 capacity.
- Temperature: 25 ± 2 °C; room must be stable.

## Key Source Facts (pp. 16–17)

- The C/25 tail capacity is the distinguishing feature: it is almost independent of resistance growth during ageing, making it the preferred ageing-robust metric.
- If the declared capacity (not C₁) must be tracked, use It-rate from the datasheet instead of 1C.
- Test duration is approximately 8 h.

## Planner Notes

- When used as entry state for another method (e.g., SOC-OCV slow curve), the standard cycle must have been completed within the previous 48 h.
- The C₁ capacity from the first discharge provides the reference current for other methods that use C-rate multiples.

## Complementary Literature

- `barai_2019_noninvasive_characterisation_review` — capacity measurement methodology context.
