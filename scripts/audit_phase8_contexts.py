"""Build a sanitized offline audit of the Phase 8A question contexts."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from enam_assessment.intelligence import (
    QuestionScope,
    answer_response_json_schema,
    build_question_context,
    citation_cards,
    estimated_request_tokens,
)
from enam_assessment.portfolio_session import calculate_holdings_overlay, recalculate_scenario
from enam_assessment.portfolio_ui import load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data = load_dashboard_data(ROOT)
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    amber = data.decision("amber")
    base = next(item for item in amber.scenarios if item["input"]["name"] == "base")
    raw = base["input"]
    delta = recalculate_scenario(
        amber,
        scenario_name="base",
        annual_revenue_growth=Decimal(str(raw["annual_revenue_growth"])) + Decimal("0.01"),
        terminal_margin=Decimal(str(raw["terminal_margin"])),
        multiple_change_factor=Decimal(str(raw["multiple_change_factor"])),
        equity_bridge_factor=Decimal(str(raw["equity_bridge_factor"])),
    )
    cases = (
        (
            "amber",
            QuestionScope.COMPANY,
            "Why can Amber require review despite its attractive base-case CAGR?",
            ("amber",),
            None,
        ),
        (
            "dbl",
            QuestionScope.COMPANY,
            "Which gate, risk, and missing evidence matter most for DBL?",
            ("dbl",),
            None,
        ),
        (
            "comparison",
            QuestionScope.COMPARISON,
            "Compare Welspun and Zee using only available evidence.",
            ("welspun", "zee"),
            None,
        ),
        (
            "behaviour",
            QuestionScope.BEHAVIOUR,
            "How should historical investor behaviour affect a current decision?",
            (),
            None,
        ),
        (
            "scenario",
            QuestionScope.SCENARIO_DELTA,
            "Explain the deterministic scenario delta.",
            ("amber",),
            delta,
        ),
    )
    contexts: dict[str, object] = {}
    for name, scope, question, company_ids, scenario_delta in cases:
        context = build_question_context(
            data,
            scope=scope,
            question=question,
            company_ids=company_ids,
            scenario_delta=scenario_delta,
        )
        cards = citation_cards(data, context, context.included_evidence_ids)
        contexts[name] = {
            "scope": scope.value,
            "context_hash": context.context_hash,
            "estimated_input_tokens": estimated_request_tokens(
                context,
                system_prompt=prompt,
                response_schema=answer_response_json_schema(context),
            ),
            "included_evidence_ids": list(context.included_evidence_ids),
            "excluded_evidence_ids": list(context.excluded_evidence_ids),
            "evidence_categories": sorted({item.category for item in cards}),
        }
    overlay = calculate_holdings_overlay(
        data.decisions,
        share_overrides={"amber": Decimal("0")},
        available_cash=Decimal("10000000"),
    )
    payload = {
        "decision_snapshot_sha256": data.portfolio["snapshot_sha256"],
        "contexts": contexts,
        "holdings_overlay_check": {
            "cash_weight": str(overlay.cash_weight),
            "hhi": str(overlay.concentration.hhi),
            "requires_review": overlay.concentration.requires_review,
        },
    }
    output = ROOT / "artifacts" / "phase8_dogfood" / "context_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
