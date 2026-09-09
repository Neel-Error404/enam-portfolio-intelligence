# Historical Trade Workbook Ingestion Report

Generated from `assessment_inputs/1 Historical Trade Data.xlsx` using the read-only Phase 2
pipeline. The encrypted workbook was decrypted in memory. No decrypted workbook or password was
written to disk, logs, documentation, or generated artifacts.

Source rows considered are rows 4 through the last non-empty A:H row. The three validated header
rows are retained as structural lineage but excluded from the source-row counts below. Totals use
only accepted realized and provisionally open lots; quarantined and structural rows are excluded.

| Sheet | Source rows | Realized | Open | Quarantined | Ignored |
|---|---:|---:|---:|---:|---:|
| Amber | 204 | 191 | 2 | 0 | 11 |
| DBL | 420 | 164 | 211 | 3 | 42 |
| Zee | 193 | 128 | 36 | 0 | 29 |
| Welspun | 475 | 229 | 213 | 0 | 33 |

## Amber

- Purchase quantity: 211,987.5
- Sale quantity: 161,449.75
- Provisionally open quantity: 50,537.75
- Realized quantity reconciliation difference: 0
- Purchase amount: 247,945,921.67
- Sale amount: 678,113,140.56
- Purchase recorded-minus-calculated difference: 0.00
- Sale recorded-minus-calculated difference: 0.00
- Transaction date range: 2017-12-12 to 2025-10-28
- Rows dated after 2025-03-31: 49
- Ignored/quarantined reasons: blank: 4; undated aggregate: 7

## DBL

- Purchase quantity: 1,051,296.642857
- Sale quantity: 236,303.5
- Provisionally open quantity: 814,993.142857
- Realized quantity reconciliation difference: 0
- Purchase amount: 362,618,261.21
- Sale amount: 101,635,653.60
- Purchase recorded-minus-calculated difference: 0.00
- Sale recorded-minus-calculated difference: 0.00
- Transaction date range: 2016-07-29 to 2025-12-12
- Rows dated after 2025-03-31: 36
- Ignored/quarantined reasons: blank: 22; purchase after sale: 3; undated aggregate: 20
- Quarantined rows: 345, 346, and 347. Each has purchase date 2018-07-17 after sale date
  2018-07-05.

## Zee

- Purchase quantity: 225,700.54
- Sale quantity: 134,034.976
- Provisionally open quantity: 91,665.564
- Realized quantity reconciliation difference: 0
- Purchase amount: 36,317,554.55
- Sale amount: 18,942,008.16
- Purchase recorded-minus-calculated difference: 0.00
- Sale recorded-minus-calculated difference: 0.00
- Transaction date range: 2019-09-24 to 2025-06-26
- Rows dated after 2025-03-31: 4
- Ignored/quarantined reasons: blank: 13; undated aggregate: 16

## Welspun

- Purchase quantity: 539,445.7
- Sale quantity: 220,853.34
- Provisionally open quantity: 318,592.36
- Realized quantity reconciliation difference: 0
- Purchase amount: 40,085,461.60
- Sale amount: 26,331,765.46
- Purchase recorded-minus-calculated difference: 0.00
- Sale recorded-minus-calculated difference: 0.00
- Transaction date range: 2018-01-05 to 2025-11-12
- Rows dated after 2025-03-31: 55
- Ignored/quarantined reasons: blank: 16; undated aggregate: 17
- The stray `XEW390` formula was outside A:H and had no effect on the parsed row range.

## Reconciliation interpretation

- Realized quantity differences are zero for all four sheets: accepted realized purchase
  quantities equal accepted sale quantities.
- Recorded-minus-calculated amount differences round to 0.00 for every sheet using an absolute
  row-level tolerance of 0.02 currency units.
- Open quantities are sums of accepted purchase lots with no sale fields; they are provisional
  because the workbook's unmatched-sell wording remains unresolved.
- Repeated rows and keys were retained. No automatic deduplication was performed.
- Transactions after the workbook's stated 2025-03-31 end date were retained and counted.

## Remaining limitations

- This is an already FIFO-matched lot dataset, not the original execution ledger.
- No portfolio NAV or execution-ledger completeness is claimed.
- Cash balances, fees, taxes, dividends, corporate actions, and original order IDs are unavailable.
- Undated numeric aggregate rows are structural evidence, not trade lots; they remain traceable by
  sheet and row in the in-memory ingestion result.
- The workbook statement about unmatched sells remains unresolved and is not used as a holdings
  rule.
- No performance, benchmark, or recommendation conclusion is made in this phase.
