# Historical Analysis Methodology

Phase 3 consumes only `IngestionResult` and `TradeLotRecord`. It does not reopen, reinterpret, or
independently parse the workbook.

## Scope and cutoff

- Analysis cutoff: 2025-12-12, the latest accepted transaction date in the supplied workbook.
- Accepted records after the workbook's stated 2025-03-31 endpoint remain included and are
  counted separately.
- Quarantined, structural, and post-cutoff records are excluded from calculations.
- Provisionally open lots contribute only to quantity, purchase cost, age, and partial open-cost
  concentration. They are not asserted to be verified current holdings.
- All performance is gross and price-only, before fees, taxes, dividends, and corporate actions.

## Realized calculations

For each valid realized lot:

- `profit = sale_amount - purchase_amount`
- `simple_return = sale_amount / purchase_amount - 1`
- `holding_days = sale_date - purchase_date`
- when `holding_days >= 365`,
  `annualized_return = (sale_amount / purchase_amount) ** (365 / holding_days) - 1`

Headline company and overall return is cost-weighted:

`cost_weighted_return = sum(realized_profit) / sum(realized_purchase_amount)`

An unweighted average of lot returns is reported only as a lot-level diagnostic. Gross losses are
shown as a positive magnitude. Win rate uses all eligible realized lots, including breakeven lots,
as its denominator. Company profit contribution is signed company net profit divided by overall
net realized profit; it is unavailable when overall net profit is zero.

Holding bands use deterministic day boundaries: less than 365 days, 365–1094 days, 1095–1825
days, and more than 1825 days. Shorter-than-365-day returns are not annualized.

## Concentration

Accepted purchase-cost shares use realized and provisional open lots. Realized-profit
concentration uses each company's share of total gross positive profits so loss offsets cannot
produce misleading negative or greater-than-100% concentration weights.

Provisional open-cost weights use only provisional open purchase amounts:

- `weight_i = company_open_cost_i / total_open_cost`
- `HHI = sum(weight_i ** 2)`
- `effective_positions = 1 / HHI`

These are partial cost-basis measures, not market-value portfolio weights.

## Inferred daily events

FIFO fragments are grouped only by company, side, and calendar date. Quantities and amounts are
summed once, and the inferred event rate is total amount divided by total quantity. This preserves
lot-level totals while reducing obvious FIFO fragmentation. A daily group may combine several
broker orders and is never labelled an original order.

Scaling is counted only when a purchase day begins with a positive inferred quantity balance.
Higher/lower purchase-rate comparisons use consecutive inferred purchase-day weighted rates while
the position remains open. A sale that leaves a positive balance is an inferred trim; a sale that
reduces balance to zero is an inferred complete exit. A later purchase from zero is an inferred
re-entry. Dates containing both purchases and sales are sequence-ambiguous and excluded from those
specific classifications.

These rules support descriptive patterns only. They cannot establish intention, averaging-down
psychology, a disposition effect, premature selling, market timing, alpha, or benchmark
outperformance.

## Phase 4 point-in-time evidence

The evidence snapshot uses a configurable default `analysis_as_of` of 2026-09-08. A filing or
research claim enters a snapshot on its publication or conservatively verified availability date,
not its fiscal period end. Market observations enter on their trading date. Later records are
retained as explicit temporal exclusions rather than silently ignored.

Stable evidence IDs hash the semantic identity of a fact or observation and exclude retrieval
time. The manifest separately records retrieval timestamps, locations, coverage, validation
status, and source hashes where available. Conflicting records keep separate IDs and reciprocal
links; no winner is selected merely because one value is newer or more convenient.

Historical market comparisons use exact purchase and sale dates. Company return is
`adjusted_close_sale / adjusted_close_purchase - 1`; benchmark return uses the corresponding TRI
levels; relative return is company return minus benchmark return. Aggregate comparison returns are
weighted by the workbook purchase cost of matched lots. A missing date makes that interval
unavailable—there is no forward-fill, backfill, or future-price substitution.

S&P BSE 500 TRI (`BSE500T`) remains primary but its official daily history was unavailable without
authentication. NIFTY 500 TRI is the secondary cross-check and uses the official `Total Returns
Index` field. No price index replaces a missing TRI. Company adjusted closes come from a labelled
secondary provider and are not independently reconstructed from corporate-action events.
