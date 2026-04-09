# Ivium CompactStat2.h Standard: Structured Hardware Datasheet Summary

## Source

- Source title: `CompactStat2.h standard`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_compactstat2h_standard_datasheet`
- Source basis: user-supplied specification text and screenshot from the product page, not a raw PDF stored in the repository

## Why This Datasheet Is Important

This is the kind of source the system was still missing. The earlier Ivium quick guides and application notes were useful for wiring, software workflow, and EIS setup logic, but they were not enough to answer the harder question: `Can this exact instrument actually do the measurement?`

This model-specific specification is the first strong source in the Ivium set for:

- current and voltage compliance
- frequency range
- signal-acquisition rate
- electrode topology
- analog and digital I/O
- whether the instrument is better suited to low-current electrochemical characterization or high-current battery testing

## Configuration Scope

This summary is for the `CompactStat2.h standard` configuration, identified in the supplied material as:

- scan range: `+-30 mA / +-10 V`
- FRA/EIS: `10 uHz to 3 MHz`
- sampling rate: up to `2 MHz`

The supplied source also mentions expandability and other current configurations. Those optional or alternate configurations should **not** be assumed to apply to the standard unit unless separately documented.

## What This Datasheet Can Confirm Well

- Current compliance: `+-30 mA`
- Maximum compliance voltage: `+-10 V`
- Maximum applied voltage: `+-10 V`
- Electrode connections: `4; WE, CE, RE, S` plus `GND`
- Potentiostat bandwidth: `>3 MHz`
- Stability settings: `High Speed`, `Standard`, and `High Stability`
- Programmable response filter: `1 MHz`, `100 kHz`, `10 kHz`, `1 kHz`, `10 Hz`
- Signal acquisition: dual-channel `24 bit` ADC, up to `2,000,000 samples/s`, with up to `1M` datapoints stored in instrument memory
- Applied potential range: `+-10 V`, `0.02 mV` resolution
- Potentiostat current ranges: `+-1 pA to +-1 A in 14 decades`
- Galvanostatic current ranges: `+-10 pA to +-1 A`
- Frequency range for impedance analysis: `10 uHz to 3 MHz`
- Impedance amplitude range: `0.02 mV to 2.0 V`, or `0.03% to 100% of current range`
- Impedance dynamic range: `0.05 nV to 10 V`, and `0.5 zA to 30 mA`
- Floating operation: user selectable
- Peripheral I/O:
  - analog in/out: `2/1`
  - digital input/output: `1 input / 3 output`
  - `I-out` / `E-out`
  - `AC-in`, `AC-out`
  - `Channel-X` and `Channel-Y` inputs

## Important Mode-Specific Interpretation

This source mixes potentiostat, galvanostat, and impedance-analyser specifications. That means the current-related limits should not be read as one single number for every mode.

The most important distinctions are:

- In the instrument-level summary and EIS dynamic-range section, `30 mA` is the key small-signal / compliance figure for the standard unit.
- In galvanostatic mode, the listed current ranges extend up to `+-1 A`.
- Therefore, the standard unit is not just a `30 mA only` instrument, but `30 mA` is still the binding figure for many potentiostatic and EIS use cases.

For system guidance, the safest abstraction is:

- **EIS / potentiostatic small-signal work**: think in terms of the `30 mA`, `+-10 V`, `10 uHz to 3 MHz` hardware envelope.
- **Galvanostatic battery cycling or pulse work**: the `+-1 A` current-range statement matters, but the user should still confirm the exact mode-specific operating envelope before release.

## What This Means For Battery-Lab Use

### What it is well suited for

- EIS on cells that fit within the instrument's low-current and `+-10 V` envelope
- 2-, 3-, or 4-electrode electrochemical measurements
- Low-current battery characterization and model-oriented studies
- OCV or pseudo-OCV support measurements when only low-rate current is needed
- Low-current or moderate-current galvanostatic studies on small cells
- ECM and EIS-based parameterization work
- Experiments that benefit from analog or digital synchronization with peripheral equipment

### What it is not the right default tool for

- High-current HPPC on most commercial cylindrical Li-ion cells
- High-throughput battery cycling
- Large-format pouch or module testing
- Multi-amp pulse-power testing where the required current exceeds the unit's practical mode-specific limits
- Replacing a dedicated battery cycler for standard cycle-life campaigns

## Practical Interpretation For Typical Cells

- For small cells around the `~1 Ah` class, this instrument may support low-rate galvanostatic work and EIS quite well.
- For many larger commercial `18650` cells, it is likely appropriate for EIS and very low-rate characterization, but not for realistic HPPC or medium-to-high-rate cycling.
- If a planned pulse or cycling current is above `1 A`, this standard configuration should generally be treated as out of scope unless another validated current-booster configuration is documented.

## What It Does Not Fully Resolve

- It does not tell us how all optional booster or expansion modules change the limits in the actual lab configuration.
- It does not replace the Ivium software notes for wiring, setup, fitting workflow, or maintenance.
- It does not by itself define the scientifically correct EIS frequency window, perturbation amplitude, or fitting model for a battery problem.

## How It Connects To The Existing Ivium Knowledge

Use the CompactStat2.h datasheet together with:

- `ivium_connecting_electrodes_quick_guide` for `how to connect`
- `ivium_quick_reference_guide` for `how to connect the software and run self-checks`
- `ivium_eis_setting_up_measurement_note` for `how to enable and configure an EIS run`
- `ivium_eis_equivalent_circuit_fitting_note` and `ivium_eis_worked_example_note` for `how to fit and inspect the measurement`

That combined chain is what lets the system answer:

- how to connect
- how to enable
- whether the hardware is likely suitable
- how to measure

## Recommended System Use

Use this datasheet when the user asks:

- `Can the CompactStat2.h standard run battery EIS?`
- `What is the EIS frequency range of this Ivium model?`
- `Can this instrument do 4-electrode measurements?`
- `Is this instrument suitable for HPPC or only for low-current work?`
- `Does this unit have analog or digital I/O for peripheral control?`

Do not use it alone when the user asks:

- `Exactly what EIS settings should I use for this chemistry?`
- `How do I wire the leads?`
- `Which equivalent circuit should I fit?`

Those should be answered by combining this datasheet with the setup notes and theory sources already in the repository.

## Practical Conclusion

Yes, this is a very valuable source and should be kept.

Compared with the earlier Ivium quick guides, this datasheet is the missing hardware-capability layer. It is the source that most directly supports `can it do the measurement` decisions for the standard CompactStat2.h configuration.
