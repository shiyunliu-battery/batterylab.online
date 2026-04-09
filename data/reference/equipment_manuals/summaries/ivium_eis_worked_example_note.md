# Ivium EIS Worked Example Note: Structured Equipment Summary

## Source

- Manual title: `A4.4 EIS Worked example`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_eis_worked_example_note`
- Raw file handling: the user supplied the PDF, but the raw application note is not stored in the repository

## Why This Note Is Useful

This note is useful because it shows one complete EIS workflow from measurement setup to Nyquist display and equivalent-circuit fitting. It does not prove the best settings for every battery, but it gives a stable starter pattern that can be adapted when the user needs a first Ivium EIS workflow.

It is especially useful for:

- preserving a minimal worked EIS example
- showing a realistic starter frequency window and amplitude
- connecting measurement execution to `SigView` and Nyquist plotting
- showing a simple Randles-style fitting flow after acquisition

## What It Can Confirm Well

- The example uses a `Constant E` measurement on an internal dummy or Randles-style circuit. See p. 1.
- The worked example sets:
  - start frequency `100000 Hz`
  - end frequency `1 Hz`
  - `5 frequencies/decade`
  - perturbation amplitude `0.01 V`
  See p. 1.
- The note shows a fixed current range of `10 mA` in the example, while also indicating that `AutoCR` is generally recommended. See p. 1.
- It uses `Connect to = internal dummy 4` for the demonstration setup. See p. 1.
- It shows the flow from measurement start to `SigView`, Nyquist plotting, and equivalent-circuit fitting. See pp. 1-2.

## What It Does Not Confirm Well

- It does not prove that the exact example settings are appropriate for a battery cell.
- It does not provide a validated battery frequency window, amplitude rule, or fit model for all cases.
- It does not replace a battery-specific EIS method note or a hardware datasheet.

## Starter Workflow Worth Preserving

1. Start from a simple EIS method such as `Constant E`.
2. Define a starter frequency window and point density.
3. Use automatic range handling unless a justified fixed range is required.
4. Run the measurement and inspect the response in `SigView`.
5. Display the Nyquist plot.
6. Move into the equivalent-circuit fitting workflow if the measurement quality is acceptable.

This is enough to support first-use guidance without pretending the example is a universal battery method.

## Recommended System Use

Use this note when the user asks:

- `What does a simple Ivium EIS run look like from start to finish?`
- `Can you show me a starter EIS setup example?`
- `Where does SigView fit into the Ivium workflow?`
- `How do I get from measurement to Nyquist plot and fitting?`

Do not use it alone when the user asks:

- `Is 10 mV always the right amplitude for my cell?`
- `Is 100 kHz to 1 Hz the correct range for my battery?`
- `Does a Randles circuit fully describe my data?`

Those require more specific theory, hardware, and battery-context reasoning.

## Practical Conclusion

Yes, this note is worth keeping.

It is the most compact `how to run one EIS example` reference in the Ivium set, and it complements the theory and fitting notes well.
