# Unified Protocol: Electrochemical Voltage Spectroscopy (EVS)

## Sources
- **[4]** Literature: A. Barai, K. Uddin, M. Dubarry, et al., "A comparison of methodologies for the non-invasive characterisation of commercial Li-ion cells," *Progress in Energy and Combustion Science*, vol. 72, pp. 1-31, 2019.

## Overview
Electrochemical Voltage Spectroscopy (EVS), typically encompassing Incremental Capacity Analysis (ICA) and Differential Voltage Analysis (DVA), is an indispensable non-invasive diagnostic methodology [4]. It converts slow voltage/capacity data into clear derivative spectra that amplify phase transitions (voltage plateaus) which are normally indistinguishable in a standard $V-Q$ curve.

Instead of measuring global capacity fade, EVS isolates specific thermodynamic changes within the internal chemistry.

## Theoretical Foundations
EVS takes the derivative of low-rate (Pseudo-OCV) cycle data.

### Incremental Capacity (IC)
$IC = \frac{dQ}{dV}$
- Emphasizes the phase-transition regions (plateaus) of the cell [4]. 
- Peaks in the IC curve indicate regions where a large amount of charge flows with minimal change in voltage. Shifts in peak area directly map to Loss of Active Material (LAM) and Loss of Lithium Inventory (LLI) [4].

### Differential Voltage (DV)
$DV = \frac{dV}{dQ}$
- Emphasizes the stoichiometric phase transitions (the transitions between plateaus).
- DV curves are especially useful for full-cell analysis because the full-cell $DV$ curve is a linear combination of the positive and negative electrode $DV$ curves ($DV_{full} = DV_{p} - DV_{n}$), allowing direct separation of the two electrode behaviors [4].

## Protocol Requirements

1. **Test Prerequisite:** EVS is not a physical test sequence itself, it is an analytical post-processing method applied to **Pseudo-OCV / slow discharge** data.
2. **Current Rate:** Data must be acquired at exceptionally low rates (typically `C/20` to `C/50`) to minimize the IR drop and dynamic overpotentials, keeping the cell near equilibrium [4].
3. **Data Quality:** High voltage resolution is strictly required (measurements accurate down to `< 1 mV`). Voltage noise will amplify enormously in the derivative, creating artificial noise spikes.

## Processing Workflow
1. Execute a strict Pseudo-OCV low-rate test (e.g., `C/25` charge and discharge at `25 °C`).
2. Subject the raw data to careful smoothing or filtering (e.g., moving average, Savitzky-Golay, or voltage-step binning) to prevent noise amplification [4].
3. Compute numeric derivatives $\frac{dQ}{dV}$ and $\frac{dV}{dQ}$.
4. Track specific identified peaks across the cell's lifespan (from Start-of-Life to End-of-Life).
5. Use the shift and area reduction of these peaks to uniquely identify:
   - **LLI:** Shift or shrinking of the primary lithium inventory peaks.
   - **LAM (PE or NE):** Dropping of specific characteristic peaks tied mathematically to the cathode or anode.
   - **Ohmic Resistance:** Shifting of the peaks along the voltage axis proportionally to the applied current.

## Method Constraints
- EVS processing requires careful differentiation from noise.
- It is highly chemistry-specific; interpreting the peaks requires baseline half-cell data for the specific active materials used [4].
