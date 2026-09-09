# Normalized Trade-Lot Data Dictionary

The public ingestion seam is `ingest_workbook(path, password) -> IngestionResult`. It returns one
`TradeLotRecord` for every row from row 1 through the final non-empty A:H row on each expected
sheet. The loader never scans columns beyond H for trade data.

## Record fields

| Field | Type | Nullable | Meaning |
|---|---|---:|---|
| `company` | `str` | No | Canonical company name associated with the expected sheet. |
| `purchase_date` | `date` | Yes | Normalized Excel purchase date. |
| `purchase_quantity` | `Decimal` | Yes | Positive purchase-lot quantity. |
| `purchase_rate` | `Decimal` | Yes | Positive unit purchase rate. |
| `purchase_amount` | `Decimal` | Yes | Recorded purchase amount. |
| `sale_date` | `date` | Yes | Normalized Excel sale date; absent for open lots. |
| `sale_quantity` | `Decimal` | Yes | Positive sale quantity; absent for open lots. |
| `sale_rate` | `Decimal` | Yes | Positive unit sale rate; absent for open lots. |
| `sale_amount` | `Decimal` | Yes | Recorded sale amount; absent for open lots. |
| `classification` | `LotClassification` | No | Exactly one row outcome described below. |
| `source_sheet` | `str` | No | Original Excel sheet name. |
| `source_row` | `int` | No | Original one-based Excel row number. |
| `validation_results` | `tuple[ValidationResult, ...]` | No | Explicit information, warnings, or errors for the row. |

`ValidationResult` contains a stable `code`, an actionable `message`, and a `severity` of `info`,
`warning`, or `error`. Invalid source values are not converted from strings into dates or numbers.

## Classifications

| Value | Rule |
|---|---|
| `valid_realized` | Complete, valid purchase and sale fields; purchase date is not after sale date; recorded amounts reconcile within tolerance. |
| `provisionally_open` | Complete, valid purchase fields and no sale fields. This is provisional and does not settle the workbook's unmatched-sell ambiguity. |
| `quarantined_invalid` | Any validation error, including malformed/missing required fields, nonpositive values, partial sale details, amount mismatch, sale without purchase, or purchase after sale. Excluded from reconciliation totals. |
| `ignored_structural` | Header rows, blank rows, or undated numeric aggregate rows. Preserved with sheet, row number, and reason but excluded from calculations. |

## Workbook contract

- Required sheets: `Amber`, `DBL`, `Zee`, and `Welspun`.
- Required A3:H3 columns: `Date`, `Qty`, `Rate`, `Amount`, `Date`, `Qty`, `Rate`, `Amount`.
- Only A:H is interpreted as trade-lot data. The last relevant row is the last row containing a
  value in A:H, regardless of Excel's reported used range.
- Dates must be native Excel date/datetime values; strings are quarantined rather than coerced.
- Quantities, rates, and amounts must be native numeric values; booleans and numeric strings are
  quarantined rather than coerced.
- Quantities, rates, and amounts must be greater than zero.
- Recorded amount must match `quantity × rate` within an absolute tolerance of `0.02`. This
  accommodates the workbook's displayed precision and binary floating-point representation.
- Dates after 2025-03-31 are accepted with the `after_stated_period` warning.
- Repeated rows are preserved.

## Reconciliation fields

Each `SheetReconciliation` reports source rows 4 onward, classification counts, accepted purchase
and sale quantities and amounts, provisionally open quantity, realized purchase-minus-sale
quantity, recorded-minus-calculated amount differences, transaction date range, post-period row
count, and ignored/quarantined reason counts with grouped source-row numbers.

## Historical-analysis outputs

- `AnalysisConfig`: explicit historical cutoff date; Phase 3 uses 2025-12-12.
- `RealizedLotMetrics`: source record, purchase cost, sale proceeds, gross realized profit, simple
  return, holding days, optional annualized return, and holding-period band.
- `RealizedPerformanceSummary`: company or overall cost/proceeds, net profit, gross profits and
  losses, cost-weighted return, outcome counts, win rate, lot-return diagnostics, holding-period
  diagnostics, and optional signed profit contribution.
- `HoldingPeriodSummary`: eligible count, purchase cost, profit, cost-weighted return, win rate,
  and median holding days for one declared band.
- `PurchaseSizingAnalysis`: accepted purchase-lot count, cost, median, largest lot, company
  purchase-cost weights, and gross-positive-profit weights.
- `OpenCostAnalysis`: provisional quantity, cost, age, company cost shares, HHI, effective position
  count, and company summaries. These are not verified holdings or market-value weights.
- `InferredEvent`: company/date/side daily group with conserved quantity, amount, weighted rate,
  and contributing source rows. It is not an original broker order.
- `TradingPatternSummary`: bounded counts for scaling purchases, higher/lower-rate additions,
  partial sales, complete exits, re-entries, same-day ambiguities, and quantity breaks.
- `BehaviourFinding`: observed pattern, quantitative evidence, counter-evidence, confidence, and
  limitation.

## Point-in-time evidence outputs

- `EvidenceConfig`: configurable snapshot boundary; the current default is 2026-09-08.
- `PriceObservation`: stable evidence ID, company/benchmark identifier, trading date, optional
  OHLC and volume, close, optional adjusted close, corporate-action status, source, retrieval
  timestamp, and validation state.
- `FundamentalFact`: company, metric, original value and unit, reporting period/end, publication
  date, source and page/section, evidence type, extraction confidence, retrieval time, and conflict
  links.
- `ResearchEvidence`: company, concise claim, reported/estimate/opinion/guidance type, publication
  date, source and page, relevant period, confidence, retrieval time, and conflict links.
- `SourceManifestEntry`: stable source ID, title/type, URL or protected local path, publication and
  retrieval dates, coverage, optional SHA-256, validation status, secondary-source flag, and notes.
- `EvidenceSnapshot`: deterministic, as-of-filtered collections of prices, fundamentals, research,
  manifest entries, and explicit temporal exclusions.
- `MarketComparison`: source lot lineage, interval dates and purchase cost, stock/primary/secondary
  returns, arithmetic relative returns, validation status, and unmatched reason.

`CorporateActionStatus` distinguishes source-adjusted prices, unadjusted prices, non-applicable
index levels, and unknown treatment. `DataState` distinguishes available, missing, stale,
unavailable, and invalid evidence. Staleness is only assigned when a caller supplies a threshold.

## Decision outputs

- `HardGateResult`: stable gate code, pass/fail/unknown status, evidence IDs, deterministic
  explanation, and none/review/sell consequence.
- `PrincipleScore`: one 0-5 dimension score or explicit unavailable value, configured weight,
  rule, supporting and counter evidence IDs, missing information, and data quality.
- `ScenarioInput` / `ScenarioResult`: named three-year operating assumptions, cited inputs,
  terminal revenue and operating metric, target price, and price CAGR.
- `CompanyDecisionSnapshot`: decision date and manifest hash; provisional shares/cost; dated price;
  approximate current value/weight; gates; scores; scenarios; target and bear-risk contribution;
  contextual benchmark evidence; underlying stance; final action; citations; versions; and review
  flags.
- `PortfolioDecisionSnapshot`: company results, residual target cash, current and target
  concentration, total bear-case portfolio-at-risk, benchmark availability, and the provisional
  holdings warning. `snapshot_sha256` hashes its canonical JSON payload.

## Memo outputs

- `DecisionMemoInput`: versioned public Phase 5 fields available to the memo layer, including
  immutable decision identity, holdings proxy, gates, scores, scenarios, benchmark context,
  limitations, citations, and source dates.
- `MemoEvidenceItem`: one cited normalized evidence record with company/instrument scope,
  availability date, concise content, evidence classification, source title/type/locator, and
  conflict IDs.
- `MemoContext`: one decision contract plus its exact stable, deduplicated evidence allow-list.
- `MemoClaim`: generated text, claim category, and one or more allowed evidence IDs.
- `GeneratedMemoNarrative`: structured model narrative whose identity, stance, action, decision
  hash, prompt version, citations, and required sections passed local validation.
- `CompanyMemoArtifact`: deterministic decision plus optional validated narrative, provider and
  deployment identifiers, explicit generation status, safe error, response ID, and provider token
  usage when returned. Status is `generated`, `not_configured`, `generation_failed`, or
  `validation_failed`.

## Streamlit presentation outputs

- `DashboardData`: cross-validated decision contracts, memo states, citation evidence, historical
  summary, and portfolio metadata loaded only from sanitized structured artifacts.
- `AllocationRow`: display-only copy of company ID/name, frozen current and target weights, stance,
  final action, review status, and persisted bear-case portfolio-at-risk.
- `MemoStatePresentation`: accessible text label, tone, and message for one explicit memo state.
- `historical_analysis_summary.json`: compact structured rendering of the completed Phase 3 report
  used by the Investor Behaviour view; it is not a second analytics calculation path.
