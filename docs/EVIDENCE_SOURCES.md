# Evidence Sources and Provenance

Snapshot date: **2026-09-08**. The machine-readable manifest is
[`evidence/manifest.json`](../evidence/manifest.json); its SHA-256 identity is
`be92698be561ae08e41763a539f0416ddfa754267692d7d5c8c173afd51488c6`.

## Identifier mapping

| Internal ID | Company / series | NSE | BSE | ISIN / index code | History note |
|---|---|---|---|---|---|
| `amber` | Amber Enterprises India Limited | `AMBER` | `540902` | `INE371P01015` | NSE listing date 2018-01-30. |
| `dbl` | Dilip Buildcon Limited | `DBL` | `540047` | `INE917M01012` | NSE listing date 2016-08-11. |
| `zee` | Zee Entertainment Enterprises Limited | `ZEEL` | `505537` | `INE256A01028` | Earlier Zee Telefilms legal-name history remains unverified from a captured primary notice. |
| `welspun` | Welspun Living Limited | `WELSPUNLIV` | `514162` | `INE192B01031` | Official IR site says formerly Welspun India; exact exchange-effective `WELSPUNIND` change date remains unresolved. |
| `bse-500-tri` | S&P BSE 500 TRI | n/a | `BSE500T` | BSE index code `17` | Primary benchmark; history is authentication-gated. |
| `nifty-500-tri` | NIFTY 500 TRI | `NIFTY 500` | n/a | official `Total Returns Index` field | Secondary cross-check; daily series captured. |

Company identifiers were verified against the [official NSE security master](https://archives.nseindia.com/content/equities/EQUITY_L.csv), official NSE quote pages, and official BSE security pages. The primary benchmark identifier was verified through [BSE index metadata](https://www.bseindices.com/AsiaIndexAPI/api/AsiaIndexDescriptionnew/w?indexcode=17).

## Market and benchmark sources

| Source | Role | Captured coverage | Status |
|---|---|---|---|
| [BSE 500 official history endpoint](https://www.bseindices.com/AsiaIndexAPI/api/GetHistoricalPRTRData_Asia/w?code=17&Fromdate=01012016&Todate=08092026&flag=1&type=1) | Primary benchmark | Requested 2016-01-01 to 2026-09-08 | **Unavailable.** Unauthenticated requests returned an empty array and the application exposes historical export behind member login. No price-index substitute was used. |
| [NIFTY historical-data endpoint](https://www.niftyindices.com/Backpage/getHistoricaldataDBtoString) | Secondary TRI | 2,647 daily observations, 2016-01-01 to 2026-09-07 | Available. Request used `name=NIFTY 500` and `DataType=TR`; the `Total Returns Index` field is used. |
| Yahoo chart API | Company prices | Amber 2,128 rows from 2018-01-30; DBL 2,489 from 2016-08-11; Zee and Welspun 2,643 each from 2016-01-01; all through 2026-09-08 | Available as a clearly labelled secondary source. OHLC, adjusted close, and volume are retained where present. |

Yahoo was used only because an official, reproducible daily company-price history was not
practically accessible. Its adjusted close is recorded as provider-adjusted; this snapshot does
not independently reconstruct every dividend, split, or other corporate action. Null rows are not
filled. Raw network responses remain in the system temporary directory, outside Git.

## Latest official company sources

- Amber: [Q4 FY26 investor presentation](https://www.ir.ambergroupindia.com/wp-content/uploads/2026/05/Investor-Presentation-Q4-FY26.pdf) and [press release](https://www.ir.ambergroupindia.com/wp-content/uploads/2026/05/Press-Release-Q4FY26-16.05.2026.pdf), dated 2026-05-16.
- Dilip Buildcon: [audited Q4/FY26 results](https://dilipbuildcon.com/wp-content/uploads/2026/05/Results-Q4-FY-2025-26.pdf), approved 2026-05-14.
- Zee: [FY26 integrated annual report](https://assets-prod.zee.com/wp-content/uploads/2026/08/Zee_IR_FY26.pdf), published 2026-08-10; its financial statements were approved 2026-05-19.
- Welspun Living: [FY26 annual report](https://www.welspunliving.com/uploads/investor_data/investorreport_9008.pdf). Because the precise upload date was not exposed, 2026-09-02—the first verified investor-page availability—is used conservatively.

The manifest records the source URL or protected local path, publication/availability date,
retrieval timestamp, coverage, source class, validation status, and a content hash where a stable
download was available. Amber, DBL, and Welspun official PDFs were hashed from temporary downloads.
Zee's official PDF returned 403 to direct `curl`, but Firecrawl retrieved the same official
250-page document; it is marked accordingly rather than assigned an invented hash.

## Supplied analyst research

The four ignored local PDFs are referenced by relative path and SHA-256 only. Extracted claims are
typed as reported fact, analyst estimate, analyst opinion, or management guidance. They were
published on 2026-05-15 to 2026-05-20 and cannot explain trades made during 2016–2025.

Zee's report has a temporal anomaly: the cover is dated 2026-05-19, while page 7 says it was
updated after a 2026-05-20 release. Claims without version-level proof use 2026-05-20 as their
conservative availability date.

## Retrieval tools and limitations

Firecrawl MCP was used to find and retrieve official pages/PDFs when direct endpoints were blocked;
Parallel Web was used for bounded official-source discovery and cross-checking. The discovery runs
included Parallel searches `search_dbbb3442a25d8c7789ff88d5bf6d70bf` and
`search_a3d3e6d68014ace415beca2329987666`, and Firecrawl search
`01a080ae-85f5-730c-8ab5-0d8484140407`. These tools are discovery/retrieval paths, not authority:
the cited exchange, company, or index-provider document remains the evidence source.

Blocked investor pages were not bypassed indefinitely and no provider was silently changed. No
private, authenticated, or paid system was accessed.
