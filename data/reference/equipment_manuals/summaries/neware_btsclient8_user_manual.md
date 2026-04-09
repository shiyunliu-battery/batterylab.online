# Neware BTSClient 8.0 User Manual: Structured Equipment Summary

## Source

- Manual title: `Neware BTS 8.0 User Manual`
- Manufacturer: `Neware`
- Product scope: `BTSClient 8.0` client/server software for the Neware battery test system
- Repository asset id: `neware_btsclient8_user_manual`
- Raw file handling: the user supplied the PDF, but the raw manual is not stored in the repository; only structured notes are kept here

## Why This Manual Is Relevant

This manual is useful for the system because it explains what the Neware BTS software layer can actually do during battery testing. It is not mainly valuable as a click-by-click tutorial. Its main value is that it exposes the step vocabulary, protection settings, export paths, channel-inspection workflow, and the practical hooks between testing, data export, and downstream analysis.

That means it can support:

- equipment capability guidance for Neware software workflows
- preflight QA questions about protection, step editing, and export settings
- analysis workflow guidance for NDA and Excel export
- future deterministic adapter design for Neware data exports

## What This Manual Can And Cannot Confirm

### What it can confirm well

- BTSClient 8.0 is a client/server battery-test software stack using TCP/IP and a database backend, with multi-user support and flexible process control. See pp. 5-6.
- The software exposes a broad step vocabulary, including constant-current charge/discharge, rest, cycle, constant-power charge/discharge, conditional jumps, and constant-voltage variants. See pp. 16-18.
- The software includes advanced protection settings, foolproof settings, step-edit defaults, and export configuration. See pp. 18-27.
- The client can open channel data in BTSDA, export data as NDA or Excel, inspect channel information while a test is running, and perform DCIR-related data operations from the data interface. See pp. 75-79.
- The manual also documents workflow features such as barcode binding, grading, historical-data search, and general precautions. See pp. 84-89.

### What it does not confirm well

- It does not provide a trustworthy hardware datasheet for a specific tester model.
- It does not by itself prove the current range, voltage range, sampling precision, or auxiliary-channel support of one exact Neware chassis.
- It does not replace a model-specific hardware manual, calibration record, or purchasing specification.

So if the system needs to answer:

- `Can this exact tester run 5 A or 100 A?`
- `What is the per-channel voltage limit?`
- `Does this exact rig support chamber control or a given auxiliary card?`

then this manual alone is not enough. A model-specific hardware manual or datasheet is still required.

## What To Extract From This Manual For The System

For this kind of manual, the system should prioritize four knowledge layers.

### 1. Stable software capabilities

These are the most reusable facts:

- software requirements and deployment shape
- test-step vocabulary
- configurable protection and foolproof options
- export pathways and supported save formats
- channel-info inspection functions
- historical-data and grading workflow hooks

These facts are much more stable and reusable than individual screenshots.

### 2. Parameter and constraint names

These are especially valuable because they can later become structured QA and workflow fields:

- cut-off voltage
- cut-off current
- default voltage upper/lower protection
- default current upper/lower protection
- default record time interval
- minimum step time interval
- batch number
- creator
- remarks
- process type
- barcode rules
- data export naming format

The exact names matter because they help align the software manual with later protocol and preprocessing logic.

### 3. High-frequency operational workflows

Only a small number of procedures should be preserved as step-by-step guidance:

- how to define and start a test profile
- how to set or merge advanced protection parameters
- how to export data to NDA or Excel
- how to inspect current channel range and active-step status

These are worth summarizing because users will repeatedly ask them.

### 4. Safety and misuse warnings

The manual contains some operational precautions that are useful for preflight QA:

- verify power-supply compatibility before use
- do not mix old and new batteries or different models
- keep sufficient spacing between running equipment
- inspect clamps and probes before use
- ensure polarity is correct
- stop using a channel if voltage/current behavior is abnormal

These are not enough to replace lab SOPs, but they are worth preserving as supporting equipment precautions. See pp. 88-89.

## What Not To Extract In Detail

Do not spend time encoding every screenshot or every menu-click path into the knowledge base.

Avoid over-encoding:

- window layout screenshots
- repetitive installation wizard pages
- exact icon positions
- view-mode cosmetics
- generic user-management steps unless your lab actually relies on them

These details are expensive to maintain and contribute little to planning or QA quality.

## Most Useful Experimental And Analysis Hooks

### Step-type vocabulary

The manual explicitly defines common step names such as:

- `CCD`
- `CCC`
- `Rest`
- `Cycle`
- `CC&CVC`
- `CP_DChg`
- `CP_Chg`
- `IF`
- `CV_DChg`
- `CCCV_DChg`

This is useful because the system can map user intent onto the kinds of step primitives that the Neware software can represent. See pp. 16-18.

### Protection and foolproof layer

The manual makes clear that Neware has both:

- protection parameters embedded in step files
- advanced protection parameters that can be merged during startup

This matters for the system because it suggests a separation between:

- method logic
- hardware/software protection overlays

That separation is directly useful for preflight QA. See pp. 18-24.

### Step-edit defaults

The step-edit pages show that the software exposes default control and metadata fields including:

- required conditions for step parameters
- creator and batch number
- remarks
- voltage and current upper/lower protection
- step interval defaults
- cut-off current
- permission to edit advanced protection per step

This is one of the most valuable sections for system design because it identifies which fields can later become structured protocol-export or QA targets. See pp. 24-27.

### Data export and analysis interface

The later pages show that the client can:

- open channel data in BTSDA
- configure graph axes
- expand cycle, step, and sampling layers
- export test data as `NDA` or `Excel`
- perform DCIR-related calculations from the data interface
- inspect channel information and current range while running

This is strong evidence that the manual should feed:

- the data adapter registry
- Neware export preprocessing
- KPI-extraction planning

See pp. 75-79.

## Recommended System Use

Use this manual when the user asks things like:

- `Can BTSClient define HPPC-like or multi-step protocols?`
- `Where does Neware expose cut-off current or protection defaults?`
- `Can Neware export Excel directly, or only NDA?`
- `How do I check the current range of a running channel?`
- `Does the Neware client expose DCIR-related analysis tools?`

Do not use this manual alone when the user asks:

- `Is this exact tester headroom enough for my current?`
- `What is the precise voltage/current accuracy of my hardware?`
- `Does my exact chassis support auxiliary temperature channels or chamber integration?`

Those questions require model-specific hardware documentation.

## Practical Conclusion

Yes, this manual is useful and should be kept as an equipment knowledge asset.

But the right abstraction is:

- **mostly parameters, capability categories, and workflow hooks**
- **a few recurring operational procedures**
- **not a full screenshot-by-screenshot software tutorial**

For Battery Lab Assistant, this manual should be treated as a `software capability and workflow source`, not as the final authority on tester hardware limits.
