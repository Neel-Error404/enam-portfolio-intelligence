# Deterministic Decision Methodology

## Boundary

The decision date is **2026-09-08**. The engine reads only the frozen Phase 4 evidence snapshot,
the Phase 4 historical-comparison artifact, and the explicit Phase 5 configuration. It does not
open the workbook, access a network, call an LLM, or infer missing facts. Evidence is eligible only
when its publication or trading date is on or before the decision date.

Workbook open lots are used solely as a **provisional working view** of holdings. They are not
verified live holdings. Current weights and any rebalance that depends on them require human
confirmation.

## Four-layer decision process

### 1. Hard gates

Each gate has a stable code, `pass`, `fail`, or `unknown` status, cited evidence IDs, an explanation,
and one of three consequences: `none`, `review_required`, or `sell`. A non-passing sell gate takes
priority over a review gate. A failed gate is never diluted by the weighted principle score.

The configured gates cover critical evidence, current price, material conflicts, governance and
alignment, balance-sheet/liquidity/funding risk, and thesis/valuation feasibility. DBL's prototype
balance-sheet sell rule is triggered when consolidated net debt exceeds 4.0 times the selected
annual EBITDA. This is an explicit assessment convention, not a supplied policy or industry rule.

### 2. Investment-principle scoring

Scores range from 0 to 5. A missing score remains unavailable and makes the weighted total
unavailable; it is never replaced by a neutral score. The prototype weights are:

| Dimension | Weight |
|---|---:|
| Business quality and durability | 20% |
| Management alignment and capital allocation | 15% |
| Reinvestment runway | 15% |
| Structural growth | 15% |
| Balance-sheet conservatism | 20% |
| Valuation and expected return | 15% |

The total is `sum(dimension score x dimension weight)` and remains on a 0-5 scale. The prototype
quality threshold is 3.00. Indicators are sector-aware, while the six dimensions and weights are
common. Each result retains its rule, supporting evidence, counter-evidence, missing information,
and evidence-quality label.

### 3. Scenario valuation

The available snapshot does not contain a consistently verified diluted share count and full
enterprise-value bridge for every company. The engine therefore uses a transparent **relative
operating-value sensitivity**, not a false-precision absolute DCF and not an analyst target price.
For each three-year scenario:

```text
terminal revenue = starting revenue x (1 + annual growth)^3
terminal operating metric = terminal revenue x terminal margin
operating growth factor = terminal operating metric / starting operating metric
target price = starting price x operating growth factor
             x multiple-change factor x equity-bridge factor
price CAGR = (target price / starting price)^(1/3) - 1
```

The starting operating metric is EBITDA (adjusted EBITDA for Zee). The multiple-change factor
represents rerating or derating relative to the starting operating-value relationship. The
equity-bridge factor explicitly haircuts or improves the translation from operating value to
equity value for leverage and cash-flow risk. The method assumes stable share translation and is
best read as a sensitivity. All growth, margin, multiple, and equity-bridge assumptions are in
[`config/decision_engine.json`](../config/decision_engine.json).

The working interpretation of the incomplete investment-principle wording is a price CAGR greater
than 25%, approximately a doubling in three years. The comparison is strict: exactly 25% does not
clear the hurdle. Bear and bull cases are sensitivities and have no assigned probabilities.

### 4. Position sizing and action mapping

The current working value is `provisional shares x latest validated adjusted close on or before the
decision date`. Current company weights are normalized within only the represented four-company
sleeve.

For a company with no blocking gate, an available score at or above 3.00, and a positive base CAGR,
the unscaled target weight is:

```text
4% position bear-loss budget / max(abs(bear CAGR), 10% sizing floor)
x (weighted score / 5)
x evidence-confidence factor
x min(base CAGR / 25%, 1)
```

If aggregate targets exceed 100%, they are scaled pro rata; otherwise the residual remains cash.
This is a loss-budget approach, not a universal single-stock cap. The 4% budget, 10% sizing floor,
and confidence factors are prototype assumptions. Position bear portfolio-at-risk is `absolute
target weight x max(-bear CAGR, 0)`. It is not statistical VaR.

The five-percentage-point band suppresses small rebalances. With no blocking gate:

- `BUY`: quality passes, base CAGR is greater than 25%, and target exceeds current by at least 5pp.
- `HOLD`: the thesis remains investable but valuation or exposure does not justify a 5pp change.
- `SELL`: quality fails, base CAGR is non-positive, a sell gate fails, or target is at least 5pp
  below current.
- `REVIEW_REQUIRED`: critical evidence or a gate is unresolved, or the portfolio action depends on
  unverified holdings or a concentration approval.

The underlying stance is preserved separately from the final portfolio action. Therefore a
favourable company scenario may still produce a sell/trim stance when the provisional current
weight materially exceeds the risk-sized target, and the final action may then require review
because those holdings are unverified. Conversely, a non-gate SELL stance becomes a final HOLD
when the implied reduction is below 5pp; a sell-mapped hard gate is not suppressed by this band.

## Concentration conventions

Prototype review levels are: single name above 35%, top two above 75%, or HHI above 0.30. Current
HHI uses the four represented holdings. Target HHI and effective positions are conditional on
deployed risky capital; cash is disclosed separately. Effective positions equal `1 / HHI`.
Common-driver labels are qualitative warnings, not correlation estimates.

## Benchmark treatment

S&P BSE 500 TRI remains the intended primary benchmark and unavailable. NIFTY 500 TRI remains a
secondary historical cross-check. Phase 4 matched-period results are displayed as context only and
are not inputs to a hard gate, principle score, valuation, sizing formula, stance, or action. No
price index substitutes for the missing primary TRI.

## Reproducibility

[`scripts/build_decision_snapshot.py`](../scripts/build_decision_snapshot.py) rebuilds the JSON and
Markdown outputs entirely offline. The snapshot SHA-256 covers the canonical decision payload and
must be identical when the frozen inputs and configuration are unchanged.
