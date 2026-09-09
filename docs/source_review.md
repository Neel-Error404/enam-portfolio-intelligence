# Source Review

## Inventory and readability

- **OBSERVED (supplied source-review record):** Six PDFs were fully inspected. Page counts in filename order are 2 (brief), 4 (Amber), 9 (DBL), 8 (Welspun), 9 (Zee), and 2 (principles).
- **OBSERVED (supplied source-review record):** The workbook is password-encrypted and was opened read-only after the user supplied access. Its five visible sheets are `Notes - Pls Read`, `Amber`, `DBL`, `Zee`, and `Welspun`.
- **OBSERVED:** The supplied SHA-256 baselines are: `0 Briefing Note.pdf` `80CC1427CB277841AD43090A7038507A758F1CCCDB7960D4282D30A0227E8E0D`; `1 Historical Trade Data.xlsx` `44903A7F07E7BF336E98DC6CC17BF884BE50E4BD3A4A2D7A833F6151F217EFD3`; `2.1 Research (Amber).pdf` `37EB4105396ADAD82EF0E2689DA3EA03EE2CA5D24910EAC184DAE717F2D3067E`; `2.2 Research (DBL).pdf` `6A3D058489CB96C64101D100653AD15C343244DD3F41E028E0895EE8F24AF0E7`; `2.3 Research (Welspun).pdf` `965B9A6036C93D73045A21B2223424DB8989AE43488DCD628CF6779F2CB32760`; `2.4 Research (Zee).pdf` `BEEF64B8B8F0A6D4B2196B77EEBB6955A0D42FF5EF2337A2B49780EC0A655E47`; `3 Investment Principles.pdf` `D8948AC1EBE06EF550D37BEA15D11765FCD2149221EDB01B9EAD7A788749E310`.
- **OBSERVED:** Original file bytes are unchanged. All seven originals are under `assessment_inputs/` and hash-verified against the supplied baselines.

## Assignment and submission

- **INFERRED:** The requested work is to infer investor style, strengths, and biases from historical timing and sizing, optionally score behavior, and build an explainable buy/hold/sell prototype only for Amber, DBL, Zee, and Welspun using principles, trade history, analyst research, and company fundamentals.
- It must state corpus, cadence, and threshold assumptions; pipeline and refresh; data and LLM security/privacy; LLM role and hallucination controls; agent roles, guardrails, and HITL if agents are used; and cloud deployment using one or two anchor services.
- **OBSERVED:** Final submission requests a write-up, GitHub code repository, five-minute audio/video, supporting links, and exported AI coding-session history showing decomposition, prompts, course corrections, and accept-versus-rewrite decisions. It must be shared with `aryaman@enam.com` within 24 hours of issue; no contact, sending, deployment, or Git publishing occurs in this phase.

## Principles

- **OBSERVED:** Durable quality includes ROE/ROCE/FCF, owner-operator alignment and capital allocation, internal reinvestment runway, structural rather than cyclical growth, conservative balance sheet, and valuation tied to quality, growth, and duration.
- **OBSERVED:** Avoid commodities, governance issues, turnarounds, external-capital dependency, and complex structures. Numerical references include `>25%` price CAGR and unresolved `X Rs in Y Yrs`.

## Workbook constraints and quality notes

- **OBSERVED (supplied source-review record):** Notes claim Apr 1 2016–Mar 31 2025; FIFO matching and unmatched sells indicate holdings. Amber has 204 data rows (purchases 2017-12-12–2025-08-26; sales through 2025-10-28); DBL 420 (purchases 2016-07-29–2025-12-12; sales through 2025-01-28); Zee 193 (purchases 2019-09-24–2025-06-26; sales through 2025-03-25); Welspun 475 (purchases 2018-01-05–2025-10-09; sales through 2025-11-12).
- **OBSERVED:** There are no trade IDs, broker/account, currency, fees/taxes, or execution times. There are 31 formulas, all cached with no formula errors. A stray Welspun formula `XEW390` inflates the used range. DBL rows 345:347 have purchase dates after sale dates. Missing-date/subtotal-like rows exist. Repeated keys may reflect FIFO and are not proven duplicate errors.

## Research comparability

- **OBSERVED:** Amber is preliminary with no rating or target; DBL is HOLD with target 596; Welspun is BUY with target 175; Zee is REDUCE with fair value 84. Methodologies differ.
- **OBSERVED:** DBL MDO FY27 16.9bn conflicts with FY26 about 16bn/FY27 25bn elsewhere; management's 30–40% growth differs from analyst 26.2%, and debt bases are unclear. Welspun FY26 EBITDA is 7.932bn versus 7.882bn and capex about 4.7bn versus 7.105bn without reconciliation. The Zee report is dated May 19 but says updated after May 20; adjusted and reported EBITDA must not be conflated. All forecasts are estimates or management claims, not verified outcomes.

## Unsupported or missing inputs

- **UNRESOLVED:** The brief says ten years spanning 2015–25, while the workbook note and later-dated rows conflict. Latest-report freshness is undefined.
- **UNRESOLVED:** No benchmark, objective, risk, timing, cost, tax, dividend, cash, corporate-action, or starting-capital rules are supplied. The X/Y threshold is unfinished; `>25%` CAGR lacks horizon and dividend basis; no validation split exists.
- **UNRESOLVED:** External filings, calls, current market data, benchmark data, and secure sharing/retention interpretation are absent. The supplied data alone cannot support a future-outperformance claim or comparable report-derived ranking.
