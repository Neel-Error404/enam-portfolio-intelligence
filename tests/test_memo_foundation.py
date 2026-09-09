import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from enam_assessment.decision import (
    GateConsequence,
    GateStatus,
    calculate_upper_bound_ratio_gate,
)
from enam_assessment.decision_engine import build_decisions, load_decision_configuration
from enam_assessment.errors import (
    DecisionConsistencyError,
    MemoConfigurationError,
    MemoContextError,
    MemoValidationError,
)
from enam_assessment.evidence import EvidenceSnapshot
from enam_assessment.evidence_io import read_snapshot
from enam_assessment.memo import (
    DECISION_CONTRACT_VERSION,
    MEMO_CONTRACT_VERSION,
    MEMO_SECTION_NAMES,
    PROMPT_VERSION,
    build_memo_context,
    memo_response_json_schema,
    parse_and_validate_memo_response,
    read_decision_memo_inputs,
)
from enam_assessment.memo_provider import AzureOpenAISettings
from enam_assessment.phase5_consistency import (
    read_phase3_open_holdings,
    reconcile_working_holdings,
)

ROOT = Path(__file__).resolve().parents[1]
PHASE5_HASH = "014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89"


def test_working_holdings_reconcile_with_phase3_artifact() -> None:
    _, specs = load_decision_configuration(ROOT / "config" / "decision_engine.json")
    expected = read_phase3_open_holdings(ROOT / "docs" / "HISTORICAL_ANALYSIS.md")

    reconcile_working_holdings(specs, expected)

    assert expected["amber"].shares == Decimal("50537.75")
    assert expected["dbl"].cost_basis == Decimal("271423739.62")
    assert expected["welspun"].shares == Decimal("318592.36")
    assert expected["zee"].cost_basis == Decimal("11405773.42")


def test_working_holdings_mismatch_identifies_company_and_field() -> None:
    _, specs = load_decision_configuration(ROOT / "config" / "decision_engine.json")
    expected = read_phase3_open_holdings(ROOT / "docs" / "HISTORICAL_ANALYSIS.md")
    changed = tuple(
        replace(item, working_shares=item.working_shares + Decimal("1"))
        if item.company_id == "amber"
        else item
        for item in specs
    )

    with pytest.raises(
        DecisionConsistencyError,
        match=r"amber working_shares.*expected 50537\.75.*received 50538\.75",
    ):
        reconcile_working_holdings(changed, expected)


def test_decimal_ratio_gate_and_strict_threshold_boundary() -> None:
    failed = calculate_upper_bound_ratio_gate(
        numerator=Decimal("7244"),
        denominator=Decimal("1766"),
        threshold=Decimal("4.0"),
    )
    boundary = calculate_upper_bound_ratio_gate(
        numerator=Decimal("400"),
        denominator=Decimal("100"),
        threshold=Decimal("4.0"),
    )

    assert failed.ratio == Decimal("7244") / Decimal("1766")
    assert failed.status is GateStatus.FAIL
    assert boundary.status is GateStatus.PASS


def test_dbl_gate_is_recalculated_from_cited_facts_without_changing_phase5() -> None:
    evidence = read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")
    config, specs = load_decision_configuration(ROOT / "config" / "decision_engine.json")
    modified_specs = tuple(
        replace(
            spec,
            gates=tuple(
                replace(
                    gate,
                    status=GateStatus.PASS,
                    consequence=GateConsequence.NONE,
                    explanation="This manual value must be ignored.",
                )
                if spec.company_id == "dbl" and gate.code == "balance_sheet_liquidity_and_funding"
                else gate
                for gate in spec.gates
            ),
        )
        for spec in specs
    )
    history = json.loads(
        (ROOT / "evidence" / "historical_comparisons.json").read_text(encoding="utf-8")
    )
    name_to_id = {
        "Amber Enterprises": "amber",
        "Dilip Buildcon": "dbl",
        "Welspun Living": "welspun",
        "Zee Entertainment Enterprises": "zee",
    }
    context = {
        name_to_id[item["company"]]: item
        for item in history["summary"]
        if item["company"] in name_to_id
    }

    result = build_decisions(evidence, modified_specs, config, historical_context=context)
    gate = next(
        item
        for item in result.company("dbl").gates
        if item.code == "balance_sheet_liquidity_and_funding"
    )

    assert gate.status is GateStatus.FAIL
    assert gate.consequence is GateConsequence.SELL
    assert gate.evidence_ids[:2] == (
        "fundamental-dbl-consolidated-net-debt-fy26",
        "fundamental-c02d7f1564a6c6e4",
    )
    assert "4.10 times FY26 EBITDA" in gate.explanation
    assert config.dbl_net_debt_to_ebitda_sell_threshold == Decimal("4.0")
    assert result.snapshot_sha256 == PHASE5_HASH


def test_prompt_has_portfolio_intelligence_identity_and_no_development_audience() -> None:
    prompt = (ROOT / "prompts" / "company_memo_prompt_v1.txt").read_text(encoding="utf-8")
    lower = prompt.lower()

    assert "portfolio-intelligence layer" in lower
    assert "portfolio owner" in lower
    assert "explain the current investment view" in lower
    assert "deterministic decision is authoritative and immutable" in lower
    assert "every material factual claim" in lower
    assert "supplied allow-list" in lower
    for forbidden in (
        "evaluator",
        "job assessment",
        "submission",
        "development phase",
        "implementation details",
        "product is being demonstrated",
    ):
        assert forbidden not in lower


def test_decision_contract_is_versioned_and_preserves_snapshot_identity() -> None:
    contracts = read_decision_memo_inputs(ROOT / "decision" / "decision_snapshot.json")

    assert len(contracts) == 4
    assert {item.contract_version for item in contracts} == {DECISION_CONTRACT_VERSION}
    assert {item.decision_snapshot_sha256 for item in contracts} == {PHASE5_HASH}
    assert all(item.provisional_holdings for item in contracts)
    assert all(item.evidence_ids for item in contracts)


def test_context_selects_exact_deduplicated_evidence_in_stable_order() -> None:
    contract = read_decision_memo_inputs(ROOT / "decision" / "decision_snapshot.json")[0]
    duplicated = replace(contract, evidence_ids=contract.evidence_ids + contract.evidence_ids[:2])
    snapshot = read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")

    first = build_memo_context(duplicated, snapshot)
    second = build_memo_context(duplicated, snapshot)

    assert first.stable_payload() == second.stable_payload()
    assert first.allowed_evidence_ids == tuple(sorted(set(contract.evidence_ids)))
    assert set(first.allowed_evidence_ids) == set(contract.evidence_ids)


def test_context_rejects_unknown_post_decision_and_wrong_company_evidence() -> None:
    contract = read_decision_memo_inputs(ROOT / "decision" / "decision_snapshot.json")[0]
    snapshot = read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")
    with pytest.raises(MemoContextError, match="not in the frozen Phase 4 snapshot"):
        build_memo_context(
            replace(
                contract,
                evidence_ids=("unknown-evidence",),
                evidence_dates=(("unknown-evidence", contract.decision_date),),
            ),
            snapshot,
        )

    cited = contract.evidence_ids[0]
    future_fundamentals = tuple(
        replace(item, publication_date=contract.decision_date + timedelta(days=1))
        if item.evidence_id == cited
        else item
        for item in snapshot.fundamentals
    )
    future_snapshot = EvidenceSnapshot(
        analysis_as_of=snapshot.analysis_as_of,
        fundamentals=future_fundamentals,
        research=snapshot.research,
        prices=snapshot.prices,
        sources=snapshot.sources,
        temporal_exclusions=snapshot.temporal_exclusions,
    )
    with pytest.raises(MemoContextError, match="after the decision date"):
        build_memo_context(contract, future_snapshot)

    wrong_company = replace(contract, company_id="dbl")
    with pytest.raises(MemoContextError, match="not this company"):
        build_memo_context(wrong_company, snapshot)


def test_memo_schema_and_citation_validation_preserve_immutable_decision() -> None:
    contract = read_decision_memo_inputs(ROOT / "decision" / "decision_snapshot.json")[0]
    context = build_memo_context(
        contract, read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")
    )
    payload = _valid_response_payload(context.decision, context.allowed_evidence_ids[0])

    memo = parse_and_validate_memo_response(json.dumps(payload), context)

    assert memo.memo_contract_version == MEMO_CONTRACT_VERSION
    assert memo.prompt_version == PROMPT_VERSION
    assert memo.source_decision_snapshot_hash == PHASE5_HASH
    assert memo.underlying_stance == contract.underlying_stance
    assert memo.final_portfolio_action == contract.final_portfolio_action
    schema = memo_response_json_schema(context.decision)
    assert schema["additionalProperties"] is False
    properties = schema["properties"]
    assert properties["memo_contract_version"]["enum"] == [MEMO_CONTRACT_VERSION]
    assert properties["company_id"]["enum"] == [context.decision.company_id]
    assert properties["source_decision_snapshot_hash"]["enum"] == [
        context.decision.decision_snapshot_sha256
    ]
    assert properties["underlying_stance"]["enum"] == [context.decision.underlying_stance]
    assert properties["final_portfolio_action"]["enum"] == [context.decision.final_portfolio_action]


def test_memo_validation_rejects_uncited_unknown_and_changed_action() -> None:
    contract = read_decision_memo_inputs(ROOT / "decision" / "decision_snapshot.json")[0]
    context = build_memo_context(
        contract, read_snapshot(ROOT / "evidence" / "normalized_snapshot.json")
    )
    valid = _valid_response_payload(context.decision, context.allowed_evidence_ids[0])

    uncited = json.loads(json.dumps(valid))
    uncited["executive_summary"]["evidence_ids"] = []
    with pytest.raises(MemoValidationError, match="requires a citation"):
        parse_and_validate_memo_response(json.dumps(uncited), context)

    unknown = json.loads(json.dumps(valid))
    unknown["supporting_evidence"][0]["evidence_ids"] = ["unknown"]
    with pytest.raises(MemoValidationError, match="outside the allow-list"):
        parse_and_validate_memo_response(json.dumps(unknown), context)

    changed = json.loads(json.dumps(valid))
    changed["final_portfolio_action"] = "buy"
    with pytest.raises(MemoValidationError, match="changed immutable field"):
        parse_and_validate_memo_response(json.dumps(changed), context)


def test_missing_azure_configuration_is_explicit_without_secret_values() -> None:
    with pytest.raises(MemoConfigurationError) as raised:
        AzureOpenAISettings.from_environment({})

    message = str(raised.value)
    assert "AZURE_OPENAI_API_KEY" in message
    assert "AZURE_OPENAI_DEPLOYMENT" in message
    assert "AZURE_OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT" in message


def test_azure_generation_controls_are_explicit_and_validated() -> None:
    settings = AzureOpenAISettings.from_environment(
        {
            "AZURE_OPENAI_API_KEY": "test-only-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-5.6-terra",
            "AZURE_OPENAI_REASONING_EFFORT": "medium",
            "AZURE_OPENAI_MAX_OUTPUT_TOKENS": "6000",
        }
    )

    assert settings.deployment == "gpt-5.6-terra"
    assert settings.reasoning_effort == "medium"
    assert settings.max_output_tokens == 6000
    assert settings.base_url == "https://example.openai.azure.com/openai/v1/"

    endpoint_with_openai = AzureOpenAISettings.from_environment(
        {
            "AZURE_OPENAI_API_KEY": "test-only-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/openai/",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-5.6-terra",
        }
    )
    assert endpoint_with_openai.base_url == "https://example.openai.azure.com/openai/v1/"

    complete_endpoint = AzureOpenAISettings.from_environment(
        {
            "AZURE_OPENAI_API_KEY": "test-only-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/openai/v1/",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-5.6-terra",
        }
    )
    assert complete_endpoint.base_url == "https://example.openai.azure.com/openai/v1/"

    explicit_base_url = AzureOpenAISettings.from_environment(
        {
            "AZURE_OPENAI_API_KEY": "test-only-key",
            "AZURE_OPENAI_BASE_URL": "https://example.openai.azure.com/openai/v1",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-5.6-terra",
        }
    )
    assert explicit_base_url.base_url == "https://example.openai.azure.com/openai/v1/"

    with pytest.raises(MemoConfigurationError, match="positive integer"):
        AzureOpenAISettings.from_environment(
            {
                "AZURE_OPENAI_API_KEY": "test-only-key",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-5.6-terra",
                "AZURE_OPENAI_MAX_OUTPUT_TOKENS": "0",
            }
        )

    with pytest.raises(MemoConfigurationError, match="must be the Azure resource root"):
        AzureOpenAISettings.from_environment(
            {
                "AZURE_OPENAI_API_KEY": "test-only-key",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/custom/path",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-5.6-terra",
            }
        )


def _valid_response_payload(decision: object, evidence_id: str) -> dict[str, object]:
    company = decision
    claim = {
        "text": "The cited evidence supports the frozen view.",
        "evidence_ids": [evidence_id],
        "category": "evidence",
    }
    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "decision_date": company.decision_date.isoformat(),
        "source_decision_snapshot_hash": company.decision_snapshot_sha256,
        "memo_contract_version": MEMO_CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "underlying_stance": company.underlying_stance,
        "final_portfolio_action": company.final_portfolio_action,
        "executive_summary": claim,
        **{name: [claim] for name in MEMO_SECTION_NAMES},
    }
