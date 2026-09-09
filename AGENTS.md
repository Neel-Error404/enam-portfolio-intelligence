# ENAM Assessment Repository

Use Python 3.12 with `py` and PowerShell. Keep `assessment_inputs/` immutable and ignored; never read secrets or put source-data credentials in code or documentation.

Raise explicit, actionable errors rather than adding silent fallbacks. Run tests in order: Foundation, Component, Integration, Workflow, Stress. Do not perform Git, network, deployment, or other external operations without explicit authorization.

Workbook ingestion is read-only and limited to columns A:H on the four expected company sheets. Preserve every parsed row's sheet, row number, classification, and validation results. Read `README.md`, `docs/DATA_DICTIONARY.md`, and `docs/INGESTION_REPORT.md` before extending analysis.
