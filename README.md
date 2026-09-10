# Portfolio Intelligence

This repository contains the Python 3.12 foundation, read-only historical trade-workbook ingestion,
deterministic historical analysis, a dated point-in-time evidence snapshot, a deterministic
investment-decision and working portfolio-sizing prototype, a citation-grounded memo layer, and a
local Streamlit portfolio-intelligence interface.

## Status

**The deterministic pipeline is frozen and the connected local portfolio-intelligence application
is implemented and verified through Phase 8D.** The app adds session-only holdings verification,
bounded grounded questions, deterministic scenario testing, claim-level evidence cards, and
supervised dispositions without changing the Phase 5 snapshot. Controlled Azure requests validated
the corrected interactive answer path, including the DBL hard-gate calculation; ordinary reruns and
citation interactions do not call the provider. The supplied PDFs and workbook remain immutable
local inputs in `assessment_inputs/` and are excluded from version control.

## Structure

- `assessment_inputs/` — protected received source files; local only.
- `src/enam_assessment/` — validation, ingestion, analytics, evidence contracts, and exact-date
  market comparisons.
- `evidence/` — curated normalized evidence, offline snapshot, provenance manifest, and comparison
  output; no raw protected input or credential.
- `config/` — human-readable, versioned prototype decision rules and assumptions.
- `decision/` — deterministic machine-readable decision snapshot and replay hash.
- `prompts/` — versioned, inspectable memo prompt.
- `memos/` — sanitized machine-readable memo status and validated narratives when available.
- `app.py` — local Streamlit entry point over the frozen structured artifacts.
- `tests/` — Foundation and synthetic ingestion, analysis, evidence, and decision Component tests.
- `docs/` — source review, methodology, decisions, assumptions, dictionaries, and reports.

## Windows setup and checks

Python 3.12 is required. From PowerShell at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
py -m pytest tests/test_config.py --basetemp .pytest_cache\foundation-tmp
py -m pytest tests/test_analytics_calculations.py --basetemp .pytest_cache\analytics-foundation-tmp
py -m pytest tests/test_evidence_foundation.py --basetemp .pytest_cache\evidence-foundation-tmp
py -m pytest tests/test_evidence_adapters.py tests/test_market_comparisons.py --basetemp .pytest_cache\evidence-component-tmp
py -m pytest tests/test_historical_analysis.py --basetemp .pytest_cache\analytics-component-tmp
py -m pytest tests/test_ingestion.py --basetemp .pytest_cache\ingestion-regression-tmp
py -m pytest tests/test_decision_calculations.py --basetemp .pytest_cache\decision-foundation-tmp
py -m pytest tests/test_decision_engine.py --basetemp .pytest_cache\decision-component-tmp
py -m pytest tests/test_memo_foundation.py --basetemp .pytest_cache\memo-foundation-tmp
py -m pytest tests/test_memo_pipeline.py --basetemp .pytest_cache\memo-component-tmp
py -m pytest tests/test_portfolio_ui_foundation.py --basetemp .pytest_cache\ui-foundation-tmp
py -m pytest tests/test_streamlit_app.py --basetemp .pytest_cache\ui-component-tmp
py -m pytest tests/test_intelligence_foundation.py --basetemp artifacts\pytest-phase8-foundation
py -m pytest tests/test_intelligence_component.py --basetemp artifacts\pytest-phase8-component
py -m pytest tests/test_phase8_integration.py --basetemp artifacts\pytest-phase8-integration
py -m pytest tests/test_phase8_workflow.py --basetemp artifacts\pytest-phase8-workflow
py -m pytest tests/test_phase8_stress.py --basetemp artifacts\pytest-phase8-stress
py scripts/build_decision_snapshot.py
py scripts/build_company_memos.py
py -m ruff format --check .
py -m ruff check .
py -m mypy src app.py
py -m pip check
```

Start the local application after the structured artifacts exist:

```powershell
py -m streamlit run app.py
```

Do not copy, modify, upload, or commit protected inputs. The optional LLM path sends only a compact
question-specific subset of frozen decision facts and allowed evidence. It calls Azure only after
an explicit submit and caches the validated result in the current session. The implementation does
not include an autonomous agent, cloud deployment, trade execution, or publishing work.

See [the ingestion report](docs/INGESTION_REPORT.md),
[historical analysis](docs/HISTORICAL_ANALYSIS.md),
[point-in-time evidence](docs/POINT_IN_TIME_EVIDENCE.md),
[evidence sources](docs/EVIDENCE_SOURCES.md),
[historical methodology](docs/METHODOLOGY.md), [data dictionary](docs/DATA_DICTIONARY.md),
[decision methodology](docs/DECISION_METHODOLOGY.md),
[current recommendations](docs/CURRENT_RECOMMENDATIONS.md),
[memo architecture](docs/LLM_MEMO_ARCHITECTURE.md), [company memos](docs/COMPANY_MEMOS.md),
[Streamlit application](docs/STREAMLIT_APP.md),
[connected product flow](docs/PORTFOLIO_INTELLIGENCE_APP.md),
[Phase 8A verification](docs/PHASE8A_VERIFICATION.md),
[source review](docs/source_review.md), [decisions](docs/decisions.md), and
[assumptions](docs/assumptions.md).
