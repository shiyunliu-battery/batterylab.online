# Unified Protocol: Electrochemical Impedance Test (EIS)

## Sources
- **[1]** Handbook: "Electrochemical impedance test," in *Test methods for improved battery cell understanding v3.0*, pp. 40-43.
- **[2]** Literature: M. Naylor Marlow, J. Chen, and B. Wu, "Degradation in parallel-connected lithium-ion battery packs under thermal gradients," *Communications Engineering*, vol. 3, no. 1, p. 2, 2024.
- **[4]** Literature: A. Barai, K. Uddin, M. Dubarry, et al., "A comparison of methodologies for the non-invasive characterisation of commercial Li-ion cells," *Progress in Energy and Combustion Science*, vol. 72, pp. 1-31, 2019.

## Overview
Electrochemical Impedance Spectroscopy (EIS) measures the frequency-dependent complex impedance $Z(\omega)$ of the battery by applying a small sinusoidal perturbation [4]. The breakdown of the total impedance permits non-invasive tracking of contact/electrolyte resistance, SEI layers, charge transfer kinetics, and solid-state diffusion [1, 4].

While HPPC tests give a time-dependent bulk resistance, EIS provides frequency-resolved dynamics that enable much stronger degradation evidence [4]. In pack-level ageing studies, EIS is typically employed at Start of Life (SOL) and End of Life (EOL) at strictly matched SOC and temperature conditions to verify the divergent growth of charge-transfer resistances [2].

## Setup & Equipment Requirements
- **Hardware:** Frequency Response Analyser (FRA) integrated with a potentiostat or battery tester. Temperature-controlled chamber.
- **Connections:** Strict attention must be paid to test leads. Minimize cabling inductance, and record the setup configuration, as changes to cables or cell holders will shift the high-frequency real-axis intercept ($R_a$) [1].
- **Environment:** Conducted at strictly controlled temperatures after complete thermal acclimatization. Measurements are acquired under Open Circuit Voltage (OCV) conditions.

## Protocol Sequence

1. **Initial State:** Fully charge the cell to `100% SOC` based on the standard CC-CV charge protocol.
2. **Rest (Equilibration):** Let the cell rest at open circuit for `1 hour` [1].
3. **EIS Acquisition:**
   - **Mode:** Potentiostatic (PEIS) or Galvanostatic (GEIS; typically PEIS is preferred for stability).
   - **Amplitude:** `5 mV rms` (or up to 10 mV if signal-to-noise is poor, while ensuring linear response) [1].
   - **Frequency Range:** `10 kHz` down to `10 mHz`. (Frequencies above 10 kHz generally only reveal cabling inductance, not battery behavior).
   - **Resolution:** `5 to 6 points per frequency decade` [1].
4. **Post-Acquisition Rest:** Let the cell rest for `10 minutes`.
5. **SOC Decrement:** Discharge the cell at `1 C` (or standard slow rate) to reach the next target SOC (typically reducing by `20% SOC` increments).
   - Use Ah-counting referenced from a prior low-rate capacity characterisation to hit the target accurately.
   - For `0% SOC`, use CC-CV until the current decays below `C/20` [1].
6. **Iterate:** Repeat Steps 2-5 for `80%, 60%, 40%, 20%, and 0% SOC`.

## Analysis Outcomes & Model Constraints

Data from EIS is conventionally plotted on a Nyquist plot (Imaginary vs Real Impedance).
- **High Frequency Intercept ($>130 \text{ Hz}$):** Represents $R_{ohm}$ (or $R_a$), the sum of electrolyte, contact, and external circuit resistance [1].
- **Mid Frequency Semicircles:** Corresponds to fast interfacial phenomena, including SEI layer resistance and charge-transfer resistance ($R_{ct}$) [1, 4]. Naylor Marlow [2] found that growth in the lower-frequency charge-transfer semicircle is often the dominant driver of divergent ageing under thermal gradients.
- **Low Frequency Tail:** The linear tail represents solid-state diffusion limitations, modeled by a Warburg impedance ($Z_W$) [1, 4].

### ECM Fitting
Quantitative analysis is performed by fitting the spectra to an Equivalent Circuit Model (ECM), typically comprised of an inductor (leads), a series resistor ($R_a$), parallel R|C blocks for SEI/charge-transfer, and a Warburg element [1]. Barai [4] explicitly cautions that the ECM structure must be justified by physical logic, keeping the number of elements as low as possible to avoid over-fitting mathematically identical curves.
