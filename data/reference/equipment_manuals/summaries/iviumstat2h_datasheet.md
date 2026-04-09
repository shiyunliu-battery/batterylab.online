# IviumStat2.h: Structured Hardware Datasheet Summary

## Source

- Source title: `IviumStat2.h`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `iviumstat2h_datasheet`
- Source basis: user-supplied specification text, screenshots, and product-page URL [IviumStat2.h](https://www.ivium.com/product/iviumstat2h/)

## Why This Datasheet Is Important

This is a strong model-specific hardware source for a more battery-capable Ivium instrument than the previously added `CompactStat2.h standard`. It helps the system answer not only whether the instrument can run EIS, but also whether it is realistic for moderate-current battery testing and pulse-oriented work.

This source is especially useful for:

- deciding whether the hardware is suitable for battery EIS
- deciding whether the hardware is suitable for moderate-current cycling or pulse work
- understanding the trade-off between high current and maximum applied voltage
- recognizing which capabilities are standard and which are optional

## Configuration Scope

This summary is for the `IviumStat2.h` standard instrument as described in the supplied specification extract:

- scan range: `+-5 A / +-10 V`
- FRA/EIS: `10 uHz to 8 MHz`
- sampling rate: up to `2 MHz`
- optional `True Linear Scan` generator
- optional `Bipotentiostat`

The expandability statements should **not** be treated as if every installed unit includes those options. The standard hardware should be interpreted separately from optional add-ons, boosters, and modules.

## What This Datasheet Can Confirm Well

- Current compliance: `+-5 A`
- Maximum compliance voltage: `+-10 V`
- Maximum applied voltage: `+-10 V below 1 A`, and `+-8 V up to 5 A`
- Electrode connections: `4; WE, CE, RE, S` plus `GND`
- Potentiostat bandwidth: `8 MHz`
- Stability settings: `High Speed`, `Standard`, and `High Stability`
- Programmable response filter: `1 MHz`, `100 kHz`, `10 kHz`, `1 kHz`, `10 Hz`
- Signal acquisition: dual-channel `24 bit` ADC, up to `2,000,000 samples/s`, with up to `1M` datapoints stored in instrument memory
- Applied potential range: `+-10 V`, `0.02 mV` resolution
- Potentiostat current ranges: `+-1 pA to +-10 A`
- Galvanostatic current ranges: `+-10 pA to +-10 A`
- Frequency range for impedance analysis: `10 uHz to 8 MHz`
- Impedance amplitude range: `0.02 mV to 2.0 V`, or `0.03% to 100% of current range`
- Impedance dynamic range: `0.05 nV to 10 V`, and `0.5 zA to 5 A`
- Safety feature: the operator can define maximum current or potential limits
- Peripheral and automation support:
  - multiple analog and digital I/O
  - peripheral control integrated in the software
  - simultaneous acquisition of current, potential, and peripheral analog signals
- Optional modules mentioned:
  - `True Linear Scan` generator
  - `Bipotentiostat`
  - power boosters
  - multiplexers

## Important Mode-Specific Interpretation

This specification mixes top-level compliance numbers, potentiostat and galvanostat current-range statements, and impedance-analyser dynamic-range values. Those should not be treated as if they all mean the same thing.

The safest interpretation for system guidance is:

- `+-5 A` is the dependable top-level standard current-compliance figure for the instrument.
- The `+-10 A` range statements indicate the span of selectable current ranges in potentiostat and galvanostat sections, but they should not automatically be interpreted as the same as a guaranteed `+-10 A` standard output capability.
- For EIS and other small-signal work, the `10 uHz to 8 MHz` FRA range and the `0.5 zA to 5 A` dynamic-range statement are the most relevant figures.
- For battery pulse or cycling work, the `+-5 A` compliance and the reduced `+-8 V` applied-voltage limit at high current are the binding hardware constraints to respect.

## What This Means For Battery-Lab Use

### What it is well suited for

- Battery EIS across a much wider dynamic range than the CompactStat2.h standard
- Low- to moderate-current battery cycling and characterization
- Moderate-current pulse or resistance-oriented testing when the required current stays inside the standard hardware envelope
- OCV, pseudo-OCV, and ECM-oriented measurements
- Research workflows that need both low-current sensitivity and higher battery-relevant current capability
- Experiments that benefit from external synchronization or peripheral control

### What it is not the right default tool for

- Very high-current pack or module testing above the standard `+-5 A` compliance level
- Production-style multi-channel cycling
- Large-cell or module pulse-power work that clearly exceeds the standard unit's current or voltage envelope
- Assuming optional modules such as the `Bipotentiostat` or `True Linear Scan` generator are present without confirmation

## Practical Interpretation For Typical Cells

- For many commercial `18650` cells, this instrument is substantially more realistic than the `CompactStat2.h standard` for low-rate to moderate-rate battery work.
- It is likely appropriate for many single-cell EIS, OCV, and moderate-current characterization tasks.
- It may support some battery pulse or HPPC-style screening on smaller or lower-current cells, but whether it is suitable depends on the requested pulse current and the cell voltage during the pulse.
- If the required current clearly exceeds `5 A`, or the required voltage at higher current exceeds the reduced applied-voltage limit, the standard configuration should be treated as out of scope unless another validated booster configuration is documented.

## Relation To CompactStat2.h Standard

Compared with `CompactStat2.h standard`, the `IviumStat2.h` is the more battery-oriented choice in this repository:

- much higher standard current capability
- broader EIS range (`8 MHz` versus `3 MHz`)
- better fit for moderate-current single-cell work

The `CompactStat2.h standard` still remains the more clearly low-current characterization instrument, while the `IviumStat2.h` is the more credible bridge between electrochemical research hardware and practical battery-cell testing.

## What It Does Not Fully Resolve

- It does not prove which optional modules are actually installed in your lab.
- It does not replace the Ivium setup notes for `how to connect`, `how to enable`, or `how to fit`.
- It does not by itself determine the scientifically correct EIS frequency window, perturbation amplitude, or equivalent circuit.

## How It Connects To The Existing Ivium Knowledge

Use the `IviumStat2.h` datasheet together with:

- `ivium_connecting_electrodes_quick_guide` for `how to connect`
- `ivium_quick_reference_guide` for software readiness and performance checks
- `ivium_eis_setting_up_measurement_note` for `how to enable and configure an EIS run`
- `ivium_eis_equivalent_circuit_fitting_note` and `ivium_eis_worked_example_note` for fitting and inspection
- the Barai review and insertion-reaction theory note for deeper EIS interpretation

This is the chain that lets the system answer:

- how to connect
- how to enable
- whether the hardware is suitable
- how to measure
- how to interpret the result

## Recommended System Use

Use this datasheet when the user asks:

- `Can IviumStat2.h run battery EIS?`
- `Is IviumStat2.h suitable for battery testing or only electrochemical research?`
- `How much current can the standard IviumStat2.h actually support?`
- `Can this instrument do moderate-current single-cell testing?`
- `What changes at higher current with respect to voltage limit?`

Do not use it alone when the user asks:

- `Exactly what EIS settings should I use for this chemistry?`
- `How should I wire the electrodes?`
- `Which equivalent circuit should I fit?`

Those still need the setup notes and theory sources already stored in the repository.

## Practical Conclusion

Yes, this is a very valuable source and should be kept.

It strengthens the system's equipment knowledge substantially because it adds a model-specific Ivium instrument that is genuinely relevant to battery-cell testing, not only to low-current electrochemical measurements.
