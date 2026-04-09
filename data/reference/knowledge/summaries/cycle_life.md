# Unified Protocol: Cycle Life and Pack Ageing

## Sources
- **[1]** Handbook: "Cycle life test," in *Test methods for improved battery cell understanding v3.0*, p. 53.
- **[2]** Literature: M. Naylor Marlow, J. Chen, and B. Wu, "Degradation in parallel-connected lithium-ion battery packs under thermal gradients," *Communications Engineering*, vol. 3, no. 1, p. 2, 2024.

## Overview
The objective of a cycle life test is to assess lifetime under specific use conditions (varying current, environmental temperature, voltage window, and time). 
While standard cell-level cycle life tests identify baseline degradation, pack-level testing (e.g., in parallel configurations) reveals how thermal gradients cause divergent current sharing, SOC drift, and accelerated pack-level failure compared to isolated cell testing [2].

**Key Principle:** The core of any cycle life test is not just the continuous iteration, but the **periodic interruption** of ageing for Reference Performance Tests (RPTs) that track capacity, pulse resistance, and ideally OCV/EIS to separate overall capacity fade into mechanistically distinct factors (e.g. static cell capacity loss vs accessible pack energy loss) [1, 2].

## Setup & Equipment Requirements
- **Hardware:** Battery cyclers, structured pack fixtures (if testing packs), and temperature chambers.
- **Validation (For Pack Testing):** The fixture and measurement chain must be treated as part of the experiment. Shunt resistors, busbar resistances, and thermal gradients must be strictly calibrated and verified under load before the test begins [2].
- **Cell Pairing (For Pack Testing):** Screen cells at Start-of-Life (SOL) to ensure candidates are matched in $R_0$ and capacity before forming the parallel pack, isolating topology/thermal effects from baseline manufacturing variance [2].

## Protocol Sequence

### 1. Start-of-Life Characterisation
Run the baseline reference metrics to establish the initial condition (BOL):
- Capacity test (at low and use-case rates).
- Modified HPPC or standard pulse test to establish $R_0$ and dynamic capability.
- (Optional) Initial OCV and EIS for later degradation mode fitting.

### 2. Ageing Block
Apply the designated usage profile. 
- *Example (Naylor Marlow Pack Workflow):* Continuous `2 C` cyclic charge/discharge at the target ambient or gradient-controlled temperature [2].
- Ageing blocks should be structured logically (e.g., blocks of `100 - 125 cycles`).

### 3. Disassembly & Checkpoint (For Pack Tests)
- Interrupt the ageing block.
- For pack tests addressing cell-level causality, **disassemble the pack** (if safe design permits) down to the series/parallel elements.

### 4. Reference Performance Test (RPT) Breakpoint
- Return the cells to reference room temperature (e.g., `20 °C` or `25 °C`) and allow multi-hour thermal equilibration.
- Repeat the characterisation block (Capacity + Pulse/HPPC). 
- *Crucial Diagnostic:* Tracking dynamic pack capacity vs underlying static cell capacity highlights when SOC imbalance (rather than just active material loss) is eroding pack energy [2].

### 5. Reassembly and Iteration
- Detail any contact resistance changes if reassembled.
- Resume the next Ageing block. Iterate until End of Life criteria (e.g. 80% initial capacity).

## Analysis Outcomes
- **Cathode Impedance Feedback:** Expect to see that lower temperatures may accelerate charge-transfer resistance growth on the cathode, while higher temperatures drive SEI/LLI loss. In parallel strings, this creates a feedback loop of current divergence [2].
- **SOH Estimation:** The extracted capacity and resistance trends from the RPTs fuel State of Health tracking models [1].
