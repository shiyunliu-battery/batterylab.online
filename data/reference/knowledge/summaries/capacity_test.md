# Unified Protocol: Capacity Test

## Sources
- **[1]** Handbook: "Test methods for battery cell performance," in *Test methods for improved battery cell understanding v3.0*, pp. 18-23.
- **[4]** Literature: A. Barai, K. Uddin, M. Dubarry, et al., "A comparison of methodologies for the non-invasive characterisation of commercial Li-ion cells," *Progress in Energy and Combustion Science*, vol. 72, pp. 1-31, 2019.

## Overview
The primary test intention is obtaining the cell capacity and energy content as a function of C-rate and temperature. 
While capacity tests are the most accessible characterisation method, the chosen rate and temperature must be tied to the intended application [4]. High-rate tests are simple and fast but mix kinetic limitations with true thermodynamic capacity. Temperature dependence dictates that higher temperatures generally improve kinetics and decrease impedance, thereby increasing the accessible capacity before a voltage cutoff is reached [4].

## Setup & Equipment Requirements
- **Hardware:** Battery cycler with sufficient current capacity, temperature chamber, and optional forced air (especially for >1 C rates to prevent limits).
- **Measurement:** 1-minute intervals, or whenever changing by 10 mV, 0.05 C, or 0.2 K [1].
- **Prerequisites:** Cell must be fully charged (e.g., standard cycle within 48h) or initially preconditioned.

## Protocol Sequence

1. **Thermal Soak:** Ensure the cell is at the target temperature. A rest of 60 minutes is applied before charging or discharging [1].
2. **Discharge Phase (CC or CC-CV):**
   - Apply constant current (CC) discharge until the minimum allowed cell voltage.
   - *Optional:* Continue with constant voltage (CV) discharge until the current decays to `C/25`. This verifies whether the total capacity is accessible despite kinetic limits [1].
3. **Rest:** Rest 60 minutes.
4. **Charge Phase (CC-CV):**
   - Apply constant current charge at the specified rate until the maximum voltage.
   - Apply constant voltage charge until current decays to `C/25` [1].
5. **Rest:** Rest 60 minutes.
6. **Rate/Temperature Iteration:** Repeat steps 2-5 for the specified matrix of conditions.

## Required Test Matrix

### C-Rates to Evaluate
- **Mandatory:** `1/5 C`, `1/2 C`, `1 C`, `2 C`
- **Optional (for dynamic scaling):** `5 C`, `10 C`, and `I_max`
- Apply the identical rate for both charge and discharge, unless limited by the manufacturer's maximum charge rate.

### Temperatures to Evaluate
- **Mandatory:** `5°C`, `25°C`, `45°C`
- **Optional (sub-zero):** `0°C`, `-10°C`, `-20°C` (subject to charge acceptance limits).
- Wait at least 2 hours when changing the chamber temperature between test blocks [1].

## Analysis Outcomes
- **Accessible vs Thermodynamic Capacity:** Higher rates reduce accessible discharge capacity due to increased overpotential ($\eta$) as governed by Butler-Volmer kinetics [4].
- **Peukert Exponent:** Derived by plotting discharge time vs current. The Peukert exponent helps estimate theoretical low-rate capacities.
- **Cycle Efficiency:** Coulombic and energy efficiencies between the applied charge and discharge blocks.
