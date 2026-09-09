# Decisions

## 2026-09-08 — Phase 1 foundation

- Scope is limited to a small Python foundation; no analytical, recommendation, LLM, UI, cloud, or external-data implementation is included.
- The package uses a conventional `src/` layout and standard-library-only path configuration.
- Received inputs are immutable local files and are ignored by Git rules.
- Input lookup strictly validates Windows-safe filenames, exact casing, and resolved containment.
- Python 3.12 is the required local environment.
- No Git repository initialization, staging, commit, or publish action is part of this phase.
- No LLM dependency is introduced.

## 2026-09-08 — Phase 2 ingestion

- Treat the workbook as an already FIFO-matched lot dataset, not an execution ledger.
- Decrypt only in memory and require the caller to pass the path and password explicitly.
- Read only A:H and derive the final row from those columns so stray far-right cells are ignored.
- Use an absolute amount-reconciliation tolerance of 0.02 currency units.
- Preserve repeated rows, retain post-2025-03-31 dates with warnings, and quarantine reversed dates.
- Classify undated numeric aggregate rows as structural; they remain traceable and excluded from calculations.
- Add only OpenPyXL and `msoffcrypto-tool` at runtime; use `types-openpyxl` for development-time
  type checking. Pandas and larger infrastructure are unnecessary.

## 2026-09-08 — Phase 3 historical analysis

- Consume only normalized `IngestionResult` records; do not introduce another workbook path.
- Use 2025-12-12 as the explicit cutoff and retain accepted post-2025-03-31 records visibly.
- Use cost-weighted realized return as the headline return; keep unweighted lot statistics as
  diagnostics only and do not annualize holdings shorter than 365 days.
- Treat provisional open lots as partial cost-basis evidence, never verified current holdings.
- Group FIFO fragments into conservative company/side/date events for pattern counts while
  retaining the underlying lot calculations and lineage.
- Record S&P BSE 500 TRI as the next phase's primary benchmark and NIFTY 500 TRI as the secondary
  cross-check; fetch neither in this phase.
- Do not use the 2026 research reports to explain historical decisions.

## 2026-09-08 — Phase 4 point-in-time evidence

- Use stable source-linked evidence IDs that do not change with retrieval time; retain retrieval
  timestamps in provenance.
- Keep conflicting values as separate facts with definition, period, source, and conflict links.
- Use official filings and index providers first. Use Yahoo Finance only as a labelled secondary
  source for daily company prices because a reproducible official history was not accessible.
- Preserve S&P BSE 500 TRI (`BSE500T`) as primary but unavailable; use official NIFTY 500 TRI only
  as the planned secondary cross-check.
- Match historical intervals on exact dates. Do not forward-fill, backfill, or substitute future
  observations.
- Treat company adjusted-close history as provider-adjusted. Do not claim independently verified
  corporate-action reconstruction.
- Retain the normalized snapshot and manifest for offline demonstration; keep raw downloads and
  network caches outside Git.

## 2026-09-08 - Phase 5 deterministic decisions

- Use four explicit layers: hard gates, six weighted principles, three-year scenarios, and
  risk-budget sizing/action mapping.
- Preserve missing dimension evidence as unavailable and make sell-mapped gates dominant over
  weighted scores.
- Use a relative EBITDA-based operating-value sensitivity because the frozen snapshot does not
  establish a comparable diluted share count and full enterprise-value bridge for every company.
- Keep underlying investment stance separate from final portfolio approval. A material rebalance
  based on provisional holdings becomes `REVIEW_REQUIRED` even when the underlying stance is clear.
- Keep S&P BSE 500 TRI unavailable as primary and NIFTY 500 TRI as context only; neither historical
  result drives a current decision.
- Persist a canonical decision snapshot and replay hash; no network or LLM is part of the build.

## 2026-09-09 - Phase 6 portfolio-intelligence memos

- Freeze the public decision interface as `phase5-company-decision-v1`; the memo layer reads the
  persisted snapshot and never reaches into decision-engine internals.
- Use `company-memo-prompt-v1` and `company-memo-v1`. The model is a portfolio-intelligence
  explanation layer for a portfolio owner, not an evaluator-facing assessment writer.
- Select only evidence IDs already cited by each decision, in stable order, and reject unknown,
  future-dated, or wrong-company records before any model request.
- Use the official OpenAI SDK with Azure's v1 Responses API and strict JSON Schema. Keep a small
  provider protocol so automated tests use a fake without network access.
- Assemble immutable decision fields locally, require citations on every material generated claim,
  and publish no fallback prose when generation or validation fails.

## 2026-09-09 - Phase 7 local portfolio-intelligence interface

- Keep Streamlit as a thin read-only projection over the frozen decision, memo, evidence, and
  historical-summary artifacts. Do not move calculations into UI callbacks or call Azure on rerun.
- Use one four-view application for investor behaviour, current portfolio, company intelligence,
  and assumptions/audit, with stance and final portfolio action kept visibly separate.
- Render only locally revalidated `generated` narratives. Preserve explicit `not_configured`,
  `generation_failed`, and `validation_failed` states without fallback prose.
- Use the exact Azure deployment `gpt-5.6-terra`, reasoning effort `medium`, and 6,000 output-token
  ceiling for controlled live attempts. Normalize supported Azure endpoint forms to exactly
  `/openai/v1/`; reject ambiguous paths instead of appending another `/openai` segment.
- Keep immutable memo identity fields constrained in the strict response schema and validate them
  again locally. Stop after the corrected Amber request returned the wrong memo-contract version;
  do not automatically retry or substitute another deployment.
