# Ageing Drive Cycle — Handbook Summary

## Primary Planning Role

- Use this chapter as the core execution frame for drive-cycle ageing campaigns (BEV or PHEV/HEV profiles).
- The initial check-up before the first ageing block and the periodic checkpoint-loop are locked.
- Profile family choice, breakpoint cadence, and reduced intermediate check-up scope are all review-controlled.

## Locked Core Elements

- **Initial check-up** (baseline RPT bundle) before the first ageing block — mandatory, not optional.
- **Ageing block**: drive-cycle profile replay for the declared cycle count or elapsed-time block.
- **Checkpoint RPT** at each declared breakpoint: core capacity + pulse bundle; reduced set for intermediate, full for end of life.
- **Continue-or-stop decision** explicitly documented at each checkpoint.
- Temperature at selected ageing temperature; RPT check-ups return cell to reference temperature (typically 25 °C or 30 ± 3 °C).

## Key Source Facts (pp. 54–57)

- The chapter explicitly allows a reduced intermediate check-up versus the initial full bundle, but the reduced set must still cover capacity, resistance, and power capability.
- Breakpoint cadence examples: every 100 cycles or every 14–28 days.
- Condition-based trigger: advance the next checkpoint if capacity fade is projected to exceed 1% before the next planned interruption.
- Equipment: programmable cycler with profile replay, temperature chamber, temperature sensors.

## Planner Notes

- Do not run the profile beyond the declared block without an explicit continue decision.
- Use `naylor_marlow_2024_parallel_pack_thermal_gradients` for guidance on pack-level or parallel-string ageing experiments.
- Use `roman_ramirez_2022_doe_review` for DOE matrix design (temperature, SOC window, profile family choices).

## Complementary Literature

- `roman_ramirez_2022_doe_review`
- `naylor_marlow_2024_parallel_pack_thermal_gradients`
- `barai_2019_noninvasive_characterisation_review`
