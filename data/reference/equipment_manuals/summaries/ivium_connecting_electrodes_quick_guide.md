# Ivium Connecting The Electrodes Quick Guide: Structured Equipment Summary

## Source

- Manual title: `Connecting the electrodes`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_connecting_electrodes_quick_guide`
- Raw file handling: the user supplied the PDF, but the raw quick guide is not stored in the repository

## Why This Guide Is Useful

This guide is short, but it is useful because the connection diagrams are operationally important. Unlike software screenshots that mostly show where to click, these figures define how the Ivium cable leads map onto the actual cell or electrochemical setup. That mapping is worth converting into structured guidance.

It is especially useful for:

- generic Ivium electrode-wiring questions
- explaining what each lead does
- first-measurement startup guidance
- understanding how Ivium saves result files during and after a run

## What It Can Confirm Well

- A standard Ivium cable uses lead assignments such as:
  - red = working electrode (`W`)
  - black = counter electrode (`C`)
  - blue = reference electrode (`R/RE`)
  - white = sense (`S`)
  - green = ground (`GND`)
  - optional second red lead = working electrode 2 (`W2`) for advanced options
  See p. 1.
- The guide shows generic connection logic for 2-electrode, 3-electrode, and 4-electrode arrangements. See p. 1.
- It outlines a minimal first-measurement flow in IviumSoft: connect the instrument or channel, choose operating mode, select a method such as standard cyclic voltammetry, enter method parameters, and start the run. See p. 1.
- It explains where result data appears after the run starts:
  - real-time result graph
  - result-data sheet
  - data files saved by the background data server and by IviumSoft itself
  See p. 2.
- It identifies saved-file types including:
  - sqlite database file for background auto-save
  - `.idf` / `.ids` files for IviumSoft data
  - optional CSV export
  See p. 2.

## What It Does Not Confirm Well

- It does not provide model-specific electrical limits.
- It does not confirm the frequency range, current range, voltage compliance, or EIS accuracy of a specific Ivium instrument.
- It does not replace a full Ivium manual for advanced FRA, battery testing, or bipotentiostat operation.

## Structured Wiring Guidance

The most reusable content from this guide is the meaning of the leads and the topology logic:

- In a 2-electrode setup, the working and counter leads define the main cell connection, while the sense lead should follow the working-electrode potential path.
- In a 3-electrode setup, the reference lead must connect to the reference electrode rather than being left conceptually merged with the counter.
- In a 4-electrode or more elaborate electrochemical setup, the guide signals that wiring must preserve distinct working, counter, reference, and sense roles.

For Battery Lab Assistant, the right abstraction is not to redraw the figure, but to preserve:

- lead-role mapping
- topology-specific connection logic
- the warning that incorrect electrode connection will invalidate the measurement

## Operational Workflow Worth Preserving

Only a small workflow needs to be kept from this guide:

1. Confirm IviumSoft and instrument connection are already correct.
2. Connect the cable leads to the cell or electrochemical setup according to the topology.
3. In IviumSoft, connect the desired instrument or channel.
4. Select the operating mode and measurement method.
5. Enter the parameters and press `Start`.
6. Review the real-time graph and saved output files.

This is enough for the system to answer first-use and wiring questions without storing screenshot-by-screenshot instructions.

## Data Handling Guidance

The guide is useful because it clarifies the automatic data flow:

- background saving through `DataServer`
- automatic save into Ivium project structure
- completed-measurement save into `.idf` / `.ids`
- optional user-managed export

This is relevant to the system because it can support future data-intake and export-adapter work for Ivium-generated files.

## Recommended System Use

Use this guide when the user asks:

- `How do I connect WE, CE, RE, and sense on an Ivium system?`
- `What does the white sense lead do?`
- `What gets saved automatically during an Ivium run?`
- `How do I start a first measurement after wiring the cell?`

Do not use it alone when the user asks:

- `Can this exact Ivium model run my HPPC pulse current?`
- `What FRA frequency range does my instrument support?`
- `What is the compliance voltage or current limit of my specific hardware?`

Those require a model-specific Ivium hardware manual or datasheet.

## Practical Conclusion

Yes, this guide is worth keeping.

The important content is not the slide layout itself, but the connection logic, the lead-role mapping, and the saved-file workflow. Those are the parts that should be available to Battery Lab Assistant.
