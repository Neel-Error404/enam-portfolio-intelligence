# Current Recommendations

Decision date: **2026-09-08**  
Evidence manifest SHA-256: `be92698be561ae08e41763a539f0416ddfa754267692d7d5c8c173afd51488c6`  
Decision snapshot SHA-256: `014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`  
Engine/configuration: `1.0.0` / `phase5-prototype-1`

> **Working-holdings warning:** Workbook open lots are an unverified working holdings proxy; weights and actions are approximate and require owner confirmation before trading.

These are deterministic assessment outputs, not trade instructions. A final action of REVIEW_REQUIRED means a person must resolve the stated approval or evidence issue.

## Decision summary

| Company | Stance | Final action | Score | Current | Target | Bear value/CAGR | Base value/CAGR | Bull value/CAGR |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Amber Enterprises India Limited | SELL | REVIEW_REQUIRED | 3.60 | 48.3% | 14.3% | 4,472.90 / -15.1% | 15,124.04 / 27.4% | 22,593.76 / 45.7% |
| Dilip Buildcon Limited | SELL | REVIEW_REQUIRED | 2.68 | 42.0% | 0.0% | 87.03 / -39.5% | 349.40 / -3.9% | 697.99 / 21.0% |
| Welspun Living Limited | HOLD | HOLD | 3.02 | 8.7% | 5.5% | 100.80 / -21.4% | 337.03 / 17.5% | 521.36 / 35.9% |
| Zee Entertainment Enterprises Limited | SELL | HOLD | 2.60 | 1.0% | 0.0% | 28.68 / -30.7% | 91.14 / 1.8% | 160.26 / 22.9% |

## Working portfolio

The four provisional open-lot positions have an approximate market value of INR 764,207,865.35. The proposed assessment sleeve retains 80.2% cash.

| Metric | Current working sleeve | Target risky sleeve |
|---|---:|---:|
| Largest name | 48.3% | 72.1% |
| Top two | 90.3% | 100.0% |
| Top three | 99.0% | 100.0% |
| HHI | 0.417 | 0.598 |
| Effective positions | 2.40 | 1.67 |

Target bear-case portfolio-at-risk is 3.3% of the represented sleeve. It is the sum of each absolute target weight times that company's bear-case downside; it is not VaR and excludes cash and unrepresented assets.

Current concentration breaches the prototype review conventions: single_name, top_two, hhi. Target risky-capital concentration is shown conditional on invested capital; the large cash allocation is reported separately.

## Benchmark context

The intended primary benchmark `bse-500-tri` remains **unavailable_authentication_required**. `nifty-500-tri` is **available_context_only**. The NIFTY comparison below is historical context only and does not enter any gate, score, scenario, target, stance, or action.
- Amber Enterprises India Limited: NIFTY 500 TRI matched-period relative return 148.9% across 98/191 eligible realized lots.
- Dilip Buildcon Limited: NIFTY 500 TRI matched-period relative return -50.5% across 146/164 eligible realized lots.
- Welspun Living Limited: NIFTY 500 TRI matched-period relative return 6.9% across 229/229 eligible realized lots.
- Zee Entertainment Enterprises Limited: NIFTY 500 TRI matched-period relative return -57.0% across 128/128 eligible realized lots.

## Amber Enterprises India Limited

**SELL / REVIEW_REQUIRED final action.** Current price INR 7,308.00 on 2026-09-08 (0 days old); working shares 50,537.750, cost basis INR 40,462,544.12, approximate market value INR 369,329,877.00, current weight 48.3%, and target 14.3%.

The weighted principle score is 3.60 / 5. Bear/base/bull targets are INR 4,472.90, INR 15,124.04, and INR 22,593.76, with three-year CAGRs of -15.1%, 27.4%, and 45.7%.

### Hard gates

| Gate | Status | Consequence | Explanation | Evidence |
|---|---|---|---|---|
| `balance_sheet_liquidity_and_funding` | pass | none | Borrowings are material and reduce the score, but positive operating cash flow and the observed EBITDA do not cross the prototype sell gate. | `fundamental-ce174b052e07074e`, `fundamental-d6fcf6d34b37a12d`, `fundamental-ef4de454414fa76c`, `fundamental-adbdf9c9faf91f36` |
| `critical_decision_evidence` | pass | none | FY26 revenue, EBITDA, cash, borrowings, and a decision-date price support a bounded relative operating-value model. | `fundamental-1eb858fe9f6565c1`, `fundamental-adbdf9c9faf91f36`, `price-bd65ec54100fe2c5` |
| `current_price` | pass | none | A validated adjusted close exists on the decision date. | `price-bd65ec54100fe2c5` |
| `governance_and_alignment` | pass | none | No serious governance event is confirmed in the bounded snapshot; promoter ownership is evidence, not a complete governance review. | `fundamental-982b62122ae89c16` |
| `material_evidence_conflict` | pass | none | Adjusted and reported PAT differ by definition; neither is used as the operating-value denominator. | `fundamental-amber-adjusted-pat-fy26`, `fundamental-amber-reported-pat-fy26` |
| `thesis_and_valuation` | pass | none | No active thesis break is recorded and a transparent operating-value sensitivity can be constructed. | `fundamental-1eb858fe9f6565c1`, `fundamental-adbdf9c9faf91f36`, `research-amber-2026-05-16-p1-electronics-estimate`, `research-amber-2026-05-16-p1-rac-guidance` |

### Principle scores

| Dimension | Weight | Score | Quality | Rule |
|---|---:|---:|---|---|
| balance sheet conservatism | 20.0% | 2.00 | high | Borrowings less cash are high relative to FY26 EBITDA despite positive operating cash flow. |
| business quality and durability | 20.0% | 4.00 | medium | Strong growth and operating scale, moderated by volatile working capital. |
| management alignment and capital allocation | 15.0% | 3.00 | medium | Meaningful promoter ownership and positive cash generation, offset by leverage and limited allocation history. |
| reinvestment runway | 15.0% | 4.50 | medium | Electronics expansion and RAC guidance indicate a substantial runway. |
| structural growth | 15.0% | 4.50 | medium | FY26 growth plus supplied electronics and RAC outlook support above-average growth. |
| valuation and expected return | 15.0% | 4.00 | medium | The base operating-value scenario clears the prototype 25% CAGR hurdle but is assumption-sensitive. |

**Strongest support (reinvestment runway):** The analyst expected electronics revenue to grow more than 40% in FY27. (`research-amber-2026-05-16-p1-electronics-estimate`); Management guidance described RAC growth outperformance of 13-15%. (`research-amber-2026-05-16-p1-rac-guidance`)

**Strongest counter-evidence (balance sheet conservatism):** borrowings 2306 INR crore; current plus non-current (`fundamental-d6fcf6d34b37a12d`); cash_and_cash_equivalents 231 INR crore (`fundamental-ce174b052e07074e`); operating_ebitda 970 INR crore (`fundamental-adbdf9c9faf91f36`); operating_cash_flow 240 INR crore (`fundamental-ef4de454414fa76c`)

**Warnings:** provisional_holdings_material_to_rebalance

**What would change the result:** Net leverage or cash conversion worsens materially; Electronics growth or RAC guidance is withdrawn; Base-case operating growth falls below the 25% price-CAGR hurdle.

**Missing information:** Comparable long-run segment returns on capital; Debt maturity and covenant schedule; Independent end-market demand series; Multi-cycle acquisition and capital-allocation outcomes; Order-level return on incremental capital; Verified share count and independently reconstructed enterprise value.

**Cited evidence and availability dates:** `fundamental-1eb858fe9f6565c1` (2026-05-16); `fundamental-982b62122ae89c16` (2026-09-08); `fundamental-adbdf9c9faf91f36` (2026-05-16); `fundamental-amber-adjusted-pat-fy26` (2026-05-16); `fundamental-amber-reported-pat-fy26` (2026-05-16); `fundamental-ce174b052e07074e` (2026-05-16); `fundamental-d6fcf6d34b37a12d` (2026-05-16); `fundamental-e1c16f99ae73902d` (2026-05-16); `fundamental-ef4de454414fa76c` (2026-05-16); `price-bd65ec54100fe2c5` (2026-09-08); `research-amber-2026-05-16-p1-electronics-estimate` (2026-05-16); `research-amber-2026-05-16-p1-rac-guidance` (2026-05-16); `research-amber-2026-05-16-p1-working-capital` (2026-05-16).

## Dilip Buildcon Limited

**SELL / REVIEW_REQUIRED final action.** Current price INR 393.55 on 2026-09-08 (0 days old); working shares 814,993.143, cost basis INR 271,423,739.62, approximate market value INR 320,740,541.42, current weight 42.0%, and target 0.0%.

The weighted principle score is 2.68 / 5. Bear/base/bull targets are INR 87.03, INR 349.40, and INR 697.99, with three-year CAGRs of -39.5%, -3.9%, and 21.0%.

### Hard gates

| Gate | Status | Consequence | Explanation | Evidence |
|---|---|---|---|---|
| `balance_sheet_liquidity_and_funding` | fail | sell | Consolidated net debt is 4.10 times FY26 EBITDA, above the prototype 4.0-times sell threshold, with 131 working-capital days. | `fundamental-dbl-consolidated-net-debt-fy26`, `fundamental-c02d7f1564a6c6e4`, `fundamental-7dbb39273996c745` |
| `critical_decision_evidence` | pass | none | Revenue, EBITDA, consolidated net debt, and price are available. | `fundamental-b3dd06efaec87764`, `fundamental-c02d7f1564a6c6e4`, `fundamental-dbl-consolidated-net-debt-fy26`, `price-9ccb6ec1f996ea08` |
| `current_price` | pass | none | A validated adjusted close exists on the decision date. | `price-9ccb6ec1f996ea08` |
| `governance_and_alignment` | unknown | review_required | High promoter ownership is countered by 8.94% of total capital recorded as promoter-encumbered. | `fundamental-670dd97c37c6fd3b`, `fundamental-45adc13be8367240` |
| `material_evidence_conflict` | unknown | review_required | Debt values use different consolidation scopes; both are retained and the consolidated value controls the balance gate. | `fundamental-dbl-consolidated-net-debt-fy26`, `fundamental-dbl-standalone-net-debt-fy26`, `research-dbl-2026-05-15-p1-debt-summary`, `research-dbl-2026-05-15-p5-debt` |
| `thesis_and_valuation` | pass | none | Order book and growth guidance permit a sensitivity, but do not override the failed balance-sheet gate. | `fundamental-79e80c48dd036555`, `research-dbl-2026-05-15-p1-revenue-guidance`, `fundamental-b3dd06efaec87764`, `fundamental-c02d7f1564a6c6e4` |

### Principle scores

| Dimension | Weight | Score | Quality | Rule |
|---|---:|---:|---|---|
| balance sheet conservatism | 20.0% | 1.00 | high | Consolidated net debt exceeds four times FY26 EBITDA and working capital is long. |
| business quality and durability | 20.0% | 3.00 | medium | Large order book and reported EBITDA are offset by working-capital intensity. |
| management alignment and capital allocation | 15.0% | 2.00 | medium | High ownership is offset by promoter encumbrance and a leveraged capital structure. |
| reinvestment runway | 15.0% | 4.00 | medium | Order book and management order-inflow guidance indicate runway. |
| structural growth | 15.0% | 4.00 | medium | EPC and mining forecasts support growth, but are forward estimates and guidance. |
| valuation and expected return | 15.0% | 2.50 | low | The base scenario does not preserve current value after explicit leverage haircuts. |

**Strongest support (reinvestment runway):** year_end_order_book 28830 INR crore (`fundamental-79e80c48dd036555`); Management guided standalone FY27 revenue growth of 30-40%, margin expansion of 150-200bps, and INR 100-120bn order inflow. (`research-dbl-2026-05-15-p1-revenue-guidance`); Mining revenue could rise from approximately INR 16bn in FY26 to INR 25bn, INR 31bn, and INR 40bn in FY27-FY29E. (`research-dbl-2026-05-15-p5-mdo-revenue`)

**Strongest counter-evidence (balance sheet conservatism):** standalone_net_debt 1889 INR crore (`fundamental-dbl-standalone-net-debt-fy26`)

**Warnings:** provisional_holdings_material_to_rebalance

**What would change the result:** Consolidated net debt falls below the configured sell threshold; Promoter encumbrance is released; Working-capital days improve with cash conversion.

**Missing information:** Capital-allocation track record by project; Consolidated debt maturity and restricted-cash schedule; Independent award and execution conversion evidence; Order-book margin and cancellation detail; Project-level returns and claims quality; Reliable enterprise-value bridge and diluted share count.

**Cited evidence and availability dates:** `fundamental-45adc13be8367240` (2026-09-08); `fundamental-670dd97c37c6fd3b` (2026-09-08); `fundamental-79e80c48dd036555` (2026-05-14); `fundamental-7dbb39273996c745` (2026-05-14); `fundamental-86653f5748974c9a` (2026-05-14); `fundamental-b3dd06efaec87764` (2026-05-14); `fundamental-c02d7f1564a6c6e4` (2026-05-14); `fundamental-dbl-consolidated-net-debt-fy26` (2026-05-14); `fundamental-dbl-standalone-net-debt-fy26` (2026-05-14); `price-9ccb6ec1f996ea08` (2026-09-08); `research-dbl-2026-05-15-p1-debt-summary` (2026-05-15); `research-dbl-2026-05-15-p1-epc-estimate` (2026-05-15); `research-dbl-2026-05-15-p1-mdo-revenue` (2026-05-15); `research-dbl-2026-05-15-p1-revenue-guidance` (2026-05-15); `research-dbl-2026-05-15-p5-debt` (2026-05-15); `research-dbl-2026-05-15-p5-mdo-revenue` (2026-05-15).

## Welspun Living Limited

**HOLD / HOLD final action.** Current price INR 207.87 on 2026-09-08 (0 days old); working shares 318,592.360, cost basis INR 20,946,080.58, approximate market value INR 66,225,792.32, current weight 8.7%, and target 5.5%.

The weighted principle score is 3.02 / 5. Bear/base/bull targets are INR 100.80, INR 337.03, and INR 521.36, with three-year CAGRs of -21.4%, 17.5%, and 35.9%.

### Hard gates

| Gate | Status | Consequence | Explanation | Evidence |
|---|---|---|---|---|
| `balance_sheet_liquidity_and_funding` | pass | none | Net debt is below one times FY26 EBITDA and operating cash flow exceeds disclosed capex. | `fundamental-8956bd3e4b3f0535`, `fundamental-c05874765ba9f6a7`, `fundamental-28eeee982f34b8b5`, `fundamental-b9187def6823edb9` |
| `critical_decision_evidence` | pass | none | Revenue, EBITDA, net debt, cash flow, and price support a bounded valuation sensitivity. | `fundamental-d914f48fa6712812`, `fundamental-c05874765ba9f6a7`, `fundamental-8956bd3e4b3f0535`, `price-c492bbff65cd3f25` |
| `current_price` | pass | none | A validated adjusted close exists on the decision date. | `price-c492bbff65cd3f25` |
| `governance_and_alignment` | pass | none | No confirmed sell-mapped governance event is present; low returns on capital constrain the score. | `fundamental-35e0c871992a62d5`, `fundamental-4b37945ed55d7c05` |
| `material_evidence_conflict` | pass | none | The two free-cash-flow figures use different definitions; both remain visible and neither drives the EBITDA scenario. | `fundamental-welspun-company-fcf-fy26`, `fundamental-welspun-ocf-minus-capex-fy26` |
| `thesis_and_valuation` | pass | none | A margin-recovery sensitivity can be constructed; the base case does not clear the 25% hurdle. | `fundamental-d914f48fa6712812`, `fundamental-c05874765ba9f6a7`, `research-welspun-2026-05-15-p2-guidance` |

### Principle scores

| Dimension | Weight | Score | Quality | Rule |
|---|---:|---:|---|---|
| balance sheet conservatism | 20.0% | 3.50 | high | Net debt is below FY26 EBITDA and operating cash flow covers disclosed capex. |
| business quality and durability | 20.0% | 3.00 | medium | Scale and positive cash flow are offset by low reported returns on capital. |
| management alignment and capital allocation | 15.0% | 2.50 | medium | Strong stated cash generation is moderated by low ROCE and conflicting FCF definitions. |
| reinvestment runway | 15.0% | 3.00 | medium | Capex and margin guidance indicate opportunity, but returns remain unproven. |
| structural growth | 15.0% | 3.00 | medium | Double-digit guidance supports growth, but evidence is management guidance rather than achieved results. |
| valuation and expected return | 15.0% | 3.00 | medium | The base margin-recovery scenario is positive but below the 25% CAGR hurdle. |

**Strongest support (balance sheet conservatism):** net_debt 775.40 INR crore (`fundamental-8956bd3e4b3f0535`); ebitda 862.01 INR crore (`fundamental-c05874765ba9f6a7`); operating_cash_flow 1174.98 INR crore (`fundamental-28eeee982f34b8b5`); ppe_cwip_intangible_capex 661.82 INR crore (`fundamental-b9187def6823edb9`)

**Strongest counter-evidence (management alignment and capital allocation):** ocf_minus_disclosed_capex_proxy 513.16 INR crore (`fundamental-welspun-ocf-minus-capex-fy26`); roce 5.61 percent (`fundamental-4b37945ed55d7c05`)

**Warnings:** No portfolio approval overlay triggered.

**What would change the result:** ROCE improves sustainably; Net-debt reduction guidance is achieved or missed; Margin recovery diverges from the base case.

**Missing information:** Comparable capital-allocation record; Debt maturity schedule; Incremental ROCE on recent capex; Independent demand and market-share series; Segment-level normalized margins; Verified share count and independent enterprise-value bridge.

**Cited evidence and availability dates:** `fundamental-163c0130e1a80b24` (2026-09-02); `fundamental-28eeee982f34b8b5` (2026-09-02); `fundamental-35e0c871992a62d5` (2026-09-02); `fundamental-4b37945ed55d7c05` (2026-09-02); `fundamental-8956bd3e4b3f0535` (2026-09-02); `fundamental-b9187def6823edb9` (2026-09-02); `fundamental-c05874765ba9f6a7` (2026-09-02); `fundamental-d914f48fa6712812` (2026-09-02); `fundamental-welspun-company-fcf-fy26` (2026-09-02); `fundamental-welspun-ocf-minus-capex-fy26` (2026-09-02); `price-c492bbff65cd3f25` (2026-09-08); `research-welspun-2026-05-15-p1-estimates` (2026-05-15); `research-welspun-2026-05-15-p2-guidance` (2026-05-15).

## Zee Entertainment Enterprises Limited

**SELL / HOLD final action.** Current price INR 86.31 on 2026-09-08 (0 days old); working shares 91,665.564, cost basis INR 11,405,773.42, approximate market value INR 7,911,654.61, current weight 1.0%, and target 0.0%.

The weighted principle score is 2.60 / 5. Bear/base/bull targets are INR 28.68, INR 91.14, and INR 160.26, with three-year CAGRs of -30.7%, 1.8%, and 22.9%.

### Hard gates

| Gate | Status | Consequence | Explanation | Evidence |
|---|---|---|---|---|
| `balance_sheet_liquidity_and_funding` | pass | none | Cash and treasury investments materially exceed debt including leases, with positive operating cash flow. | `fundamental-b2ce864a0cbf21b1`, `fundamental-2c4d942040875295`, `fundamental-2c2f44ce000554d3` |
| `critical_decision_evidence` | pass | none | Revenue, adjusted EBITDA, cash, debt, and current price are available. | `fundamental-5bdb226df2ca447b`, `fundamental-zee-adjusted-ebitda-fy26`, `price-dc8d7c8637c66233` |
| `current_price` | pass | none | A validated adjusted close exists on the decision date. | `price-dc8d7c8637c66233` |
| `governance_and_alignment` | pass | none | No confirmed sell-mapped governance event is present; low promoter ownership is reflected in the score and remains a limitation. | `fundamental-4d52fd4a962dee07` |
| `material_evidence_conflict` | pass | none | Reported and adjusted EBITDA are retained as distinct definitions; adjusted EBITDA is used consistently in scenarios. | `fundamental-zee-adjusted-ebitda-fy26`, `fundamental-zee-reported-ebitda-fy26` |
| `thesis_and_valuation` | pass | none | A recovery sensitivity is possible, but weak growth and operating evidence reduce the score rather than trigger a binary gate. | `fundamental-5bdb226df2ca447b`, `fundamental-zee-adjusted-ebitda-fy26`, `research-zee-2026-05-20-p1-fy26-summary`, `research-zee-2026-05-20-p2-management` |

### Principle scores

| Dimension | Weight | Score | Quality | Rule |
|---|---:|---:|---|---|
| balance sheet conservatism | 20.0% | 4.50 | high | Cash and treasury investments substantially exceed debt and operating cash flow is positive. |
| business quality and durability | 20.0% | 2.50 | medium | Large revenue base and cash generation are offset by declining adjusted EBITDA and core operating weakness. |
| management alignment and capital allocation | 15.0% | 1.50 | medium | Low promoter ownership and absent FY27 guidance weaken alignment and allocation confidence. |
| reinvestment runway | 15.0% | 2.00 | low | Network reach exists, but the snapshot does not establish high-return reinvestment opportunities. |
| structural growth | 15.0% | 2.00 | medium | Analyst sales forecasts are modest and FY26 reported revenue declined. |
| valuation and expected return | 15.0% | 2.50 | medium | The base recovery sensitivity remains below the 25% hurdle; the analyst target is context only. |

**Strongest support (balance sheet conservatism):** cash_and_treasury_investments 2759.5 INR crore (`fundamental-b2ce864a0cbf21b1`); total_debt_including_lease_liabilities 265.1 INR crore (`fundamental-2c4d942040875295`); operating_cash_flow 708.1 INR crore (`fundamental-2c2f44ce000554d3`)

**Strongest counter-evidence (management alignment and capital allocation):** cash_and_treasury_investments 2759.5 INR crore (`fundamental-b2ce864a0cbf21b1`)

**Warnings:** No portfolio approval overlay triggered.

**What would change the result:** Sustained core EBITDA recovery; Clear management growth and margin guidance; Evidence of stronger alignment or capital returns.

**Missing information:** Comparable digital and linear segment economics; Detailed capital-return and governance remediation evidence; Digital unit economics and incremental returns; Management growth guidance; Restricted-cash breakdown; Verified share count for an absolute equity bridge.

**Cited evidence and availability dates:** `fundamental-2c2f44ce000554d3` (2026-08-10); `fundamental-2c4d942040875295` (2026-08-10); `fundamental-4d52fd4a962dee07` (2026-08-10); `fundamental-5bdb226df2ca447b` (2026-08-10); `fundamental-b2ce864a0cbf21b1` (2026-08-10); `fundamental-zee-adjusted-ebitda-fy26` (2026-08-10); `fundamental-zee-reported-ebitda-fy26` (2026-08-10); `price-dc8d7c8637c66233` (2026-09-08); `research-zee-2026-05-20-p1-forecast` (2026-05-20); `research-zee-2026-05-20-p1-fy26-summary` (2026-05-20); `research-zee-2026-05-20-p1-opinion` (2026-05-20); `research-zee-2026-05-20-p1-q4-results` (2026-05-20); `research-zee-2026-05-20-p2-management` (2026-05-20).

## Limitations and approval boundary

- Provisional open lots are not verified current holdings. Current values, weights, and all material rebalances require owner confirmation.
- The scenario model is a relative operating-value sensitivity, not an independent absolute valuation. It assumes a stable share translation and uses explicit multiple and equity-bridge factors instead of inventing missing diluted share counts.
- Scenario assumptions are prototype judgments, not facts or analyst targets. Bear, base, and bull cases are not probability-weighted.
- Price history is provider-adjusted and corporate actions were not independently reconstructed. The primary BSE TRI series remains unavailable.
- The four-company sleeve omits cash balances, other securities, liabilities, taxes, fees, dividends, and complete NAV. Target cash is a model residual, not a verified account balance.
- No recommendation uses evidence after 2026-09-08, an LLM, live network data, or the historical benchmark result as a scoring input.
