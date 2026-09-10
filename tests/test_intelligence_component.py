import json
from pathlib import Path

import pytest

from enam_assessment.errors import MemoProviderError
from enam_assessment.intelligence import (
    ANSWER_CONTRACT_VERSION,
    ANSWER_PROMPT_VERSION,
    AnswerStatus,
    QuestionContext,
    QuestionScope,
    build_question_context,
    generate_grounded_answer,
    get_or_generate_answer,
)
from enam_assessment.memo_provider import ProviderResult, ProviderUsage
from enam_assessment.portfolio_ui import DashboardData, load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]


class FakeAnswerProvider:
    def __init__(self, *, mutation: str | None = None) -> None:
        self.mutation = mutation
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def deployment_id(self) -> str:
        return "fake-portfolio-intelligence"

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
        assert "portfolio-intelligence layer" in system_prompt
        assert response_schema["additionalProperties"] is False
        self.calls += 1
        evidence = context["evidence"]
        assert isinstance(evidence, list) and evidence
        evidence_id = evidence[0]["evidence_id"]
        claim = {
            "text": "The cited evidence supports this explanation of the frozen decision.",
            "evidence_ids": [evidence_id],
            "category": "grounded_explanation",
        }
        payload = {
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
        if self.mutation == "citation":
            payload["direct_answer"]["evidence_ids"] = ["unknown"]
        elif self.mutation == "identity":
            payload["company_ids"] = ["wrong"]
        return ProviderResult(
            output_text=json.dumps(payload),
            response_id="fake-response",
            usage=ProviderUsage(800, 200, 1000),
        )


class FailingAnswerProvider(FakeAnswerProvider):
    def generate(
        self,
        *,
        system_prompt: str,
        context: dict[str, object],
        response_schema: dict[str, object],
    ) -> ProviderResult:
        self.calls += 1
        raise MemoProviderError("Synthetic provider failure.")


@pytest.fixture
def dashboard() -> DashboardData:
    return load_dashboard_data(ROOT)


def test_valid_fake_answer_is_generated_and_session_cache_prevents_duplicate_calls(
    dashboard: DashboardData,
) -> None:
    context = _context(dashboard)
    provider = FakeAnswerProvider()
    cache = {}

    first, first_cached = get_or_generate_answer(cache, context, provider, system_prompt=_prompt())
    second, second_cached = get_or_generate_answer(
        cache, context, provider, system_prompt=_prompt()
    )

    assert first.status is AnswerStatus.GENERATED
    assert first.answer is not None
    assert first.usage == ProviderUsage(800, 200, 1000)
    assert first_cached is False
    assert second_cached is True
    assert second == first
    assert provider.calls == 1


@pytest.mark.parametrize("mutation", ["citation", "identity"])
def test_invalid_fake_answer_fails_closed(dashboard: DashboardData, mutation: str) -> None:
    artifact = generate_grounded_answer(
        _context(dashboard), FakeAnswerProvider(mutation=mutation), system_prompt=_prompt()
    )

    assert artifact.status is AnswerStatus.VALIDATION_FAILED
    assert artifact.answer is None
    assert artifact.error
    assert artifact.response_id == "fake-response"
    assert artifact.usage == ProviderUsage(800, 200, 1000)


def test_provider_failure_keeps_context_and_explicit_status(dashboard: DashboardData) -> None:
    context = _context(dashboard)
    artifact = generate_grounded_answer(context, FailingAnswerProvider(), system_prompt=_prompt())

    assert artifact.status is AnswerStatus.GENERATION_FAILED
    assert artifact.answer is None
    assert artifact.context.context_hash == context.context_hash
    assert artifact.error == "Synthetic provider failure."


def test_all_question_scopes_assemble_without_network(dashboard: DashboardData) -> None:
    cases = (
        (QuestionScope.COMPANY_BRIEF, ("amber",), 3500),
        (QuestionScope.COMPANY, ("dbl",), 2500),
        (QuestionScope.PORTFOLIO, (), 2500),
        (QuestionScope.COMPARISON, ("welspun", "zee"), 2500),
        (QuestionScope.BEHAVIOUR, (), 2500),
    )

    contexts = tuple(
        build_question_context(
            dashboard,
            scope=scope,
            question="Explain this scope.",
            company_ids=company_ids,
            input_token_budget=budget,
        )
        for scope, company_ids, budget in cases
    )

    assert [item.scope for item in contexts] == [item[0] for item in cases]
    assert all(item.included_evidence_ids for item in contexts)


def _context(dashboard: DashboardData) -> QuestionContext:
    return build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Why is Amber review required?",
        company_ids=("amber",),
    )


def _prompt() -> str:
    return (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
