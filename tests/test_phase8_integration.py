import json
from decimal import Decimal
from pathlib import Path

from enam_assessment.intelligence import (
    ANSWER_CONTRACT_VERSION,
    ANSWER_PROMPT_VERSION,
    AnswerStatus,
    QuestionScope,
    build_question_context,
    generate_grounded_answer,
)
from enam_assessment.memo_provider import ProviderResult
from enam_assessment.portfolio_session import calculate_holdings_overlay, recalculate_scenario
from enam_assessment.portfolio_ui import load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]


class ContextEchoProvider:
    calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def deployment_id(self) -> str:
        return "fake-context-echo"

    @property
    def reasoning_effort(self) -> str:
        return "low"

    @property
    def max_output_tokens(self) -> int:
        return 2200

    def generate(
        self,
        *,
        system_prompt: str,
        context: dict[str, object],
        response_schema: dict[str, object],
    ) -> ProviderResult:
        self.calls += 1
        evidence = context["evidence"]
        assert isinstance(evidence, list) and evidence
        claim = {
            "text": "The bounded context supports this explanation without changing the decision.",
            "evidence_ids": [evidence[0]["evidence_id"]],
            "category": "grounded_explanation",
        }
        return ProviderResult(
            json.dumps(
                {
                    "scope": context["scope"],
                    "company_ids": context["company_ids"],
                    "decision_snapshot_sha256": context["decision_snapshot_sha256"],
                    "context_hash": context["context_hash"],
                    "answer_contract_version": ANSWER_CONTRACT_VERSION,
                    "prompt_version": ANSWER_PROMPT_VERSION,
                    "direct_answer": claim,
                    "supporting_points": [claim],
                    "counterpoints": [],
                    "relevant_unknowns": [],
                    "change_conditions": [],
                }
            )
        )


def test_real_artifacts_support_connected_overlay_scenario_and_grounded_answer() -> None:
    data = load_dashboard_data(ROOT)
    decision = data.decision("amber")
    frozen = decision.stable_payload()
    overlay = calculate_holdings_overlay(
        data.decisions,
        share_overrides={"amber": Decimal("50000")},
        available_cash=Decimal("1000000"),
    )
    base = next(item for item in decision.scenarios if item["input"]["name"] == "base")
    raw = base["input"]
    delta = recalculate_scenario(
        decision,
        scenario_name="base",
        annual_revenue_growth=Decimal(str(raw["annual_revenue_growth"])) + Decimal("0.01"),
        terminal_margin=Decimal(str(raw["terminal_margin"])),
        multiple_change_factor=Decimal(str(raw["multiple_change_factor"])),
        equity_bridge_factor=Decimal(str(raw["equity_bridge_factor"])),
    )
    context = build_question_context(
        data,
        scope=QuestionScope.SCENARIO_DELTA,
        question="Explain what changed in the scenario.",
        company_ids=("amber",),
        scenario_delta=delta,
    )
    provider = ContextEchoProvider()
    result = generate_grounded_answer(
        context,
        provider,
        system_prompt=(ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(
            encoding="utf-8"
        ),
    )

    assert overlay.uses_verified_values is True
    assert overlay.cash_weight > 0
    assert "scenario:amber:base" in context.included_evidence_ids
    assert result.status is AnswerStatus.GENERATED
    assert provider.calls == 1
    assert decision.stable_payload() == frozen
    assert data.portfolio["snapshot_sha256"] == decision.decision_snapshot_sha256
