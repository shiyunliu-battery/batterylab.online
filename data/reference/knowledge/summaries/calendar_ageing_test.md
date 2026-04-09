# Calendar Ageing Test — Handbook Summary

## Primary Planning Role

- Use this chapter as the primary executable reference for SOC-temperature storage campaigns with periodic 25 °C check-ups.
- The 25 °C check-up framing, target-SOC setting, return-to-25-°C hold (~5 h), and residual discharge are all locked.
- Matrix breadth, check-up periodicity, and reference-capacity definition remain review-controlled.

## Locked Core Elements

- **Baseline 25 °C check-up** before the first storage block (mandatory).
- **Target SOC** setting at 25 °C before each storage block (using reference-capacity logic).
- **Storage block** at selected SOC and temperature for the declared elapsed-time interval.
- **Return to 25 °C** until thermal equilibrium (~5 h typical hold; extend if needed).
- **Residual discharge** to Vmin before the next 25 °C check-up sequence.
- Stop criterion: SOH ≤ 80%, storage duration ≥ 6–12 months, or visible degradation.

## Key Source Facts (pp. 58–61)

- Adapt storage duration so the irreversible capacity loss between two check-ups stays at or below ~5%.
- Typical breakpoint examples: 45 °C every 6 weeks; 60 °C every 4 weeks; 25 °C every 8 weeks.
- Recommended 2–3 cells per calendar condition for reproducibility.
- Pre-checkpoint hold: return to 25 °C for ~5 h (source-backed example; extend if cell has not equilibrated).
- Equipment: battery tester for check-ups, temperature chamber, compression plate if required by cell format.

## Planner Notes

- Keep charge-retention (reversible) and irreversible capacity fade measurements strictly separate in analysis.
- Use `roman_ramirez_2022_doe_review` to rationalise the matrix breadth and selected storage conditions.

## Complementary Literature

- `roman_ramirez_2022_doe_review`
- `naylor_marlow_2024_parallel_pack_thermal_gradients`
- `barai_2019_noninvasive_characterisation_review`
