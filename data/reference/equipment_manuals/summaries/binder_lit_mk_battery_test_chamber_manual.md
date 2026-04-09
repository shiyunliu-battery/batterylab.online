# BINDER LIT MK Battery Test Chambers: Structured Equipment Summary

## Source

- Manual title: `LIT MK (E5) Battery test chambers`
- Manufacturer: `BINDER GmbH`
- Product scope: `LIT MK 240`, `LITMK240-400V`, `LITMK240-400V-C`, `LIT MK 720`, `LITMK720-400V`, `LITMK720-400V-C`
- Repository asset id: `binder_lit_mk_battery_test_chamber_manual`
- Manual issue: `03/2021`
- Raw file handling: the user supplied the PDF, but the raw manual is not stored in the repository; only structured notes are kept here

## Why This Manual Is Relevant

This manual should be treated as a **battery test chamber system manual**, not as a simple thermal-chamber datasheet. Its value comes from the combination of:

- thermal capability
- EUCAR-linked battery-load boundaries
- integrated safety systems
- controller workflow
- operator responsibilities

That makes it important for:

- deciding whether a battery thermal or ageing test is permitted in the chamber
- checking whether a planned sample load stays inside the chamber's intrinsic-safety assumptions
- planning gas detection, CO2 suppression, inertization, and exhaust expectations
- building preflight QA and lab SOP support

## What This Manual Can Confirm Well

### Model scope

- The manual covers the `LIT MK 240` and `LIT MK 720` battery test chambers, including variants with a voltage and frequency changer. See cover and pp. 46-53.

### Intended battery-lab use

- The chambers are intended for temperature treatment, ageing tests, and performance tests of lithium-ion accumulators. See pp. 16-17.
- Charge and discharge cycles may be carried out inside the chamber at different temperature values. See p. 16.
- For planned tests with EUCAR hazard levels up to `3`, cells, modules, and full battery systems are permitted. See p. 17.
- For planned tests with EUCAR hazard levels `4` to `6`, only **individual cells** are permitted, not interconnected modules or systems. See pp. 17-21.
- Abuse testing, destructive testing, deliberate short-circuit generation, deeply discharged cells, and mechanically damaged cells are not generally permitted. See pp. 17-20.
- The chamber is **not explosion-protected**, so EUCAR hazard level `7` is not permitted. See p. 17.

### Defined-load limits for higher-hazard tests

- For EUCAR hazard levels `4` to `6` without additional operator-provided flushing or inertization, the chamber's intrinsic safety is defined only for:
  - `max. one single 18650 cell` in `LIT MK 240`
  - `max. three 18650 cells` in `LIT MK 720`
  See pp. 19-21.
- The manual defines the reference `18650` as up to `5.0 Ah`, diameter `18 x 65 mm`, with a maximum event energy of `200 Wh` for one cell. See p. 21.
- If the defined load is exceeded, additional operator-provided flushing or inertization is required, and responsibility shifts to the operator for those additional protective measures. See pp. 21-22.

### Integrated safety systems

- Integrated gas detection monitors `O2`, `H2`, and `CO`. See pp. 41-42.
- A `CO2` fire suppression device is included and can be triggered automatically and manually. See pp. 43-44.
- The chamber includes a mechanical door lock and a heated pressure relief flap / exhaust path. See pp. 44-45.
- A class 2 temperature safety controller is integrated and should be considered part of the operating safety concept. See pp. 80-83.

### Operating and environmental limits

- Temperature range: `-40 °C to +110 °C` (`-40 °F to 230 °F`). See p. 156.
- Temperature fluctuation: `0.1 to 0.5 K`. See p. 156.
- Average heating rate: `5.0 K/min` for `LIT MK 240`, `4.0 K/min` for `LIT MK 720`. See p. 156.
- Average cooling rate: `3.5 K/min` for `LIT MK 240`, `3.4 K/min` for `LIT MK 720`. See p. 156.
- Heating from `-40 °C` to `110 °C`: `40 min` for `LIT MK 240`, `96 min` for `LIT MK 720`. See p. 156.
- Cooling from `110 °C` to `-40 °C`: `160 min` for `LIT MK 240`, `100 min` for `LIT MK 720`. See p. 156.
- The technical data are specified for an **unloaded** chamber at `+22 °C +/- 3 °C`; full load changes the heating and cooling times. See p. 156.
- Permissible ambient temperature during operation: `+18 °C to +32 °C`. See p. 47.

### Useful hardware details for test setup

- The standard specification includes a heated window door, Ethernet communication, and a class 2 safety controller. See p. 156.
- Access-port scope differs by model:
  - `LIT MK 240`: one `50 mm` access port
  - `LIT MK 720`: two `80 mm` access ports
  See p. 156.

## What This Manual Says About Operating Workflow

### General safety-device startup

Before normal operation, the chamber workflow expects activation and checking of:

- the `CO2` cylinder and coil connector
- the gas detection system
- the valve function
- the CO2 flushing line
- any operator-provided inertization

See pp. 65-70.

### Gas-detection behavior

- After switching on gas detection, wait about `5 minutes` for sensor initialization. During initialization, the sensors show `Err 2`. See p. 66.
- The measuring and dilution gas must remain at a `1:1` ratio, otherwise the `CO` and `H2` sensors malfunction and fault notifications occur. See p. 66.
- The operator can receive analog and binary outputs from the sensor systems and alarm states. See pp. 76-79.

### Behavior when the door is opened

- The fan turns off immediately when the door opens.
- After `60 seconds`, heating and refrigeration switch off.
- The compressor can continue for `5 minutes` without cooling function.

See p. 65.

### Safety-controller guidance

- The safety controller supports `Limit (absolute)` and `Offset (relative)` modes. See pp. 81-82.
- `Offset` mode is recommended for program operation. See p. 82.
- The manual recommends setting the safety-controller threshold about `2 °C to 5 °C` above the desired setpoint, with a typical recommendation of `Offset = 2 °C`. See p. 82.

### Controller and program workflow

- The `MB2` controller supports fixed-value operation, time programs, and week programs. See pp. 55-61 and 87-108.
- Alarm lists, event handling, and controller status views are part of the standard operating flow. See pp. 75-79.

## What The Operator Must Still Own

This manual is unusually explicit that the operator remains responsible for major parts of the safe operating concept.

The operator must provide and maintain:

- risk assessment
- employee training
- operating instructions
- personal protective equipment where required
- `SOPs`
- a system logbook
- an operation log
- recurring testing and maintenance records

See pp. 27-32.

The operation log is recommended to include at least:

- battery arrangement and specification
- chamber controller setpoints
- test parameters
- safety-controller mode and value
- gas-detection activation state
- any additional operator safety measures
- responsible person, date, and signature

See p. 29.

For operator-provided permanent inertization, the manual states clearly that safe operation of that additional system lies with the operator, not with the chamber. See pp. 21-22 and 49-50.

## What This Manual Cannot Confirm By Itself

- It does not by itself prove your **site-specific** exhaust, inertization, or fire-protection installation is compliant.
- It does not replace local SOPs, training records, or the operator risk assessment.
- It does not prove that a planned high-hazard test is permitted just because the chamber can reach the target temperature.
- It does not make the chamber explosion-protected.

So this manual should never be used only as:

- a generic temperature-range source
- a replacement for chamber commissioning records
- a replacement for the lab's safety sign-off process

## How This Chamber Should Be Used In The System

Use this asset when the user asks:

- `Can this chamber support battery ageing or performance testing?`
- `Can we run EUCAR 4 to 6 cell tests in this chamber?`
- `How many 18650 cells are allowed without extra inertization?`
- `What safety systems must be active before starting?`
- `What temperature envelope and ramp performance should we assume?`
- `What does the operator still have to provide beyond the chamber hardware?`

Do not use it alone when the user asks:

- `Is our lab's exhaust or inertization installation compliant?`
- `Can we safely run a destructive abuse test?`
- `Can we ignore operator logbooks because the chamber has alarms?`

Those questions still require local safety governance and installation-specific documentation.

## Practical Conclusion

Yes, this manual is highly valuable and belongs in the equipment knowledge layer.

The right abstraction is not `thermal chamber operating steps`, but:

- chamber-system capability
- battery-specific hazard boundaries
- integrated safety concept
- operator obligations
- controller and alarm workflow

For Battery Lab Assistant, it should be treated as a **battery-test-chamber safety and operating source**, not as a simple environmental-chamber datasheet.
