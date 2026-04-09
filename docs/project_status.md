# Project Status

Battery Lab Assistant is an early-stage local battery workflow tool. The
current open-source snapshot is best treated as a draft planning and
data-handling assistant, not as an autonomous approval system for lab release.

## Current Strengths

- structured chemistry and method lookup
- selected-cell and imported-cell context carry-through
- protocol drafting with controlled constraints
- deterministic raw export inspection and starter analysis
- markdown report drafting from structured outputs

## Current Limits

- generated plans still require human review before execution
- several workflow asset families are still scaffolded rather than complete
- model-based preview and ECM fitting are not part of the publish surface
- the default local UI does not include production auth, role control, or audit logging

## Good Contribution Areas

- cycler data adapters and normalization rules
- deterministic QA and KPI definitions
- report and DOE templates
- curated equipment and method-reference assets
- regression tests, packaging, and developer docs

## Intended Use

Use this repository for local experimentation, workflow prototyping, and
asset-first lab tooling development. Treat outputs as draft engineering support
unless your own deployment adds the review, governance, and validation layers
required by your organization.
