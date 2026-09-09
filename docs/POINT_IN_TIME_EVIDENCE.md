# Point-in-Time Evidence and Historical Market Comparisons

Analysis as of: **2026-09-08**. No observation or source with a later availability date is in the
snapshot. The offline artifact contains 12,550 price observations, 40 normalized fundamental
facts, 22 supplied-research claims, and 19 source-manifest entries.

## Coverage and temporal rules

- Filings become usable on their publication or conservatively verified availability date, never
  on their fiscal period end.
- Analyst research becomes usable on its report date. The supplied May 2026 reports are excluded
  from any reconstruction of the 2016–2025 trades.
- Company and benchmark intervals require observations on the exact recorded purchase and sale
  dates. Neither prior nor future observations are substituted, and unknown gaps are not filled.
- Company returns use the source's adjusted close. Benchmark returns use the official TRI level.
- A signal observed at a daily close would be actionable only at the next eligible trading
  timestamp. Phase 4 calculates historical close-to-close comparisons only; it does not simulate
  signals or executions.

| Instrument | Observations | First | Last | Adjustment status |
|---|---:|---|---|---|
| Amber Enterprises | 2,128 | 2018-01-30 | 2026-09-08 | Adjusted by secondary source |
| Dilip Buildcon | 2,489 | 2016-08-11 | 2026-09-08 | Adjusted by secondary source |
| Zee Entertainment | 2,643 | 2016-01-01 | 2026-09-08 | Adjusted by secondary source |
| Welspun Living | 2,643 | 2016-01-01 | 2026-09-08 | Adjusted by secondary source |
| NIFTY 500 TRI | 2,647 | 2016-01-01 | 2026-09-07 | TRI; corporate-action adjustment not applicable |
| S&P BSE 500 TRI | 0 | n/a | n/a | Unavailable from unauthenticated official history endpoint |

The 8 September NIFTY close was not yet available when the controlled retrieval ran. The snapshot
therefore ends on 7 September instead of importing a future or provisional value.

## Latest fundamental evidence

These values retain their original units and definitions. They are not forced into a common
valuation model.

| Company | FY26 revenue | EBITDA | PAT | Cash / debt | Other decision-useful evidence |
|---|---:|---:|---:|---|---|
| Amber | Revenue from operations ₹12,186 Cr, +22% | Operating EBITDA ₹970 Cr; 8.0% margin | Reported ₹226 Cr; adjusted ₹338 Cr | Cash ₹231 Cr; current plus non-current borrowings ₹2,306 Cr | OCF ₹240 Cr; promoter 38.17%; no pledge reported in the shareholding filing |
| Dilip Buildcon | Consolidated ₹8,984 Cr | Consolidated ₹1,766 Cr; 19.66% margin | Consolidated ₹1,398 Cr | Consolidated net debt ₹7,244 Cr; standalone net debt ₹1,889 Cr | Order book ₹28,830 Cr; working-capital days 131; promoter 63.14%; 8.94% of total capital pledged or otherwise encumbered |
| Zee | Operating revenue ₹8,098.9 Cr, −2% | Reported ₹346.3 Cr; adjusted ₹754.7 Cr | Continuing PAT ₹271.3 Cr | Cash and treasury investments ₹2,759.5 Cr; debt including leases ₹265.1 Cr | OCF ₹708.1 Cr; disclosed capex ₹160.4 Cr; promoter 3.99% |
| Welspun Living | Revenue from operations ₹9,399 Cr | ₹862.01 Cr; 9.10% margin | PAT after minority ₹204.44 Cr | Net debt ₹775.40 Cr | OCF ₹1,174.98 Cr; disclosed capex ₹661.82 Cr; ROCE 5.61%; ROE 4.20%; net operating cycle 82 days |

Missing fields remain missing: Amber's explicit consolidated net-debt, capex, ROE, and ROCE were
not established; DBL's FY26 OCF, capex, ROE, and ROCE were not reliably extracted; Zee's comparable
ROE/ROCE was not added. No proxy is silently substituted.

## Research evidence

| Company | Structured claims | Coverage | Important distinction or conflict |
|---|---:|---|---|
| Amber | 4 | Q4/FY26 results, FY27 guidance and estimates, working capital | Reported PAT and adjusted PAT remain separate; 56 reported period-end working-capital days and the analyst's adjusted 29-day figure are not interchangeable. |
| Dilip Buildcon | 7 | Q4/FY26, FY27 guidance, debt, order book and mining | Debt appears as several standalone/consolidated definitions; FY27 MDO revenue is stated as both ₹16.9bn and ₹25bn in different passages and remains unresolved. |
| Zee | 5 | Q4/FY26 results, FY27–28 estimates, viewership and rating | Reported, adjusted, and core EBITDA remain separate; all uncertain-version claims use 20 May because of the report's 19/20 May date anomaly. |
| Welspun Living | 6 | Q4/FY26, estimates, guidance and capex | FY26 reported EBITDA ₹7.882bn versus modelled ₹7.932bn, and incurred capex ₹4.7bn versus modelled ₹7.105bn, remain separately typed. |

The research is analyst material, not an official filing. “Reported fact” means reported in that
analyst source unless an official fact with its own evidence ID corroborates it.

## Historical market comparisons

The input population reconciles to Phase 2 and Phase 3: 712 valid realized lots were eligible;
462 provisional open lots, 3 quarantined rows, and 127 structural rows were not used. Eligible
realized purchase cost is ₹342,729,061.29, matching the Phase 3 report. The market series matched
601 lots with ₹246,899,875.49 of purchase cost, or **72.0%** of eligible realized cost.

| Company | Eligible lots | Exact stock/NIFTY matches | Cost coverage | Stock return | NIFTY 500 TRI return | Relative return |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 712 | 601 | 72.0% | 86.9% | 32.2% | 54.7% |
| Amber Enterprises | 191 | 98 | 60.5% | 182.7% | 33.8% | 148.9% |
| Dilip Buildcon | 164 | 146 | 84.7% | −19.1% | 31.4% | −50.5% |
| Welspun Living | 229 | 229 | 100.0% | 35.7% | 28.8% | 6.9% |
| Zee Entertainment | 128 | 128 | 100.0% | −27.3% | 29.7% | −57.0% |

Returns in this table are purchase-cost-weighted averages of matched-lot close-to-close returns.
“Relative return” is stock return minus NIFTY 500 TRI return over the same dates. It is not alpha,
does not measure the investor's execution price, and is not a portfolio return.

Primary S&P BSE 500 TRI coverage is **0 of 712 lots** because its official daily history could not
be obtained without authentication. It remains the declared primary benchmark and is not replaced
by the BSE 500 price index. NIFTY 500 TRI is therefore reported only as the designated secondary
cross-check.

The 111 unmatched stock intervals comprise 93 Amber lots and 18 DBL lots. Most begin before the
NSE listing histories available from the chosen price source: 91 Amber lots have purchase dates in
December 2017 or January 2018 before the 2018-01-30 listing history, and 12 DBL lots begin on
2016-07-29 before the 2016-08-11 listing history. Eight additional intervals use 2018-03-31, a
non-trading Saturday, and are intentionally not shifted to another date.

## Evidence age

No hard freshness threshold is imposed. Ages are descriptive as of 2026-09-08.

| Company | Oldest claim availability | Newest claim availability | Newest age | Note |
|---|---|---|---:|---|
| Amber | 2026-05-16 | 2026-09-08 | 0 days | Latest date is a conservative retrieval-date proxy for a shareholding document whose posting date was unavailable. |
| Dilip Buildcon | 2026-05-14 | 2026-09-08 | 0 days | Latest date is the same conservative shareholding proxy. |
| Zee | 2026-05-20 | 2026-08-10 | 29 days | Research uses 20 May for claims affected by its update-date anomaly. |
| Welspun Living | 2026-05-15 | 2026-09-02 | 6 days | 2 September is the first verified annual-report availability date. |

## What the evidence supports—and what it does not

- On the matched subset, Amber and Welspun had positive cost-weighted relative returns versus the
  secondary NIFTY 500 TRI; DBL and Zee had negative relative returns. This is evidence about the
  selected intervals, not skill, alpha, or benchmark outperformance for a complete portfolio.
- Phase 3's concentration and holding-period findings remain supported by the workbook. Phase 4
  does not use 2026 research to rationalize earlier trades.
- A formal disposition effect remains unsupported because contemporaneous values for both sold
  and retained positions are incomplete.
- Premature selling remains unavailable: optional three-, six-, and twelve-month post-sale tests
  were not asserted because corporate-action provenance is provider-defined and not every interval
  has a complete reliable forward window.
- Portfolio NAV return, cash-aware attribution, drawdown, Sharpe ratio, XIRR, market-timing skill,
  and current portfolio weights remain unsupported.
- The workbook remains a FIFO-matched lot dataset, not an original order ledger. Its pre-listing
  dates for Amber and DBL require owner/source clarification before any alternate price-matching
  rule is introduced.

Detailed source provenance is in [EVIDENCE_SOURCES.md](EVIDENCE_SOURCES.md). The offline records
are in `evidence/normalized_snapshot.json`; lot-level comparisons are in
`evidence/historical_comparisons.json`.
