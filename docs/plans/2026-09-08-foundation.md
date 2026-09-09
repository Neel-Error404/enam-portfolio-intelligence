# Foundation Plan — 2026-09-08

## Outcome

Create a Python 3.12 repository foundation with protected supplied inputs and a tested, deterministic project-path configuration seam.

## Boundaries

Only the listed repository files and input relocation are in scope. Historical analysis, recommendations, LLM/RAG/agents, UI, cloud, external data, deployment, sending, and Git publishing are excluded.

## Tasks

1. Verify input hashes; relocate originals to `assessment_inputs/` without changing bytes.
2. Add minimal project metadata, source-review notes, and explicit scope decisions.
3. Drive `ProjectPaths` behavior from public tests, then add the smallest implementation.
4. Provision Python 3.12 locally and run Foundation checks.

## Checks

Verify source hashes before and after relocation; run focused pytest, Ruff format/check, mypy, ignore-rule, and credential-text scans. The user chose subagent-driven execution; no commit steps are included.
