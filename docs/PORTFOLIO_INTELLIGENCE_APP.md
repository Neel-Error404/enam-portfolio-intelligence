# Portfolio Intelligence Application

## Purpose

The local Streamlit application connects the frozen analytical outputs into a supervised investor
workflow:

`review portfolio -> understand priorities -> investigate -> ask -> inspect evidence -> test a scenario -> record a disposition`

The deterministic Phase 5 snapshot remains authoritative. Session overlays and model explanations
do not modify it.

## Run locally

From PowerShell in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
py -m streamlit run app.py
```

The app reads only the sanitized local decision, evidence, historical-summary, and memo artifacts.
It does not reopen the protected workbook or PDFs.

## Views

- **Portfolio Cockpit** — review or adjust workbook-derived shares and available cash for the
  session; compare active weights with frozen targets; review concentration, actions, and common
  drivers; ask portfolio or two-company questions.
- **Company Intelligence** — inspect the immutable stance/action, principles, gates, scenarios,
  evidence balance, compact brief, questions, deterministic Scenario Lab, and owner disposition.
- **Investor Behaviour** — review accepted historical outcomes and limitations, then ask a bounded
  question that cites the deterministic historical summary.
- **Assumptions & Audit** — inspect hashes, versions, model settings, legacy memo states, session
  activity, benchmark treatment, limitations, and download a sanitized session audit.

## Shared Portfolio Intelligence conversation

Every view puts an `Ask AI about this page` action beside its title. It opens one shared,
Streamlit-native Portfolio Intelligence dialog that remains consistent across page and company
navigation. The sidebar contains only a compact secondary launcher, not a duplicate conversation.
The current page is the labelled default context. `Ask AI about this` actions attach structured
analytical sections; chips in the dialog show each section's originating page and company or
portfolio scope until the user removes or clears it. Opening or closing the dialog, selecting
context, navigating, and ordinary reruns do not call Azure. Only the explicit question submission
does.

Question contexts are assembled from structured decision, evidence, historical, active-portfolio,
scenario, artifact, and bounded-conversation records. Compact evidence contains an explicit company
or instrument, evidence kind/category, availability date, reporting period or relevant date, unit,
and evidence ID. The active overlay is sent as a traceable derived record and is kept distinct from
frozen engine weights and from reported company facts.

Context and cache hashes include active shares/cash provenance, selected artifacts, relevant recent
turns, scenario delta, prompt version, and response-contract version. An answer generated before a
relevant session change remains visible with its original context and is labelled as historical
rather than reinterpreted.

The page hierarchy follows the investment workflow: portfolio state and concentration precede
allocation and decisions; company hard gates precede principle scores and valuation; behaviour
scope and limitations precede interpretation; and the audit view explains the deterministic/LLM
boundary before hashes and runtime details. Long action labels wrap rather than overlap, including
on a 390-pixel-wide viewport.

## Interactive Azure configuration

Questions are sent only after an explicit submit. Ordinary Streamlit reruns never call Azure.
The required environment variables are:

- `AZURE_OPENAI_ENDPOINT` or `AZURE_OPENAI_BASE_URL`;
- `AZURE_OPENAI_API_KEY`;
- `AZURE_OPENAI_DEPLOYMENT=gpt-5.6-terra`.

Optional interactive controls are `ENAM_INTELLIGENCE_REASONING_EFFORT` (default `low`) and
`ENAM_INTELLIGENCE_MAX_OUTPUT_TOKENS` (default `2200`). Secrets are neither displayed nor stored.
The endpoint adapter accepts an Azure resource root, `/openai`, or the canonical `/openai/v1/`
form and normalizes it once.

## Grounding and budgets

The question router supports company briefs, company questions, portfolio questions, two-company
comparisons, historical-behaviour questions, and deterministic scenario-delta explanations. It
uses deterministic scope/topic selection, never embeddings or semantic search.

- Company briefs have a 3,500-token request budget.
- Interactive answers have a 2,500-token request budget.
- A conservative prompt/schema reserve is removed before evidence selection.
- Evidence IDs are selected and ordered deterministically. Excluded IDs are retained in the local
  audit context, not sent to the model.
- Scope-defining deterministic calculations are retained before external supporting records.
- Requests that cannot retain citable evidence within budget fail explicitly.

Actual Azure usage is recorded when returned by the provider. Validated answers are cached only in
the current Streamlit session by normalized question and complete context hash.

## Authority and validation

The model may synthesize and explain supplied facts. It cannot calculate or change scores, gates,
scenario outputs, weights, stances, final actions, or human dispositions. Responses must match
`portfolio-answer-v1`, preserve the exact decision and context hashes, and cite only evidence from
that request. Invalid responses are not rendered as trusted content.

Citation validation proves traceability to the bounded context, not semantic truth. Every rendered
claim has a `Sources for this claim` control that opens only its cited records. The cards lead with a
readable source label and provenance class, then show the complete sanitized evidence record,
company/instrument, category, reporting period or observation date, unit, availability date, source
title/type/locator, recorded conflicts, and the raw evidence ID for audit. The current sanitized
contract provides locators but not verified original-source URLs, so the application deliberately
shows no source links rather than fabricating or exposing a local-file target.

## Session-only state and audit

Workbook-derived open-lot shares and frozen price evidence are active on first load. Cash was not
supplied, so the default is an explicit zero-cash calculation assumption rather than a verified
account balance. Optional share and cash changes, scenario overrides, grounded answers, and owner
dispositions exist only in the Streamlit session. Each holding and the cash field retain their
supplied/assumed or user-entered provenance. Reset restores the supplied-data defaults.

A sanitized JSON audit can be downloaded; it records context selection, provider metadata, usage,
validation state, scenario overrides, and dispositions. Generated-answer metadata is also appended
immediately to the ignored `artifacts/phase8b/live_answer_audit.jsonl` file so a later validation
failure or closed browser does not erase the response ID and provider usage. Neither record
represents an executed trade or a promoted decision.

Manual claim-support review has no preselected verdict. The reviewer must explicitly choose
`passed` or `failed`; both the verdict and note are appended to the ignored audit rather than
rewriting earlier records.

## Known limitations

- Open-lot shares are calculated from supplied assessment data, not independently verified live
  holdings.
- Scenario values remain prototype relative operating-value sensitivities.
- S&P BSE 500 TRI remains unavailable; NIFTY 500 TRI is historical context only.
- No live data refresh, order execution, authentication, database, or production persistence is
  present.

## Verification status

Phase 8C closed the live grounding gate with a validated DBL hard-gate answer, and Phase 8D closed
the claim-level citation-usability gate without another Azure request. The current application
therefore has a GO verdict for local application readiness. The complete suite result and exact
deterministic replay hash are recorded in `docs/PHASE8A_VERIFICATION.md`; earlier failed calls remain
there as authentic history rather than being rewritten.
