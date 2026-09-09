# Streamlit Portfolio Intelligence

## Purpose

The application is a read-only presentation layer over the frozen analytical artifacts. It is for
a portfolio owner reviewing historical behaviour, working exposure, company evidence, deterministic
decisions, and validated portfolio-intelligence commentary. It does not parse the workbook, refresh
market data, recalculate investment outputs, or call Azure when Streamlit reruns.

Start it from the repository root in the project environment:

```powershell
py -m streamlit run app.py
```

The normal local URL is `http://localhost:8501`.

## Authoritative inputs

- `decision/decision_snapshot.json`: decisions, weights, gates, principles, scenarios, portfolio
  concentration, and replay hash.
- `memos/company_memos.json`: explicit memo state, frozen decision contract, provider metadata,
  validated narrative when available, and token usage when returned.
- `evidence/normalized_snapshot.json`: normalized citation provenance used to resolve evidence IDs.
- `evidence/historical_analysis_summary.json`: a compact structured rendering of the already
  completed historical analysis for the behaviour view.

Artifact loading is fail-closed. Missing or malformed files, a stale embedded decision contract, an
unsupported memo contract, an unknown company, or an invalid generated narrative raises an explicit
application error. A rejected narrative is never rendered as trusted content.

## Views

1. **Investor Behaviour** presents realized results, holding patterns, sizing, provisional open-cost
   concentration, conservative event-pattern findings, and historical benchmark context.
2. **Current Portfolio** keeps stance, final action, human approval, current weight, target weight,
   cash, concentration, and bear-case portfolio-at-risk distinct.
3. **Company Intelligence** shows the six principles, hard gates, bear/base/bull scenarios, evidence
   balance, explicit memo state, change triggers, missing information, and citation provenance.
4. **Assumptions & Audit** exposes dates, hashes, versions, provider metadata, benchmark limitations,
   and the deterministic-versus-LLM authority boundary.

All four memo states are explicit: `generated`, `not_configured`, `generation_failed`, and
`validation_failed`. Deterministic analysis remains visible in every state. Only a `generated`
narrative that passes the Phase 6 schema, identity, temporal, and citation checks is displayed.

## Current live status

On 10 September 2026, endpoint normalization was corrected so an endpoint already ending in
`/openai` becomes the documented SDK base path `/openai/v1/`, rather than the invalid duplicated
path `/openai/openai/v1/`. The controlled Amber request then reached deployment `gpt-5.6-terra`
with reasoning effort `medium` and a 6,000-token output limit. Azure returned structured output, but
local validation rejected it because `memo_contract_version` was changed from `company-memo-v1` to
`phase5-company-decision-v1`. Amber is therefore `validation_failed`; the other companies were not
called after the failed smoke gate and remain `generation_failed`.

Azure reported 6,104 input tokens, 3,222 output tokens, and 9,326 total tokens for Amber. No charge
is confirmed. Immutable response fields are now pinned to their exact allowed values in the strict
JSON Schema, as well as being checked after generation.

The next live step is one explicitly approved Amber retry using the strengthened schema. Only after
that memo validates should the existing builder call the remaining companies. No UI code change is
required for a successful artifact: the app will load and validate the regenerated memo file.

## Local verification

The pure UI-support tests validate artifact loading, view models, formatting, scenario order,
citations, and memo-state mapping. Streamlit's application test harness exercises every view and all
four companies without network access. A local health check verifies the server endpoint; browser
screenshots are kept only under ignored `artifacts/` for local review.
