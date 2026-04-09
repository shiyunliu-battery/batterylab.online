# Ivium EIS Theory Application Note: Structured Equipment Summary

## Source

- Manual title: `A4.1 EIS Theory`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_eis_theory_application_note`
- Raw file handling: the user supplied the PDF, but the raw application note is not stored in the repository

## Why This Note Is Useful

This application note is short, but it contains the practical theory statements that users often need before setting up an EIS run. It is useful because it links core impedance concepts to measurement choices that matter for batteries, especially the choice between voltage and current perturbation, the need for small-signal operation, and the usual high-to-low frequency sweep order.

It is especially useful for:

- explaining what EIS is doing at a practical level
- answering why current perturbation is often preferred for batteries
- explaining why amplitude should stay small
- clarifying the usual frequency-sweep direction and phase terminology

## What It Can Confirm Well

- EIS applies a sinusoidal perturbation and observes the response over a frequency range so that processes with different characteristic times can be separated. See p. 1.
- For low-impedance systems such as batteries, current perturbation is often preferred because a voltage perturbation can force high current responses, stress the compliance range, or move the system away from a pseudo-linear regime. See p. 1.
- The usual practice is to sweep from high frequency to low frequency. See p. 1.
- The excitation amplitude should remain small so the response stays close to the pseudo-linear region assumed by EIS. See p. 1.
- The note introduces the basic phase concept and the impedance ratio between sinusoidal voltage and current. See p. 1.

## What It Does Not Confirm Well

- It does not provide the hardware limits of a specific Ivium model.
- It does not specify the exact safe amplitude, current range, or compliance range for every battery case.
- It does not replace a deeper battery-EIS theory source when the user asks about Warburg diffusion, bounded diffusion, or detailed ECM interpretation.

## Most Reusable Guidance

- If the cell is a low-impedance battery, start from the assumption that galvanostatic EIS may be the safer and more stable default than potentiostatic EIS unless the hardware and test objective clearly support the voltage-driven mode.
- Sweep from high frequency to low frequency unless there is a specific reason not to.
- Keep the perturbation small enough that the cell response stays close to linear and the fitted impedance remains interpretable.
- Treat this note as a measurement-practice reminder rather than a full electrochemistry derivation.

## Recommended System Use

Use this note when the user asks:

- `Why is current-controlled EIS often preferred for batteries?`
- `Why should the EIS perturbation amplitude stay small?`
- `Do I sweep frequency from high to low or the other way around?`
- `What does phase shift mean in an EIS measurement?`

Do not use it alone when the user asks:

- `Can my exact Ivium instrument source this current amplitude?`
- `What equivalent circuit should I fit to this battery spectrum?`
- `How do diffusion and insertion kinetics create the Nyquist shape?`

Those require either a model-specific hardware manual or a stronger theory source.

## Practical Conclusion

Yes, this note is worth keeping.

Its value is not that it is mathematically complete, but that it captures the practical theory choices behind battery EIS setup: perturbation mode, sweep direction, and small-signal discipline.
