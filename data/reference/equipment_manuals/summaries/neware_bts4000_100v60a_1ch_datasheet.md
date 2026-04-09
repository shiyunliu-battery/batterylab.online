# Neware BTS4000-100V60A-1CH: Structured Hardware Datasheet Summary

## Source

- Source title: `BTS4000-100V60A Battery testing system`
- Manufacturer: `Neware`
- Repository asset id: `neware_bts4000_100v60a_1ch_datasheet`
- Source basis: user-supplied PDF datasheet, not stored in the repository

## Why This Datasheet Is Important

This datasheet adds the missing high-voltage, high-current Neware hardware layer. The previously stored `BTSClient 8.0` manual explains the software workflow, but it does not answer whether a specific tester can actually support a pack-level or high-power experiment. This model does.

## What This Datasheet Can Confirm Well

- System model scope: `BTS4000-100V60A`, item code `CT-4001-100V60A-NA`
- Input AC: `380V/208V +-10% / 50Hz`
- Input power: `7747 W`
- Voltage range: `0.5V to 100V`
- Minimum discharge voltage: `3V`
- Voltage accuracy and stability: `+-0.1% of FS`
- Current range per channel: `0.3A to 60A`
- Current accuracy and stability: `+-0.1% of FS`
- CV cut-off current: `0.12A`
- Output power per channel: `6000 W`
- Current response time: maximum rising time `20 ms`
- Minimum data-record interval: `100 ms`
- Logging triggers include time, voltage change, and current change
- Charge modes: `CC`, `CV`, `CCCV`, `CP`, and `CCCV for battery pack`
- Discharge modes: `CC`, `CP`, `CR`
- Pulse support:
  - charge and discharge pulse modes
  - minimum pulse width `500 ms`
  - up to `32` pulses
  - charge/discharge switching supported
- `DCIR` supported
- Channel-parallel note: for output current above `100A`, channel parallel mode is supported, but pulse function is disabled in parallel mode
- Safety and operations support:
  - power-off data protection
  - offline operation
  - user-defined protection conditions
  - hardware foolproof protection at `IP20`
- Data and communication:
  - `TCP/IP`
  - `MySQL`
  - export to `Excel`, `TXT`, `CSV`, `PDF`, and plots
- Connection method: `Kelvin connection`
- Channel control: independent closed-loop and independent control
- Form factor / cabinet size: `24U (19"), 600 x 600 x 1260 mm`

## What This Means For Battery-Lab Use

### What it is well suited for

- High-voltage and high-current single-channel battery testing
- Pack-level or module-level tests within the `100V / 60A / 6000W` envelope
- Large-cell or high-power single-channel cycling
- Pack-oriented `CCCV`, `CP`, `CR`, and DCIR workflows
- Slower pulse work where `500 ms` minimum pulse width is acceptable

### What it is not the right default tool for

- Fast pulse experiments below `500 ms`
- High-channel-count screening
- Small-cell multi-channel ageing campaigns where throughput matters more than one very large channel
- EIS or frequency-domain impedance work, since the datasheet is for a cycler channel rather than an FRA instrument

## Important Interpretation Boundaries

- This is a **single-channel** high-power system, not a multi-channel screening rack.
- The pulse function exists, but the minimum pulse width is `500 ms`, so it is not a substitute for very fast transient instrumentation.
- Parallel-channel operation is mentioned only for >`100 A` output, and the note explicitly says pulse is disabled in parallel mode. That should be treated as a hard constraint.
- The `100V` and `60A` limits make this much more suitable for pack/module work than the lower-voltage Neware systems in the repository.

## Relation To Other Neware Assets

- Use `neware_btsclient8_user_manual` for software operation, step editing, export, and analysis workflow.
- Use this datasheet for `can the hardware do it` questions.
- Compared with `BTS4000-5V6A-8CH`, this unit trades channel count for voltage, current, and power.
- Compared with `CT-4008-5V30A-NA`, this unit is the high-voltage pack-side option rather than the medium-voltage, medium-current single-cell option.

## Recommended System Use

Use this datasheet when the user asks:

- `Can our Neware system run a 60A or high-voltage battery test?`
- `Is this tester appropriate for pack-level CCCV or CR discharge?`
- `Can this system do DCIR?`
- `What is the minimum pulse width on this channel?`

Do not use it alone when the user asks:

- `How do I configure the protocol in BTSClient?`
- `What exact export path or report file does the software create?`

Those still require the software manual already stored in the repository.

## Practical Conclusion

Yes, this is a valuable model-specific Neware hardware source.

It is the right asset for high-power capability questions and clearly belongs in the equipment knowledge layer as the pack- or high-power-oriented Neware option.
