# Ivium Quick Reference Guide: Structured Equipment Summary

## Source

- Manual title: `Quick guide to Ivium`
- Manufacturer: `Ivium Technologies`
- Repository asset id: `ivium_quick_reference_guide`
- Raw file handling: the user supplied the PDF, but the raw quick guide is not stored in the repository

## Why This Guide Is Useful

This quick guide is useful as a readiness and maintenance document. It does not explain EIS theory, but it does explain how IviumSoft is installed, how the instrument is connected in software, how the menu system is organised, and how a built-in performance test is run.

That makes it relevant for:

- software readiness checks
- first-time instrument connection
- troubleshooting and self-diagnostic guidance
- firmware/software version consistency questions

## What It Can Confirm Well

- IviumSoft is installed from the supplied package and includes drivers, example data, and the help/manual content. See p. 1.
- Instruments and channels are selected in IviumSoft by serial number, then connected through the adjacent `Connect` action. See p. 1.
- The menu structure includes:
  - `File` for data and method files
  - `Options` for device and data handling, including FRA-related options
  - `Tools` for maintenance and special operations
  - `Help` and `About` for documentation and version information
  See p. 1.
- A built-in `Performance test` exists for self-diagnostic checking of the instrument in standard configuration. The guide states that the test can help determine whether calibration is still correct or whether a problem is hardware-related. See p. 2.
- The performance-test report is stored as a text file named after the serial number with `.ipt` extension. See p. 2.
- Software and firmware versions must match for correct communication and operation. See p. 2.

## What It Does Not Confirm Well

- It does not provide the hardware electrical limits of a specific instrument.
- It does not provide a full EIS measurement procedure or a model-specific FRA specification.
- It does not give enough detail to define exact EIS amplitude, frequency-window, or battery-test compliance settings.

## Most Reusable Operational Guidance

### Instrument readiness

This guide supports a compact readiness flow:

1. Install or update IviumSoft.
2. Power up the instrument.
3. In IviumSoft, identify the instrument or channel by serial number.
4. Connect the selected device in software.
5. Confirm that software and firmware versions are aligned.

This is useful for the system because it defines the software-side preconditions before any measurement discussion begins.

### Self-diagnostic / maintenance

The `Performance test` section is especially valuable because it provides a structured maintenance hook:

- run the performance test only when an instrument is connected
- use the standard configuration
- connect the cell cable to `Testcell1`
- clear option flags before running the test
- expect all statuses to return `Pass`
- if repeated failures occur, calibration or service may be needed

This can later become a troubleshooting checklist in the system.

### Upgrade management

The guide also clarifies that software upgrade and firmware upgrade are coupled: the firmware version on the instrument should match the IviumSoft version. This is an important diagnostic rule because communication issues may be caused by version mismatch rather than by the electrochemical setup itself.

## Recommended System Use

Use this guide when the user asks:

- `How do I know IviumSoft is connected to the right instrument?`
- `Where do I check the software or firmware version?`
- `How do I run the Ivium self-test?`
- `What does the built-in performance test actually tell me?`
- `What kind of file does the performance test save?`

Do not use it alone when the user asks:

- `What current can this Ivium hardware deliver?`
- `What is the exact EIS frequency range?`
- `Can this unit run my battery protocol at a given amplitude or compliance?`

Those questions require a model-specific hardware manual or specification sheet.

## Practical Conclusion

Yes, this guide is worth keeping, but as a readiness and maintenance source rather than a full measurement-theory or hardware-limit source.

For Battery Lab Assistant, the important parts are:

- connection by serial number
- menu-role interpretation
- self-test workflow
- software/firmware consistency

Those are the parts most likely to improve equipment support and troubleshooting quality.
