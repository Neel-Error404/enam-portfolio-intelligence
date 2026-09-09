# Historical Performance and Investor-Behaviour Analysis

Analysis cutoff: **2025-12-12**.

Results use only normalized `IngestionResult` records. They are gross, price-only results before
fees, taxes, dividends, and corporate actions. Transactions after the workbook's stated 2025-03-31
endpoint are retained through the declared cutoff.

## Coverage and exclusions

| Input records | Realized lots | Provisional open lots | Quarantined | Structural | After stated period | After cutoff |
|---:|---:|---:|---:|---:|---:|---:|
| 1304 | 712 | 462 | 3 | 127 | 144 | 0 |

Quarantined, structural, and post-cutoff records are excluded from every calculation. Provisional
open lots are excluded from realized-return calculations. The 127 structural records comprise 12
header rows and the 115 ignored data rows reported in Phase 2.

### Reconciliation to Phase 2

- Accepted lot population: `712 + 462 = 1,174`, matching the Phase 2 realized and open counts.
- Accepted purchase cost: `686,967,199.03`, matching the sum of Phase 2 company purchase amounts.
- Realized sale proceeds: `825,022,567.78`, matching the sum of Phase 2 company sale amounts.
- Excluded data rows: 3 quarantined plus 115 ignored, matching Phase 2. Header rows are retained as
  structural lineage but were not included in Phase 2's data-row counts.
- Post-2025-03-31 rows: 144, matching `49 + 36 + 4 + 55` from the Phase 2 company summaries.

## Methodology

- Lot profit = sale amount minus purchase amount.
- Lot simple return = sale amount divided by purchase amount, minus one.
- Headline cost-weighted return = total net realized profit divided by total realized purchase
  cost.
- Annualized return is calculated only at 365 holding days or longer as
  `(sale amount / purchase amount)^(365 / holding days) - 1`.
- Gross profits sum positive lot profits; gross losses are the positive magnitude of negative lot
  profits.
- Win rate divides winning lots by all eligible realized lots, including breakeven lots in the
  denominator.
- Profit contribution = company net realized profit divided by overall net realized profit; it is
  unavailable when overall net profit is zero.
- Holding bands use days: `<365`, `365-1094`, `1095-1825`, and `>1825`.

## Realized performance

| Scope | Lots | Purchase cost | Sale proceeds | Net profit | Gross profits | Gross losses | Cost-weighted return | W/L/B | Win rate | Mean lot return | Median lot return | Mean days | Median days | Profit contribution |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Overall | 712 | 342,729,061.29 | 825,022,567.78 | 482,293,506.49 | 518,800,644.98 | 36,507,138.49 | 140.7% | 455/256/1 | 63.9% | 105.6% | 26.1% | 720.81 | 589.00 | n/a |
| Amber Enterprises | 191 | 207,483,377.55 | 678,113,140.56 | 470,629,763.01 | 471,053,652.54 | 423,889.53 | 226.8% | 187/4/0 | 97.9% | 243.5% | 157.1% | 941.48 | 820.00 | 97.6% |
| Dilip Buildcon | 164 | 91,194,521.59 | 101,635,653.60 | 10,441,132.00 | 36,797,929.14 | 26,356,797.14 | 11.4% | 67/97/0 | 40.9% | 49.3% | -19.5% | 649.55 | 561.00 | 2.2% |
| Welspun Living | 229 | 19,139,381.02 | 26,331,765.46 | 7,192,384.44 | 9,847,643.37 | 2,655,258.92 | 37.6% | 170/58/1 | 74.2% | 97.3% | 33.3% | 761.52 | 608.00 | 1.5% |
| Zee Entertainment Enterprises | 128 | 24,911,781.13 | 18,942,008.16 | -5,969,772.97 | 1,101,419.93 | 7,071,192.90 | -24.0% | 31/97/0 | 24.2% | -13.3% | -26.4% | 410.00 | 341.00 | -1.2% |

The cost-weighted return is the headline realized-return measure. Mean and median lot returns are
shown only as lot-level diagnostics.

## Holding-period results

| Band | Lots | Purchase cost | Realized profit | Cost-weighted return | Win rate | Median days |
|---|---:|---:|---:|---:|---:|---:|
| Less than one year | 225 | 114,655,702.12 | -6,883,945.54 | -6.0% | 48.4% | 131.00 |
| One to three years | 366 | 180,195,051.97 | 266,594,984.15 | 147.9% | 65.8% | 763.00 |
| Three to five years | 66 | 10,398,945.17 | 3,867,209.62 | 37.2% | 75.8% | 1366.00 |
| More than five years | 55 | 37,479,362.03 | 218,715,258.26 | 583.6% | 100.0% | 1999.00 |

### Winners versus losers

| Outcome | Lots | Mean holding days | Median holding days |
|---|---:|---:|---:|
| Winners | 455 | 849.14 | 807.00 |
| Losers | 256 | 491.67 | 446.50 |

Loss-making realized lots were held for materially less time at the median than winning lots.
This is holding asymmetry, not a formal disposition-effect finding: contemporaneous values of sold
and retained positions are unavailable, and company mix can affect the comparison.

## Position sizing and concentration

- Accepted purchase lots: 1,174
- Accepted purchase cost: 686,967,199.03
- Median purchase-lot cost: 137,726.39
- Largest purchase-lot cost: 40,459,741.92

| Company | Accepted purchase-cost share | Gross-positive-profit share |
|---|---:|---:|
| Amber Enterprises | 36.1% | 90.8% |
| Dilip Buildcon | 52.8% | 7.1% |
| Welspun Living | 5.8% | 1.9% |
| Zee Entertainment Enterprises | 5.3% | 0.2% |

The largest accepted lot is 293.77 times the median, but these are FIFO-matched fragments rather
than original order sizes. Dilip Buildcon has the largest accepted historical purchase-cost share,
while Amber contributes most gross positive realized profit.

## Partial open-cost concentration

Open lots are provisional rather than verified current holdings. No unrealized return is calculated
without a dated market price.

| Company | Lots | Quantity | Purchase cost | Open-cost share | Median age days | Oldest age days |
|---|---:|---:|---:|---:|---:|---:|
| Amber Enterprises | 2 | 50,537.75 | 40,462,544.12 | 11.8% | 2921.00 | 2921 |
| Dilip Buildcon | 211 | 814,993.142857 | 271,423,739.62 | 78.8% | 351.00 | 3423 |
| Welspun Living | 213 | 318,592.36 | 20,946,080.58 | 6.1% | 1491.00 | 2376 |
| Zee Entertainment Enterprises | 36 | 91,665.564 | 11,405,773.42 | 3.3% | 290.50 | 626 |

Open-cost HHI is **0.64**, equivalent to **1.56** equal-sized cost-basis positions. These are
partial cost-basis measures, not complete or market-value portfolio weights.

## Inferred trading patterns

Inferred daily events are not original broker orders. All accepted FIFO fragments with the same
company, side, and date are grouped; quantity and amount are summed once and the event rate is
amount divided by quantity. Dates containing both sides are sequence-ambiguous.

| Company | Purchase days | Sale days | Scaling buys | Higher-rate | Lower-rate | Partial sales | Complete exits | Re-entries | Same-day ambiguous | Quantity breaks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Amber Enterprises | 32 | 50 | 30 | 12 | 18 | 49 | 0 | 0 | 1 | 0 |
| Dilip Buildcon | 141 | 27 | 132 | 56 | 76 | 19 | 0 | 0 | 8 | 0 |
| Welspun Living | 162 | 31 | 154 | 71 | 83 | 24 | 1 | 1 | 6 | 0 |
| Zee Entertainment Enterprises | 46 | 20 | 35 | 17 | 18 | 10 | 0 | 0 | 10 | 0 |

## Evidence-backed behaviour findings

### Holding asymmetry — medium confidence

- Observed pattern: Loss-making realized lots were held shorter at the median than winning lots.
- Evidence: 455 winning lots had an 807-day median; 256 losing lots had a 446.5-day median.
- Counter-evidence: Means were also longer for winners, but company mix and very large Amber gains
  materially influence the aggregate result.
- Limitation: This is not a disposition-effect test without contemporaneous values for sold and
  retained positions.

### Open-cost concentration — medium confidence

- Observed pattern: Provisional open purchase cost is concentrated in Dilip Buildcon.
- Evidence: It represents 78.8% of 462 provisional lots' purchase cost; HHI is 0.64 and the
  effective position count is 1.56.
- Counter-evidence: The other three companies account for 21.2% of provisional open cost, and
  Amber's two old open fragments account for 11.8%.
- Limitation: This is partial cost basis, not current portfolio weight. Cash, other holdings,
  current prices, and complete NAV are unknown.

### Purchase sizing — medium confidence

- Observed pattern: Accepted FIFO lot sizes vary materially.
- Evidence: Across 1,174 lots, the largest purchase cost is 293.77 times the median.
- Counter-evidence: Dilip Buildcon accounts for 52.8% of accepted purchase cost, so company mix
  contributes to the dispersion.
- Limitation: FIFO fragmentation can make lot-size dispersion different from original order-size
  dispersion.

### Inferred scaling — low confidence

- Observed pattern: Daily grouped records are consistent with repeated scaling while positions
  remained open.
- Evidence: 351 inferred scaling purchase days include 156 at a higher and 195 at a lower weighted
  rate than the preceding purchase day.
- Counter-evidence: 25 dates contain both inferred purchases and sales; these are sequence-
  ambiguous. Only one complete exit and one later re-entry were inferable, both in Welspun.
- Limitation: Daily groups merge FIFO fragments and may combine multiple orders. Averaging-down,
  trimming intent, re-entry intent, and thesis persistence cannot be established confidently.

## Unsupported findings and metrics

The data does not support claims of a formal disposition effect, premature selling, market-timing
skill, alpha, or benchmark outperformance. Portfolio NAV return, drawdown, Sharpe ratio, XIRR,
complete attribution, current market-value weights, and unrealized returns are not calculated.

The workbook lacks complete cash balances, other securities, dated market values, fees, taxes,
dividends, corporate actions, and original execution/order history. The supplied 2026 analyst
reports are not used to explain historical transactions.

## Deferred benchmark and point-in-time questions

- Primary future benchmark: S&P BSE 500 TRI.
- Secondary cross-check: NIFTY 500 TRI.
- Obtain dated benchmark and security-price histories before measuring relative returns or
  post-sale outcomes.
- Establish point-in-time corporate-action, dividend, fee, tax, cash, and portfolio-universe
  treatment before broader attribution.
