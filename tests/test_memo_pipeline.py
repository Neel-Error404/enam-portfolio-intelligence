import json
from pathlib import Path

import pytest

from enam_assessment.errors import MemoProviderError
from enam_assessment.evidence_io import read_snapshot
from enam_assessment.memo import (
    MEMO_CONTRACT_VERSION,
    MEMO_SECTION_NAMES,
    PROMPT_VERSION,
    DecisionMemoInput,
    MemoContext,
    build_memo_context,
    read_decision_memo_inputs,
)
from enam_assessment.memo_generation import MemoStatus, generate_company_memo
from enam_assessment.memo_provider import ProviderResult

ROOT = Path(__file__).resolve().parents[1]


class FakeMemoProvider:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def deployment_id(self) -> str:
        return "fake-structured-model"

    @property
    def reasoning_effort(self) -> str:
        return "medium"

    @property
    def max_output_tokens(self) -> int:
        return 6000

    def generate(
        self,
        *,
        system_prompt: str,
        context: dict[str, object],
        response_schema: dict[str, object],
    ) -> ProviderResult:
        assert "portfolio-intelligence layer" in system_prompt
        assert context["decision"]
        assert response_schema["additionalProperties"] is False
        self.calls += 1
        return ProviderResult(output_text=self.output_text, response_id="fake-response")


class FailingMemoProvider:
    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def deployment_id(self) -> str:
        return "fake-failure"

    @property
    def reasoning_effort(self) -> str:
        return "medium"

    @property
    def max_output_tokens(self) -> int:
        return 6000

    def generate(
        self,
        *,
        system_prompt: str,
        context: dict[str, object],
        response_schema: dict[str, object],
    ) -> ProviderResult:
        raise MemoProviderError("Synthetic provider failure.")


@pytest.fixture
def contexts() -> tuple[MemoContext, ...]:
    decisions = read_decision_memo_inputs(ROOT / "decision" / "decision_snapshot.json")
    evidence = read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")
    return tuple(build_memo_context(item, evidence) for item in decisions)


def test_valid_fake_response_produces_valid_memo(contexts: tuple[MemoContext, ...]) -> None:
    context = contexts[0]
    provider = FakeMemoProvider(
        json.dumps(_response(context.decision, context.allowed_evidence_ids[0]))
    )

    artifact = generate_company_memo(context, provider, system_prompt=_prompt())

    assert artifact.memo_generation_status is MemoStatus.GENERATED
    assert artifact.narrative is not None
    assert artifact.narrative.company_id == context.decision.company_id
    assert artifact.decision.decision_snapshot_sha256 == context.decision.decision_snapshot_sha256
    assert artifact.reasoning_effort == "medium"
    assert artifact.max_output_tokens == 6000
    assert provider.calls == 1


def test_representative_portfolio_intelligence_memo_validates(
    contexts: tuple[MemoContext, ...],
) -> None:
    amber = next(item for item in contexts if item.decision.company_id == "amber")
    response = (ROOT / "tests" / "fixtures" / "validated_memo_amber.json").read_text(
        encoding="utf-8"
    )

    artifact = generate_company_memo(amber, FakeMemoProvider(response), system_prompt=_prompt())

    assert artifact.memo_generation_status is MemoStatus.GENERATED
    assert artifact.narrative is not None
    assert "portfolio weight" in artifact.narrative.executive_summary.text
    assert "evaluator" not in response.lower()


@pytest.mark.parametrize("mutation", ["unknown", "uncited", "company", "action"])
def test_invalid_fake_response_is_not_published(
    contexts: tuple[MemoContext, ...], mutation: str
) -> None:
    context = contexts[0]
    payload = _response(context.decision, context.allowed_evidence_ids[0])
    if mutation == "unknown":
        payload["supporting_evidence"][0]["evidence_ids"] = ["not-allowed"]
    elif mutation == "uncited":
        payload["executive_summary"]["evidence_ids"] = []
    elif mutation == "company":
        payload["company_id"] = "wrong-company"
    else:
        payload["final_portfolio_action"] = "buy"

    artifact = generate_company_memo(
        context, FakeMemoProvider(json.dumps(payload)), system_prompt=_prompt()
    )

    assert artifact.memo_generation_status is MemoStatus.VALIDATION_FAILED
    assert artifact.narrative is None
    assert artifact.decision.final_portfolio_action == context.decision.final_portfolio_action


def test_provider_failure_preserves_deterministic_decision(
    contexts: tuple[MemoContext, ...],
) -> None:
    context = contexts[0]

    artifact = generate_company_memo(context, FailingMemoProvider(), system_prompt=_prompt())

    assert artifact.memo_generation_status is MemoStatus.GENERATION_FAILED
    assert artifact.narrative is None
    assert artifact.decision.stable_payload() == context.decision.stable_payload()
    assert artifact.error == "Synthetic provider failure."


def test_all_four_contexts_assemble_offline_and_are_order_independent(
    contexts: tuple[MemoContext, ...],
) -> None:
    evidence = read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")

    rebuilt = tuple(build_memo_context(item.decision, evidence) for item in reversed(contexts))

    assert {item.decision.company_id for item in contexts} == {
        "amber",
        "dbl",
        "welspun",
        "zee",
    }
    assert {item.decision.company_id: item.stable_payload() for item in contexts} == {
        item.decision.company_id: item.stable_payload() for item in rebuilt
    }


def test_material_conflicts_remain_in_selected_context(
    contexts: tuple[MemoContext, ...],
) -> None:
    amber = next(item for item in contexts if item.decision.company_id == "amber")

    assert any(item.conflicting_evidence_ids for item in amber.evidence)
    assert amber.decision.hard_gates
    assert amber.decision.missing_data_flags


def _prompt() -> str:
    return (ROOT / "prompts" / "company_memo_prompt_v1.txt").read_text(encoding="utf-8")


def _response(decision: DecisionMemoInput, evidence_id: str) -> dict[str, object]:
    claim = {
        "text": "The cited evidence supports the frozen portfolio view.",
        "evidence_ids": [evidence_id],
        "category": "evidence",
    }
    return {
        "company_id": decision.company_id,
        "company_name": decision.company_name,
        "decision_date": decision.decision_date.isoformat(),
        "source_decision_snapshot_hash": decision.decision_snapshot_sha256,
        "memo_contract_version": MEMO_CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "underlying_stance": decision.underlying_stance,
        "final_portfolio_action": decision.final_portfolio_action,
        "executive_summary": claim,
        **{name: [claim] for name in MEMO_SECTION_NAMES},
    }
