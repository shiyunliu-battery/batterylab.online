# Ivium EIS Equivalent Circuit Fitting Note: Structured Equipment Summary

## Source

- Manual title: `A4.3 EIS Equivalent circuit fitting`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_eis_equivalent_circuit_fitting_note`
- Raw file handling: the user supplied the PDF, but the raw application note is not stored in the repository

## Why This Note Is Useful

This note is useful because it translates Ivium's fitting tool into a structured component dictionary and fitting workflow. For Battery Lab Assistant, that is much more important than preserving the exact window layout. It helps the system answer practical fitting questions such as how a circuit is entered, which element labels the software expects, and how a candidate ECM is assembled.

It is especially useful for:

- explaining how the Equivalent Circuit Evaluator is used
- preserving the element codes Ivium expects
- capturing the syntax for series and parallel combinations
- connecting Nyquist fitting workflow to a practical software procedure

## What It Can Confirm Well

- The Equivalent Circuit Evaluator supports several ways to define a model:
  - draw the circuit manually
  - enter a circuit string
  - select a predefined model
  - ask the software to suggest a model
  - load a previously saved model
  See p. 1.
- The note provides a reusable element dictionary:
  - `R` = resistor
  - `C` = capacitor
  - `W` = Warburg
  - `Q` = constant-phase element
  - `L` = inductance
  - `T` = hyperbolic-tangent diffusion element
  - `O` = hyperbolic-cotangent diffusion element
  - `G` = Gerischer element
  See pp. 1-2.
- The syntax rules are explicitly described:
  - `+` for series
  - `*` for parallel
  - brackets for grouping
  See p. 2.
- The note shows that once the model is defined, Ivium exposes a parameter list for the fit. See p. 2.

## What It Does Not Confirm Well

- It does not say which circuit is scientifically correct for a given battery chemistry or ageing state.
- It does not guarantee parameter identifiability.
- It does not replace a theory source for deciding when a Warburg, Gerischer, or diffusion element is physically justified.

## Most Reusable Guidance

- Treat this note as the software-side ECM syntax reference.
- Use it to help the system explain how to build or enter a circuit in Ivium.
- Do not use it alone to justify a physical interpretation of fitted elements.
- Pair it with a battery-EIS theory source when the user asks what the fitted circuit means electrochemically.

## Recommended System Use

Use this note when the user asks:

- `How do I enter an equivalent circuit in Ivium?`
- `What is the syntax for series and parallel elements?`
- `What does element code Q, W, T, O, or G mean in the Ivium fitter?`
- `Can Ivium suggest a model automatically?`

Do not use it alone when the user asks:

- `Should I use a Warburg or a Gerischer here?`
- `Does this fitted circuit prove diffusion-limited behavior?`
- `Which ECM is best for my battery degradation study?`

Those require theory and battery-domain interpretation beyond this software note.

## Practical Conclusion

Yes, this note is worth keeping.

Its main value is that it preserves Ivium's circuit-entry language and fitting workflow in a form the system can reuse consistently.
