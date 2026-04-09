# Unified Protocol: Pulse Test / HPPC

## Sources
- **[1]** Handbook: "Pulse test," in *Test methods for improved battery cell understanding v3.0*, pp. 31-37.
- **[2]** Literature: M. Naylor Marlow, J. Chen, and B. Wu, "Degradation in parallel-connected lithium-ion battery packs under thermal gradients," *Communications Engineering*, vol. 3, no. 1, p. 2, 2024. (Supplement)
- **[4]** Literature: A. Barai, K. Uddin, M. Dubarry, et al., "A comparison of methodologies for the non-invasive characterisation of commercial Li-ion cells," *Progress in Energy and Combustion Science*, vol. 72, pp. 1-31, 2019.

## Overview
The Pulse Test, often known as Hybrid Pulse Power Characterization (HPPC), evaluates the power capability of the battery under dynamic charge and discharge conditions across varying C-rates, SOCs, and temperatures [1].

**Theoretical Foundation:** Unlike EIS which resolves processes in the frequency domain, HPPC produces a time-dependent bulk resistance ($R_{\mathrm{pulse}} = \frac{\Delta V}{\Delta I}$). This resistance is not a pure physical constant; it is an aggregate of Ohmic, charge-transfer, and diffusion timescales [4]. The measured resistance depends fundamentally on pulse duration, pulse amplitude, temperature, and SOC [4]. Therefore, HPPC data is ideal for parameterising Equivalent Circuit Models (ECM) but less suited for uniquely separating isolated degradation mechanisms without other supporting tests.

## Setup & Equipment Requirements
- **Hardware:** High-power battery cycler, climate/temperature chamber, temperature sensors.
- **Measurement:** High-resolution sampling is critical during pulses. Record every `10 - 20 ms` or the absolute minimum allowed by the tester, or at `3 mV` changes [1].
- **Prerequisites:** Fully charged battery following a standard cycle. Acclimated to the target temperature for at least 3-6 hours [1].

## Standard HPPC Sequence (Handbook Baseline)

1. **Capacity Reference:** Discharge at `0.5 C` to the minimum voltage cutoff to measure the actual available capacity for strict 10% Depth of Discharge (DoD) tracking. Fully recharge.
2. **SOC Step Down:** Discharge at `0.5 C` until achieving a `10%` DoD decrement.
3. **Rest:** Allow the cell to rest for 60 minutes.
4. **Pulse Block:**
   - Discharge pulse at $I_1$ for **18 seconds**.
   - Rest for 60 seconds.
   - Charge pulse at $I_1$ for **18 seconds**.
   - Rest for 60 seconds.
   - *Repeat for different current rates* (e.g., $I_2, I_3$, etc. typically `0.2C, 1C, 5C`).
5. **Iteration:** Repeat steps 2-4 down to 10% SOC [1].

## Modified HPPC Sequence (Naylor Marlow Variant)

For robust degradation tracking across long ageing breakpoints, Naylor Marlow [2] employs a tightly controlled modified HPPC targeting ECM parameterization:
1. **Initial Charge:** CC-CV `1 C` to `4.2 V`.
2. **Target SOC Limit:** Discharge at slow rate `0.25 C` to `90% SOC`.
3. **Long Rest:** Rest `60 min`.
4. **Pulse Block Series:**
   - Sequential `18 s` discharge and charge pulses applied at `0.2 C`, `1 C`, and `3 C`.
   - `60 s` rest between all pulses.
5. **Iteration:** Step down by `10% SOC` increments via `0.25 C` discharge and repeat the pulse block until reaching `2.7 V` (roughly 9 total pulse blocks) [2].

## Analysis Outcomes & Model Constraints
- **Resistance Extraction:** Calculate separate resistance values ($R_0$, $R_2$, $R_{10}$, $R_{18}$) based on the $\Delta V$ observed at specific timings during the pulse [1].
- **ECM Fitting:** Resistance values are used to fit an $R_0 - R_{RC}$ equivalent circuit. Note that a single fitted ECM will only be strictly valid for the specific timescales and usage patterns covered by the HPPC pulses.
- **Degradation Tracking:** Growth in specific pulse resistances over ageing campaigns reveals power fade, though interpreting whether that growth is driven by CEI, SEI, or LLI requires complementary tests like EIS or EVS [2, 4].
