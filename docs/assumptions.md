# Assumptions and Unresolved Decisions

## 2026-09-08

- **UNRESOLVED:** The supplied material does not define the latest-report freshness window, corpus refresh cadence, thresholds, benchmark, objective, risk rules, or timing/cost/tax/dividend/cash/corporate-action treatment.
- **UNRESOLVED:** The investment-principles `X Rs in Y Yrs` threshold is unfinished; the stated `>25%` price CAGR has no horizon or dividend basis.
- **UNRESOLVED:** There is no validation split, external filing/call/current-market/benchmark dataset, or secure-sharing/retention interpretation.
- **UNRESOLVED:** The brief's ten-year 2015–25 framing conflicts with the workbook note's Apr 2016–Mar 2025 period and later-dated rows.
- **ASSUMED FOR PHASE 1:** Inputs remain local, immutable, and unavailable to tests; later phases must make all analytical and privacy assumptions explicit before implementation.

## 2026-09-08 — Phase 3

- **DECIDED:** Historical calculations stop at 2025-12-12 and retain accepted records after the
  source note's 2025-03-31 endpoint.
- **DECIDED:** Realized results are gross and price-only. Open lots are used only for quantity,
  purchase-cost, age, and partial cost-basis concentration.
- **ASSUMED:** Daily company/side grouping is a conservative analytical event, not a reconstruction
  of original broker orders or intent.
- **DEFERRED:** S&P BSE 500 TRI is the primary future benchmark and NIFTY 500 TRI is the secondary
  cross-check. No benchmark or market data is fetched in Phase 3.
- **UNRESOLVED:** Complete cash, NAV, other holdings, fees, taxes, dividends, corporate actions,
  original orders, and dated market values remain unavailable.

## 2026-09-08 — Phase 4

- **DECIDED:** The current evidence snapshot is bounded at 2026-09-08. Publication date controls
  filing/research availability; trading date controls market observations.
- **ASSUMED:** Yahoo adjusted close is usable as a clearly labelled secondary market-data field,
  but its corporate-action adjustments are provider-defined and not independently reconstructed.
- **UNRESOLVED:** Official S&P BSE 500 TRI history is authentication-gated. `BSE500T` remains the
  primary identifier, but no primary-benchmark return is calculated and no price index is used as
  a substitute.
- **UNRESOLVED:** Exact exchange-effective dates for Welspun's `WELSPUNIND` to `WELSPUNLIV` symbol
  change and Zee's earlier legal name were not established from a captured primary notice.
- **UNRESOLVED:** Amber and DBL workbook lots predate their NSE listing histories, and eight lots
  use 2018-03-31, a non-trading Saturday. Exact-date matching leaves them unavailable.
- **ASSUMED:** When an official document's posting date was not exposed, the first verified public
  availability date is used conservatively and labelled as such.
- **DEFERRED:** No freshness threshold is policy. Source age is reported, and any future threshold
  must be a configurable prototype assumption.

## 2026-09-08 - Phase 5

- **ASSUMED:** Provisionally open lots are a working holdings proxy, not verified live positions.
- **ASSUMED:** The unfinished return wording means a price CAGR greater than 25% over three years.
- **ASSUMED:** Principle weights, the 3.00 quality threshold, 4% position bear-loss budget, 10%
  sizing-downside floor, 5pp rebalance band, confidence factors, and concentration thresholds are
  configurable prototype conventions rather than supplied policy.
- **ASSUMED:** Relative operating-value scenarios use stable share translation plus explicit
  multiple and equity-bridge factors because comparable diluted share counts and complete
  enterprise-value bridges are unavailable.
- **UNRESOLVED:** Live holdings, complete NAV, other assets, cash, liabilities, transaction costs,
  and tax constraints remain unavailable; no recommendation is ready for execution.

## 2026-09-09 - Phase 6

- **ASSUMED:** A concise cited memo is useful as an explanation layer, but the deterministic Phase 5
  snapshot remains the sole authority for numbers and actions.
- **ASSUMED:** Citation allow-list validation establishes provenance presence, not semantic
  entailment or independent truth verification.
- **RESOLVED:** The earlier `NotFoundError` came from duplicating `/openai` while constructing the
  SDK base URL. The corrected `/openai/v1/` route reached Azure and returned structured output.
- **UNRESOLVED:** The returned Amber response changed `memo_contract_version`, so it failed local
  validation. Immutable fields are now pinned in the request schema, but a new live retry has not
  been made. Azure reported 9,326 total tokens; no charge is confirmed.

## 2026-09-09 - Phase 7

- **DECIDED:** The local interface reads sanitized structured artifacts only and never refreshes
  data, recomputes investment outputs, or calls Azure during a Streamlit rerun.
- **ASSUMED:** `evidence/historical_analysis_summary.json` is a presentation snapshot of the
  completed Phase 3 analysis, not a new source of analytical truth.
- **UNRESOLVED:** Amber is `validation_failed`; DBL, Welspun, and Zee remain `generation_failed`
  because the smoke gate prevented their calls. All four must be generated and locally validated
  before live Phase 6/7 closure.
