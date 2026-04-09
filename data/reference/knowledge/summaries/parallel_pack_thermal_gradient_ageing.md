# Unified Protocol: Parallel-Pack Thermal Gradient Ageing

## Sources
- **[2]** Literature: M. Naylor Marlow, J. Chen, and B. Wu, "Degradation in parallel-connected lithium-ion battery packs under thermal gradients," *Communications Engineering*, vol. 3, no. 1, p. 2, 2024.

## Overview
Ageing cells strictly in isolation often underestimates the degradation a pack will experience in the field. When cells are connected in parallel and subjected to thermal gradients—common due to uneven cooling or edge effects—the resulting unequal temperatures cause divergent internal resistance growth. The cell string ages disproportionately.

This protocol measures the divergent ageing and current distribution of cells in parallel, explicitly controlling the thermal boundaries of each cell [2].

## Setup & Equipment Requirements

1. **Hardware:** A specialized `1S2P` (or `1SXP`) pack testing fixture capable of independently measuring branch currents (e.g. precise shunt resistors) and independently heating/cooling individual cell surfaces (e.g. Peltier elements and water blocks).
2. **Calibration:** 
   - Measure contact resistances on assembly and reassembly.
   - Calibrate individual branch-current shunts and verify busbar resistances.
   - Validate temperature-control uniformity on all cells under actual load prior to starting the test [2].
3. **Cell Pairing:**
   - Measure the 1kHz impedance ($R_0$) and capacity of all candidate cells.
   - Strictly pair cells with near-identical starting specs to form packs, ensuring any divergence is caused strictly by the thermal gradient, not manufacturing defects [2].

## Ageing Sequence: Method

### Start of Life Characterisation (SOL)
1. Subject each individual cell to reference capacity testing (`0.1 C`, `1 C`, `2 C`) and a modified HPPC sequence at reference temperature `20 °C` [2].
2. Form the paired `1S2P` pack and test the overall pack capacity at `20 °C`.

### Ageing Blocks
1. Assign packs to control thermal cases (e.g., both cells homogeneous at `32.5 °C`) and gradient cases (e.g., Cell A at `45.0 °C`, Cell B at `20.0 °C`, maintaining mean `32.5 °C`).
2. Subject the pack to continuous `2 C` cyclic steady-state charge and discharge. Record branch current distributions simultaneously [2].
3. Breakpoint: After `125 cycles` (or suitable interval), interrupt the ageing sequence.

### Diagnostic Breakpoints (RPT)
1. **Pack Discharge:** Measure dynamic capacities at the pack level under the thermal operating conditions.
2. **Disassembly:** Dissassemble the pack into single cells.
3. **Single-Cell RPT:** Equilibrate the cells back to `20 °C` and re-run the SOL Characterisation testing. Track isolated capacity fade and the divergence of HPPC bulk resistance.
4. **Reassembly:** Re-calculate contact resistance, rebuild the pack fixture, re-apply the gradient, and execute the next ageing block.

## Analytical Targets
- **Accessible Pack Capacity:** Determine the SOC deficit [2]. A pack with severely divergent resistance may never fully discharge the "healthy" cell because the string hits the global cutoff voltage earlier than an isolated cell would.
- **Current Split:** Record how branch current diverges away from cooler/higher-resistance cells.
- **Cathode vs Anode Limitation:** The positive feedback loop observed in gradients is often driven by low-temperature accelerated charge-transfer resistance on the cathode, contrasting with high-temperature accelerated Solid Electrolyte Interphase (SEI) growth [2].
