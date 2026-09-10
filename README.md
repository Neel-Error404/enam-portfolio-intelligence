# Portfolio Intelligence

Portfolio Intelligence is a supervised decision-support prototype for a four-company equity
portfolio. It combines historical transaction analysis, dated company evidence, explicit
investment rules, deterministic portfolio calculations, and bounded AI explanations with
claim-level provenance.

The design keeps three responsibilities separate:

- people define and review investment judgments and assumptions;
- deterministic code calculates gates, scores, scenarios, weights, stances and actions;
- the language model explains a bounded view but cannot change a decision.

It is an assessment prototype—not an autonomous agent, trade-execution system, live portfolio
record, or claim of investment outperformance.

## Start here

1. Launch the application and follow the connected workflow:
   `Portfolio Cockpit -> Investor Behaviour -> Company Intelligence -> Assumptions & Audit`.
2. Read [Historical Performance and Investor-Behaviour Analysis](docs/HISTORICAL_ANALYSIS.md) for
   the transaction findings and their limits.
3. Read [Decision Methodology](docs/DECISION_METHODOLOGY.md) and
   [Current Recommendations](docs/CURRENT_RECOMMENDATIONS.md) for the rules and frozen outputs.
4. Read [Portfolio Intelligence Application](docs/PORTFOLIO_INTELLIGENCE_APP.md) for the product,
   deterministic/LLM boundary, session state and known limitations.
5. Read [Phase 8 Verification](docs/PHASE8A_VERIFICATION.md) for the preserved failures, corrections
   and exact local verification evidence.

## What the prototype covers

- Read-only ingestion of the supplied encrypted trade workbook with row-level validation,
  quarantine and lineage.
- Gross, price-only historical analysis across 712 realized lots, with explicit exclusions and no
  unsupported complete-portfolio performance claim.
- A point-in-time evidence snapshot dated 8 September 2026 containing prices, fundamentals,
  research claims and source provenance for Amber, Dilip Buildcon, Zee and Welspun Living.
- Deterministic hard gates, six principle scores, relative operating-value scenarios, loss-budget
  position sizing, company stances and portfolio actions.
- A four-view Streamlit workflow with session-only holdings, cash and scenario overlays.
- Explicit-submit Azure OpenAI explanations constrained by strict response identity, schema and
  citation allow-lists. Citation validation proves traceability, not semantic truth.

## Current verified boundary

The deterministic decision pipeline and connected local application are frozen and verified
through Phase 8D. The decision snapshot replay hash is:

```text
014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89
```

Phase 9 is deployed in Azure Container Apps in Central India as of 10 September 2026:
`https://ca-enam-assessment-ci.proudsand-d17a58a5.centralindia.azurecontainerapps.io/`.
The active revision `ca-enam-assessment-ci--phase9-b4000` is healthy; all four views were
browser-verified without inference during navigation. Exactly one new hosted user-facing
generation after the 4,000-token input-budget fix succeeded, preserving the deterministic
DBL `SELL` / `REVIEW_REQUIRED` result. Image digests, response usage, claim-support review,
rollback constraints and the retained operator procedure are in
[the Phase 9 execution record and deployment runbook](docs/PHASE9_AZURE_DEPLOYMENT.md).

This is a public, no-auth assessment deployment with paid AI enabled, not a production-ready
service. Anyone with access can submit potentially billable questions. Scale-to-zero and revision
changes can lose session state; audit files are ephemeral, with no durable logs or persistence.
The current Azure consumption query returned zero posted items, which is not proof of zero final
charge because billing can lag.

The protected PDFs and workbook remain local under `assessment_inputs/`, are immutable for this
project, and are excluded from version control.

## Run locally

Python 3.12 is required. From PowerShell at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The application opens from sanitized structured artifacts already included in the repository. It
does not need the protected workbook or PDFs at runtime, and it does not call Azure during startup,
navigation, ordinary reruns or citation inspection.

Alternatively, with Docker available:

```powershell
docker build -t enam-assessment .
docker run --rm -p 8501:8501 enam-assessment
```

Both local routes intentionally start without Azure credentials. The deterministic application
remains usable; optional AI configuration is documented in
[the Phase 9 deployment runbook](docs/PHASE9_AZURE_DEPLOYMENT.md).

## Verify the local checkpoint

The exact level-by-level commands, environment notes and observed results are in
[Phase 8 Verification](docs/PHASE8A_VERIFICATION.md). Run the levels in its documented order and
stop at the first failure. The key deterministic replay is:

```powershell
py scripts/build_decision_snapshot.py
```

`scripts/build_company_memos.py` is deliberately excluded from the normal verification sequence.
It can call Azure when credentials are configured and rewrites the memo artifact. Run it only as a
separately approved live operation.

## Architecture and data boundary

```text
protected workbook/PDFs
        |
        | read-only, local preparation
        v
sanitized evidence + historical summaries
        |
        v
deterministic decision snapshot
        |
        +---------------------> Streamlit views and session overlays
        |                                      |
        |                                      | explicit question submit
        |                                      v
        +--------------------------> bounded Azure explanation
                                             |
                                             v
                               schema, identity and citation validation
```

The model never receives raw workbook rows, passwords, credentials, complete source documents or
arbitrary repository files. It receives only the permitted question-specific decision facts and
evidence. Invalid provider output fails closed and cannot replace the deterministic result.

## Repository map

- `app.py` — Streamlit entry point and connected product workflow.
- `src/enam_assessment/` — ingestion, analysis, evidence, decisions, memo/intelligence contracts,
  and session portfolio logic.
- `config/decision_engine.json` — versioned prototype policies and assumptions.
- `evidence/` — sanitized point-in-time evidence and historical summaries.
- `decision/` — deterministic machine-readable decision snapshot.
- `prompts/` and `memos/` — versioned AI contracts and sanitized memo status.
- `tests/` — Foundation, Component, Integration, Workflow and Stress verification.
- `infra/` and `Dockerfile` — Phase 9 deployment definition.
- `docs/` — detailed methodology, provenance, assumptions and verification records.

For deeper evidence, continue with [Point-in-Time Evidence](docs/POINT_IN_TIME_EVIDENCE.md),
[Evidence Sources](docs/EVIDENCE_SOURCES.md), [Data Dictionary](docs/DATA_DICTIONARY.md), and
[LLM Memo Architecture](docs/LLM_MEMO_ARCHITECTURE.md).

## Known limits

- Workbook open lots are a provisional holdings proxy; cash and complete NAV were not supplied.
- Historical results exclude fees, taxes, dividends and corporate actions.
- Relative operating-value scenarios are sensitivities, not an absolute DCF or price forecast.
- S&P BSE 500 TRI remains unavailable; NIFTY 500 TRI is context only and does not drive decisions.
- There is no live data refresh, trade execution, authentication, database or durable session state.
- Original-source URLs are not present in the sanitized evidence contract, so the interface shows
  exact source records and locators without fabricating links.
