# Unified Protocol: SOC-OCV (Pseudo-OCV and GITT)

## Sources
- **[1]** Handbook: "Low C-rate cycle / Slow (dis)charge curve," in *Test methods for improved battery cell understanding v3.0*, p. 24.
- **[2]** Literature: M. Naylor Marlow, J. Chen, and B. Wu, "Degradation in parallel-connected lithium-ion battery packs under thermal gradients," *Communications Engineering*, vol. 3, no. 1, p. 2, 2024. (Supplement)
- **[4]** Literature: A. Barai, K. Uddin, M. Dubarry, et al., "A comparison of methodologies for the non-invasive characterisation of commercial Li-ion cells," *Progress in Energy and Combustion Science*, vol. 72, pp. 1-31, 2019.

## Overview
This method derives the thermodynamic equilibrium voltage (EMF/OCV) as a function of the cell's State of Charge (SOC) or capacity. The OCV is a fundamental thermodynamic property that carries information about phase transitions, solid solutions, and electrode stoichiometry [4]. It is essential for ECM battery modelling, State of Charge estimation, and degradation-mode fitting.

Because true thermodynamic equilibrium takes hours or days to reach at each point, evaluating the OCV curve is a trade-off between accuracy and time. The three predominant approaches are:
1. **Pseudo-OCV Method (Low C-rate Cycle):** A continuous, very slow charge and discharge (e.g., `C/25` or `C/50`) where dynamic effects are minimized. The true OCV is approximated by averaging the two curves [1, 4].
2. **GITT (Galvanostatic Intermittent Titration Technique):** Applying small discrete capacity steps followed by long relaxation periods (often >4 hours) until reaching < 5mV/h change. This provides the most accurate thermodynamic curve [4].
3. **OCV Degradation Mode Fitting:** Generating slow reference data specifically to match against half-cell PE and NE data, allowing estimation of Loss of Lithium Inventory (LLI) and Loss of Active Material (LAM) [2].

## Setup & Equipment Requirements
- **Hardware:** High-precision battery cycler and temperature chamber.
- **Environment:** Strictly `25 ± 2 °C` [1]. Temperature stability is critical because thermodynamic potentials vary strongly with temperature (due to entropy). Ensure the cell is fully acclimated before testing.
- **Measurement:** High-resolution data acquisition is required. Ensure recording at `1 minute` intervals, or whenever voltage changes by `1 mV` or temperature by `0.2 K` [1].
- **Pre-test State:** Cell MUST be fully charged/discharged exactly according to the standard cycle reference test right before starting.

## Protocol sequence: Pseudo-OCV (Standard)

1. **Preconditioning:** Ensure the cell is loaded under the standard cycle conditions. Let it rest for 2 hours to achieve thermal equilibrium.
2. **Slow Discharge:** Discharge the cell from 100% to the minimum allowed cell voltage using a constant current of `C/25` [1].
3. **Rest:** Rest the cell for at least 1 hour (4-12 hours is preferable for full relaxation).
4. **Slow Charge:** Charge the cell from 0% back to the maximum allowed cell voltage at `C/25` [1].
5. **Averaging:** Subtract the remaining overpotentials by taking the mean of the charge and discharge curves at each capacity point to estimate the thermodynamic EMF [1, 4].

## Protocol sequence: GITT (High-Fidelity Alternative)

Use this method when maximum thermodynamic accuracy or diffusion coefficient measurement is required [4].
1. **Pulse Step:** Apply a charge or discharge pulse (e.g., `1 C` or `C/10`) for a set duration equating to a specific SOC step (e.g., `5% SOC`).
2. **Relaxation Step:** Cut the current and allow the cell to rest until `dV/dt < 1 mV/h` (this can take several hours per step).
3. **Record OCV:** The final rested voltage is recorded as the thermodynamic OCV for that SOC.
4. **Iterate:** Repeat steps 1-3 until the voltage limits of the cell are reached.

## Analysis Outcomes & Model Constraints
- **Degradation Diagnostics (LLI / LAM):** Using the Pseudo-OCV data, the curve can be aligned to PE and NE half-cell curves. Shrinkage or slipping between these curves identifies the primary degradation mechanism (whether cathode-related, anode-related, or inventory loss) [2].
- **EMF Tracking:** Tracking the shift of the Pseudo-OCV curve between Beginning of Life (BOL) and End of Life (EOL) checkpoints is a non-invasive way to detect changes in accessible capacity outside of dynamic testing.
- **EVS Foundation:** The low-rate data recorded here is the direct input required for Incremental Capacity Analysis (ICA/EVS) [1, 4].
