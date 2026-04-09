# Ivium EIS Setting Up A Measurement Note: Structured Equipment Summary

## Source

- Manual title: `A4.2 EIS Setting up a measurement`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_eis_setting_up_measurement_note`
- Raw file handling: the user supplied the PDF, but the raw application note is not stored in the repository

## Why This Note Is Useful

This note is one of the most useful Ivium EIS documents for Battery Lab Assistant because it explains how an EIS measurement is actually configured in IviumSoft. It is not only a click path; it also defines which acquisition modes, range-handling options, and advanced settings matter when moving from theory into a real measurement.

It is especially useful for:

- identifying the EIS method variants available in IviumSoft
- explaining how to define the frequency grid
- clarifying single-sine, multi-sine, and dual-sine options
- preserving the practical meaning of `AutoCR`, `Pre ranging`, and `DualCR`
- capturing advanced setup fields such as equilibration, `Connect to`, and `Apply wrt OCP`

## What It Can Confirm Well

- IviumSoft exposes several impedance-oriented methods, including `Constant E`, `Constant I`, `PotentialScan`, and `CurrentScan`. See pp. 1-2.
- The user can define start and end frequencies, the number of frequencies per decade, the perturbation amplitude, and manual frequency overrides. See p. 1.
- The note distinguishes `Single sine`, `Multi sine`, and `Dual sine` measurement modes. See p. 1.
- Current-range handling options such as `AutoCR`, `Pre ranging`, and `DualCR` are part of the setup workflow and affect whether the instrument automatically adapts the current range or prepares the range before the run. See p. 2.
- In advanced mode, the note preserves important setup fields such as:
  - equilibration time
  - stability or bandwidth settings
  - `Connect to` choices such as `Cell-4EL`, `Cell-2EL`, or internal dummy cells
  - `Apply wrt OCP`
  See pp. 2-3.
- The note states that FRA settings are usually left at the default values unless the user has a specific reason to change them. See p. 3.

## What It Does Not Confirm Well

- It does not define the maximum safe amplitude for every battery, SoC, or temperature condition.
- It does not provide model-specific current, voltage, or frequency limits.
- It does not replace a battery-specific method note for deciding which frequency window, rest state, or excitation size is scientifically appropriate.

## Structured Measurement Guidance

The most reusable content from this note is the setup logic:

1. Choose the correct impedance method family for the objective.
2. Define the frequency window and point density.
3. Choose the perturbation mode and amplitude.
4. Decide whether automatic current-range handling is needed.
5. Set the connection topology correctly in advanced mode.
6. Leave deeper FRA settings at default unless there is a justified reason to deviate.

For the system, this is more valuable than preserving screenshot-by-screenshot instructions.

## Recommended System Use

Use this note when the user asks:

- `How do I set up an EIS run in IviumSoft?`
- `What is the difference between Constant E and Constant I?`
- `What does AutoCR do?`
- `Where do I choose Cell-4EL versus Cell-2EL?`
- `Should I change the FRA settings by default?`

Do not use it alone when the user asks:

- `Is this frequency window scientifically correct for my battery mechanism question?`
- `Can my instrument hold this perturbation without clipping?`
- `How should I interpret the fitted ECM physically?`

Those need either stronger theory support or a hardware-specific specification.

## Practical Conclusion

Yes, this note should be part of the equipment knowledge layer.

It gives the clearest operational bridge from EIS theory to an actual Ivium measurement setup and is directly useful for answering `how to enable` and `how to measure` questions.
