import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from enam_assessment.errors import (
    HoldingsOverlayError,
    QuestionContextError,
    QuestionValidationError,
    ScenarioLabError,
)
from enam_assessment.intelligence import (
    ANSWER_CONTRACT_VERSION,
    ANSWER_PROMPT_VERSION,
    DEFAULT_BRIEF_INPUT_TOKENS,
    DEFAULT_QUESTION_INPUT_TOKENS,
    ConversationHistoryItem,
    QuestionScope,
    SelectedArtifact,
    answer_cache_key,
    answer_response_json_schema,
    build_hard_gates_artifact,
    build_interactive_provider,
    build_question_context,
    citation_cards,
    estimated_request_tokens,
    normalize_question,
    parse_and_validate_answer,
)
from enam_assessment.portfolio_session import (
    calculate_holdings_overlay,
    recalculate_scenario,
    record_disposition,
)
from enam_assessment.portfolio_ui import DashboardData, load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]
PHASE5_HASH = "014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89"


@pytest.fixture
def dashboard() -> DashboardData:
    return load_dashboard_data(ROOT)


def test_question_contexts_are_compact_stable_and_cover_every_scope(
    dashboard: DashboardData,
) -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    cases = (
        (QuestionScope.COMPANY_BRIEF, ("amber",), DEFAULT_BRIEF_INPUT_TOKENS),
        (QuestionScope.COMPANY, ("amber",), DEFAULT_QUESTION_INPUT_TOKENS),
        (QuestionScope.PORTFOLIO, (), DEFAULT_QUESTION_INPUT_TOKENS),
        (QuestionScope.COMPARISON, ("welspun", "zee"), DEFAULT_QUESTION_INPUT_TOKENS),
        (QuestionScope.BEHAVIOUR, (), DEFAULT_QUESTION_INPUT_TOKENS),
    )

    for scope, company_ids, budget in cases:
        first = build_question_context(
            dashboard,
            scope=scope,
            question="  Explain   the current view and its risks. ",
            company_ids=company_ids,
            input_token_budget=budget,
        )
        second = build_question_context(
            dashboard,
            scope=scope,
            question="Explain the current view and its risks.",
            company_ids=company_ids,
            input_token_budget=budget,
        )

        assert first.stable_payload() == second.stable_payload()
        assert first.included_evidence_ids == tuple(sorted(set(first.included_evidence_ids)))
        assert set(first.included_evidence_ids).isdisjoint(first.excluded_evidence_ids)
        assert (
            estimated_request_tokens(
                first,
                system_prompt=prompt,
                response_schema=answer_response_json_schema(first),
            )
            <= budget
        )


def test_interactive_prompt_preserves_product_role_and_authority_boundary() -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    lowered = prompt.lower()

    assert "portfolio-intelligence layer" in lowered
    assert "portfolio owner" in lowered
    assert "lead with a direct answer" in lowered
    assert "never exceed 400 words" in lowered
    assert "deterministic snapshot is authoritative" in lowered
    assert "every material claim" in lowered
    for forbidden in ("evaluator", "job assessment", "submission", "development phase"):
        assert forbidden not in lowered


def test_comparison_context_prunes_for_the_complete_request_budget(
    dashboard: DashboardData,
) -> None:
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPARISON,
        question="Explain the current view and its risks.",
        company_ids=("welspun", "zee"),
    )
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")

    assert context.input_token_budget == 4000
    assert (
        estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        <= context.input_token_budget
    )
    assert set(context.included_evidence_ids) >= {
        "decision:welspun",
        "decision:zee",
        "session:active-portfolio",
    }
    assert context.excluded_evidence_ids
    assert set(context.included_evidence_ids).isdisjoint(context.excluded_evidence_ids)


def test_explicit_prompt_is_budgeted_without_loading_from_the_working_directory(
    dashboard: DashboardData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    prompt += "\n" + "Additional instruction. " * 120
    monkeypatch.chdir(tmp_path)

    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPARISON,
        question="Explain the current view and its risks.",
        company_ids=("welspun", "zee"),
        system_prompt=prompt,
    )

    assert (
        estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        <= 4000
    )
    assert set(context.included_evidence_ids) >= {
        "decision:welspun",
        "decision:zee",
        "session:active-portfolio",
    }


def test_missing_prompt_and_oversized_required_context_fail_explicitly(
    dashboard: DashboardData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(QuestionContextError, match="supply system_prompt explicitly"):
        build_question_context(
            dashboard,
            scope=QuestionScope.COMPANY,
            question="Which DBL hard gate failed?",
            company_ids=("dbl",),
        )
    with pytest.raises(QuestionContextError, match="Request too broad for the 4000-token"):
        build_question_context(
            dashboard,
            scope=QuestionScope.COMPANY,
            question="Which DBL hard gate failed?",
            company_ids=("dbl",),
            selected_artifacts=(build_hard_gates_artifact(dashboard, "dbl"),),
            system_prompt=prompt * 8,
        )


def test_attached_portfolio_summary_fits_budget_with_citable_decisions(
    dashboard: DashboardData,
) -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    overlay = calculate_holdings_overlay(dashboard.decisions)
    artifact = SelectedArtifact(
        artifact_id="portfolio-summary-concentration",
        label="Portfolio summary and concentration",
        origin_page="Portfolio Cockpit",
        company_ids=(),
        payload={
            "represented_total_value": str(overlay.total_value),
            "available_cash": str(overlay.available_cash),
            "cash_source": overlay.cash_source,
            "company_weights": {
                item.company_id: str(overlay.company_weights[item.company_id])
                for item in dashboard.decisions
            },
            "cash_weight": str(overlay.cash_weight),
            "top_two_weight": str(overlay.concentration.top_two_weight),
            "top_three_weight": str(overlay.concentration.top_three_weight),
            "hhi": str(overlay.concentration.hhi),
            "effective_positions": str(overlay.concentration.effective_positions),
            "review_reasons": list(overlay.concentration.review_reasons),
        },
    )

    context = build_question_context(
        dashboard,
        scope=QuestionScope.PORTFOLIO,
        question=(
            "Which positions drive concentration in the active portfolio, and why do their "
            "frozen actions, target weights, and review states require attention?"
        ),
        active_overlay=overlay,
        selected_artifacts=(artifact,),
    )

    assert set(context.included_evidence_ids) >= {
        "artifact:portfolio-summary-concentration",
        "decision:portfolio-summary",
        "session:active-portfolio",
    }
    assert all(
        set(item) == {"company_id", "company_name", "underlying_stance", "final_action"}
        for item in context.decision_facts
    )
    assert (
        estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        <= DEFAULT_QUESTION_INPUT_TOKENS
    )


def test_attached_behaviour_findings_replace_duplicate_derived_summary(
    dashboard: DashboardData,
) -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    artifact = SelectedArtifact(
        artifact_id="historical-behaviour-findings",
        label="Historical behaviour patterns and limitations",
        origin_page="Investor Behaviour",
        company_ids=(),
        payload={
            "coverage": dashboard.historical["coverage"],
            "findings": [
                {
                    "title": item["title"],
                    "observed": item["observed"],
                    "counter_evidence": item["counter_evidence"],
                    "confidence": item["confidence"],
                    "limitation": item["limitation"],
                }
                for item in dashboard.historical["findings"]
            ],
            "interpretation_boundary": (
                "Observed FIFO-lot patterns do not prove intent, skill, alpha, or psychology."
            ),
        },
    )

    context = build_question_context(
        dashboard,
        scope=QuestionScope.BEHAVIOUR,
        question=(
            "How should the investor's historical sizing and selling behaviour influence a "
            "current portfolio decision?"
        ),
        selected_artifacts=(artifact,),
    )

    assert "artifact:historical-behaviour-findings" in context.included_evidence_ids
    assert "analysis:historical-behaviour" not in context.included_evidence_ids
    assert (
        estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        <= DEFAULT_QUESTION_INPUT_TOKENS
    )


def test_scope_and_budget_errors_are_explicit(dashboard: DashboardData) -> None:
    with pytest.raises(QuestionContextError, match="requires 2 valid unique"):
        build_question_context(
            dashboard,
            scope=QuestionScope.COMPARISON,
            question="Compare them",
            company_ids=("amber",),
        )
    with pytest.raises(QuestionContextError, match="at most 500 characters"):
        normalize_question("x" * 501)
    with pytest.raises(QuestionContextError, match="overhead reserve"):
        build_question_context(
            dashboard,
            scope=QuestionScope.COMPANY,
            question="Why?",
            company_ids=("amber",),
            input_token_budget=100,
        )


def test_interactive_provider_uses_fixed_deployment_and_bounded_defaults() -> None:
    provider = build_interactive_provider(
        {
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/openai",
            "AZURE_OPENAI_API_KEY": "test-only-key",
        }
    )

    assert provider.deployment_id == "gpt-5.6-terra"
    assert provider.reasoning_effort == "low"
    assert provider.max_output_tokens == 2200


def test_context_rejects_future_and_wrong_company_evidence(dashboard: DashboardData) -> None:
    amber_evidence = dashboard.evidence_by_company["amber"]
    selected = next(item for item in amber_evidence if item.evidence_id.startswith("fundamental-"))
    future = replace(
        selected, available_date=dashboard.decision("amber").decision_date + timedelta(days=1)
    )
    future_items = tuple(
        future if item.evidence_id == selected.evidence_id else item for item in amber_evidence
    )
    future_data = replace(
        dashboard,
        evidence_by_company={**dashboard.evidence_by_company, "amber": future_items},
    )
    with pytest.raises(QuestionContextError, match="after the decision date"):
        build_question_context(
            future_data,
            scope=QuestionScope.COMPANY_BRIEF,
            question="Explain the company",
            company_ids=("amber",),
            input_token_budget=DEFAULT_BRIEF_INPUT_TOKENS,
        )

    wrong = replace(selected, company_or_instrument_id="zee")
    wrong_items = tuple(
        wrong if item.evidence_id == selected.evidence_id else item for item in amber_evidence
    )
    wrong_data = replace(
        dashboard,
        evidence_by_company={**dashboard.evidence_by_company, "amber": wrong_items},
    )
    with pytest.raises(QuestionContextError, match="wrong company"):
        build_question_context(
            wrong_data,
            scope=QuestionScope.COMPANY_BRIEF,
            question="Explain the company",
            company_ids=("amber",),
            input_token_budget=DEFAULT_BRIEF_INPUT_TOKENS,
        )


def test_answer_schema_and_validation_pin_identity_and_citations(
    dashboard: DashboardData,
) -> None:
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Why is the action review required?",
        company_ids=("amber",),
    )
    schema = answer_response_json_schema(context)
    properties = schema["properties"]
    assert properties["scope"]["enum"] == ["company"]
    assert properties["company_ids"]["items"]["enum"] == ["amber"]
    assert properties["company_ids"]["minItems"] == 1
    assert properties["company_ids"]["maxItems"] == 1
    _assert_strict_schema(schema)
    payload = _answer_payload(context)

    answer = parse_and_validate_answer(json.dumps(payload), context)

    assert answer.answer_contract_version == ANSWER_CONTRACT_VERSION
    assert answer.prompt_version == ANSWER_PROMPT_VERSION
    assert answer.decision_snapshot_sha256 == PHASE5_HASH

    payload["supporting_points"][0]["evidence_ids"] = ["unknown"]
    with pytest.raises(QuestionValidationError, match="outside the allow-list"):
        parse_and_validate_answer(json.dumps(payload), context)

    payload = _answer_payload(context)
    payload["direct_answer"]["evidence_ids"] = []
    with pytest.raises(QuestionValidationError, match="requires one or more evidence IDs"):
        parse_and_validate_answer(json.dumps(payload), context)


def test_every_question_scope_emits_a_strict_schema_without_empty_enums(
    dashboard: DashboardData,
) -> None:
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    amber = dashboard.decision("amber")
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
        (QuestionScope.COMPANY, ("amber",), None),
        (QuestionScope.PORTFOLIO, (), None),
        (QuestionScope.COMPARISON, ("welspun", "zee"), None),
        (QuestionScope.BEHAVIOUR, (), None),
        (QuestionScope.SCENARIO_DELTA, ("amber",), delta),
    )

    for scope, company_ids, scenario_delta in cases:
        context = build_question_context(
            dashboard,
            scope=scope,
            question=f"Explain the {scope.value} view.",
            company_ids=company_ids,
            scenario_delta=scenario_delta,
        )
        schema = answer_response_json_schema(context)
        _assert_strict_schema(schema)
        assert (
            estimated_request_tokens(context, system_prompt=prompt, response_schema=schema)
            <= context.input_token_budget
        )
        properties = schema["properties"]
        assert isinstance(properties, dict)
        company_schema = properties["company_ids"]
        assert isinstance(company_schema, dict)
        items = company_schema["items"]
        assert isinstance(items, dict)
        if scope in {QuestionScope.PORTFOLIO, QuestionScope.BEHAVIOUR}:
            assert context.company_ids == ()
            assert company_schema["minItems"] == 0
            assert company_schema["maxItems"] == 0
            assert "enum" not in items
        else:
            assert items["enum"] == list(company_ids)
            assert company_schema["minItems"] == len(company_ids)
            assert company_schema["maxItems"] == len(company_ids)


def _assert_strict_schema(node: object) -> None:
    assert isinstance(node, dict)
    if "enum" in node:
        assert isinstance(node["enum"], list)
        assert node["enum"]
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False
        properties = node.get("properties")
        assert isinstance(properties, dict)
        assert set(node.get("required", [])) == set(properties)
        for child in properties.values():
            _assert_strict_schema(child)
    if node.get("type") == "array":
        assert "items" in node
        _assert_strict_schema(node["items"])


def test_citation_cards_resolve_source_and_deterministic_provenance(
    dashboard: DashboardData,
) -> None:
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY_BRIEF,
        question="Summarize Amber",
        company_ids=("amber",),
        input_token_budget=DEFAULT_BRIEF_INPUT_TOKENS,
    )
    source_id = next(
        item for item in context.included_evidence_ids if item.startswith("fundamental")
    )
    stable_context = context.stable_payload()
    cards = citation_cards(dashboard, context, ("decision:amber", source_id))

    assert cards[0].source_type == "deterministic_decision"
    assert cards[0].display_label == "Frozen Amber decision"
    assert cards[0].provenance_class == "Frozen decision record"
    assert cards[1].source_title
    assert cards[1].display_label
    assert cards[1].provenance_class == "Supplied source evidence"
    assert context.stable_payload() == stable_context
    with pytest.raises(QuestionValidationError, match="outside the request allow-list"):
        citation_cards(dashboard, context, ("unknown",))


def test_citation_cards_give_derived_records_distinct_readable_labels(
    dashboard: DashboardData,
) -> None:
    artifact = build_hard_gates_artifact(dashboard, company_id="dbl")
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Which DBL gate matters most?",
        company_ids=("dbl",),
        selected_artifacts=(artifact,),
    )
    required = (
        "decision:dbl",
        "session:active-portfolio",
        "artifact:dbl-hard-gates",
        "fundamental-dbl-consolidated-net-debt-fy26",
    )

    cards = citation_cards(dashboard, context, required)
    by_id = {card.evidence_id: card for card in cards}

    assert by_id["decision:dbl"].display_label == "Frozen DBL decision"
    assert by_id["decision:dbl"].provenance_class == "Frozen decision record"
    assert (
        by_id["session:active-portfolio"].display_label == "Current session portfolio calculation"
    )
    assert by_id["session:active-portfolio"].provenance_class == "Active-session calculation"
    assert by_id["artifact:dbl-hard-gates"].display_label == "Attached DBL hard-gate analysis"
    assert by_id["artifact:dbl-hard-gates"].provenance_class == ("Attached application artifact")
    assert "₹7,244 crore ÷ ₹1,766 crore is approximately 4.10×" in (
        by_id["artifact:dbl-hard-gates"].summary
    )
    assert "SELL stance, REVIEW_REQUIRED action, 0.0% target" in (
        by_id["artifact:dbl-hard-gates"].summary
    )
    assert (
        by_id["fundamental-dbl-consolidated-net-debt-fy26"].display_label
        == "FY26 consolidated net debt — ₹7,244 crore"
    )
    assert by_id["fundamental-dbl-consolidated-net-debt-fy26"].provenance_class == (
        "Supplied source evidence"
    )


def test_holdings_overlay_is_session_only_and_resettable(dashboard: DashboardData) -> None:
    frozen = tuple(item.stable_payload() for item in dashboard.decisions)
    baseline = calculate_holdings_overlay(dashboard.decisions)
    changed = calculate_holdings_overlay(
        dashboard.decisions,
        share_overrides={"amber": Decimal("0")},
        available_cash=Decimal("1000000"),
    )
    reset = calculate_holdings_overlay(dashboard.decisions)

    assert baseline.uses_verified_values is False
    assert baseline.cash_source == "assumed_zero"
    assert {item.source for item in baseline.holdings} == {"supplied_workbook"}
    assert changed.uses_verified_values is True
    assert changed.cash_source == "user_entered"
    assert next(item for item in changed.holdings if item.company_id == "amber").source == (
        "user_entered"
    )
    assert changed.company_weights["amber"] == 0
    assert changed.cash_weight > 0
    assert reset == baseline
    assert tuple(item.stable_payload() for item in dashboard.decisions) == frozen
    with pytest.raises(HoldingsOverlayError, match="cannot be negative"):
        calculate_holdings_overlay(dashboard.decisions, available_cash=Decimal("-1"))


def test_context_uses_active_overlay_and_invalidates_cache_after_session_change(
    dashboard: DashboardData,
) -> None:
    baseline_overlay = calculate_holdings_overlay(dashboard.decisions)
    changed_overlay = calculate_holdings_overlay(
        dashboard.decisions,
        share_overrides={"amber": Decimal("0")},
        available_cash=Decimal("1000000"),
    )
    baseline = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Why does Amber need review?",
        company_ids=("amber",),
        active_overlay=baseline_overlay,
    )
    changed = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Why does Amber need review?",
        company_ids=("amber",),
        active_overlay=changed_overlay,
    )

    assert baseline.context_hash != changed.context_hash
    assert answer_cache_key(baseline) != answer_cache_key(changed)
    assert (
        baseline.decision_facts[0]["active_session_weight"]
        != (changed.decision_facts[0]["active_session_weight"])
    )
    assert changed.active_portfolio["cash_source"] == "user_entered"
    active_record = next(
        item for item in changed.evidence if item.evidence_id == "session:active-portfolio"
    )
    assert active_record.category == "user_input_and_deterministic_calculation"
    assert "shares 0" in active_record.content
    assert "session-entered share overrides are active only for ['amber']" in active_record.content

    baseline_record = next(
        item for item in baseline.evidence if item.evidence_id == "session:active-portfolio"
    )
    assert "no session-entered share overrides are active" in baseline_record.content


def test_compact_evidence_and_follow_up_context_are_attributed_and_stable(
    dashboard: DashboardData,
) -> None:
    artifact = SelectedArtifact(
        artifact_id="amber-evidence-balance",
        label="Amber evidence balance",
        origin_page="Company Intelligence",
        company_ids=("amber",),
        payload={"focus": "cash flow"},
        evidence_ids=("fundamental-1eb858fe9f6565c1",),
    )
    history = ConversationHistoryItem(
        question="What supports Amber?",
        direct_answer="The prior answer discussed the cited revenue evidence.",
        scope=QuestionScope.COMPANY,
        company_ids=("amber",),
        evidence_ids=("fundamental-1eb858fe9f6565c1",),
        context_hash="prior-context",
    )
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Why?",
        company_ids=("amber",),
        selected_artifacts=(artifact,),
        conversation_history=(history,),
    )
    evidence = next(
        item for item in context.evidence if item.evidence_id == "fundamental-1eb858fe9f6565c1"
    )

    assert evidence.company_or_instrument_id == "amber"
    assert evidence.evidence_kind == "fundamental_fact"
    assert evidence.reporting_period_or_date == "FY2026"
    assert evidence.unit == "INR crore"
    assert context.selected_artifacts == (artifact,)
    assert context.conversation_history == (history,)
    assert {item["company_id"] for item in context.active_portfolio["holdings"]} == {
        "amber",
        "dbl",
        "welspun",
        "zee",
    }
    assert "artifact:amber-evidence-balance" in context.included_evidence_ids


def test_conversation_history_model_payload_is_bounded_and_explicit() -> None:
    history = ConversationHistoryItem(
        question="Why?",
        direct_answer="word " * 200,
        scope=QuestionScope.PORTFOLIO,
        company_ids=(),
        evidence_ids=("decision:portfolio-summary",),
        context_hash="prior-context",
    )

    payload = history.model_payload()

    assert payload["answer_excerpt_truncated"] is True
    assert len(str(payload["direct_answer_excerpt"])) <= 420
    assert "context_hash" not in payload
    assert history.stable_payload()["context_hash"] == "prior-context"


def test_hosted_dbl_question_with_both_attachments_fits_default_4000_token_budget(
    dashboard: DashboardData,
) -> None:
    decision = dashboard.decision("dbl")
    frozen = decision.stable_payload()
    overlay = calculate_holdings_overlay(dashboard.decisions)
    summary = SelectedArtifact(
        artifact_id="dbl-decision-summary",
        label=f"{decision.company_name} decision summary",
        origin_page="Company Intelligence",
        company_ids=("dbl",),
        payload={
            "stance": decision.underlying_stance,
            "final_action": decision.final_portfolio_action,
            "human_review_required": decision.human_review_required,
            "human_review_reasons": list(decision.human_review_reasons),
            "active_weight": str(overlay.company_weights["dbl"]),
            "frozen_target_weight": decision.target_weight,
            "weighted_principle_score": decision.weighted_principle_score,
        },
    )
    hard_gates = build_hard_gates_artifact(dashboard, "dbl")
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question=(
            "Why is Dilip Buildcon marked SELL / REVIEW_REQUIRED, and how does its 4.10× "
            "net debt-to-EBITDA calculation compare with the 4.0× hard-gate limit?"
        ),
        company_ids=("dbl",),
        active_overlay=overlay,
        selected_artifacts=(summary, hard_gates),
    )
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")

    assert context.input_token_budget == DEFAULT_QUESTION_INPUT_TOKENS == 4000
    assert (
        estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        <= 4000
    )
    assert context.selected_artifacts == (summary, hard_gates)
    assert set(context.included_evidence_ids) >= {
        "artifact:dbl-decision-summary",
        "artifact:dbl-hard-gates",
        "decision:dbl",
        "session:active-portfolio",
        "fundamental-dbl-consolidated-net-debt-fy26",
        "fundamental-c02d7f1564a6c6e4",
    }
    evidence = {item.evidence_id: item for item in context.evidence}
    assert "consolidated_net_debt: 7244 INR crore" in (
        evidence["fundamental-dbl-consolidated-net-debt-fy26"].content
    )
    assert "consolidated_ebitda: 1766 INR crore" in (
        evidence["fundamental-c02d7f1564a6c6e4"].content
    )
    gate_content = json.loads(evidence["artifact:dbl-hard-gates"].content)
    assert gate_content["frozen_decision"] == {
        "underlying_stance": "sell",
        "final_action": "review_required",
        "target_weight": "0",
        "weighted_principle_score": "2.675",
        "human_review_required": True,
        "human_review_reasons": ["provisional_holdings_material_to_rebalance"],
    }
    failed_gate = next(
        gate
        for gate in gate_content["hard_gates"]
        if gate["code"] == "balance_sheet_liquidity_and_funding"
    )
    assert failed_gate["status"] == "fail"
    assert failed_gate["consequence"] == "sell"
    assert failed_gate["calculation"]["result"] == "approximately 4.10x"
    assert failed_gate["calculation"]["sell_threshold"] == "4.0x"
    assert failed_gate["calculation"]["comparison"] == "above_sell_threshold"
    assert decision.stable_payload() == frozen
    assert context.decision_snapshot_sha256 == PHASE5_HASH


def test_active_dbl_gate_follow_up_fits_the_interactive_budget(
    dashboard: DashboardData,
) -> None:
    artifact = build_hard_gates_artifact(dashboard, "dbl")
    overlay = calculate_holdings_overlay(
        dashboard.decisions,
        share_overrides={"amber": Decimal("40000")},
        available_cash=Decimal("5000000"),
    )
    history = ConversationHistoryItem(
        question=(
            "How should the investor's historical sizing and selling behaviour influence "
            "a current portfolio decision?"
        ),
        direct_answer="Prior grounded behaviour answer. " * 40,
        scope=QuestionScope.BEHAVIOUR,
        company_ids=(),
        evidence_ids=(),
        context_hash="prior-behaviour-context",
    )
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question=(
            "Using the attached DBL hard-gate section and the current active portfolio, which "
            "DBL hard gates and missing evidence matter most, and what remains unchanged in "
            "the frozen decision?"
        ),
        company_ids=("dbl",),
        active_overlay=overlay,
        selected_artifacts=(artifact,),
        conversation_history=(history,),
    )
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")

    assert (
        estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        <= DEFAULT_QUESTION_INPUT_TOKENS
    )
    assert "artifact:dbl-hard-gates" in context.included_evidence_ids
    assert "session:active-portfolio" in context.included_evidence_ids
    assert "fundamental-dbl-consolidated-net-debt-fy26" in context.included_evidence_ids
    assert "fundamental-c02d7f1564a6c6e4" in context.included_evidence_ids
    serialized = json.dumps(context.model_payload(), ensure_ascii=False, sort_keys=True)
    assert "₹7,244 crore" in serialized
    assert "₹1,766 crore" in serialized
    assert "approximately 4.10×" in serialized
    assert "configured 4.0× sell threshold" in serialized
    artifact_record = next(
        item for item in context.evidence if item.evidence_id == "artifact:dbl-hard-gates"
    )
    artifact_content = json.loads(artifact_record.content)
    assert artifact_content["frozen_decision"] == {
        "underlying_stance": "sell",
        "final_action": "review_required",
        "target_weight": "0",
        "weighted_principle_score": "2.675",
        "human_review_required": True,
        "human_review_reasons": ["provisional_holdings_material_to_rebalance"],
    }
    assert context.conversation_history in ((), (history,))


def test_scenario_lab_recalculates_with_existing_function_and_preserves_baseline(
    dashboard: DashboardData,
) -> None:
    decision = dashboard.decision("amber")
    frozen = decision.stable_payload()
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

    assert delta.recalculated.target_price > delta.baseline.target_price
    assert delta.target_price_delta == delta.recalculated.target_price - delta.baseline.target_price
    assert decision.stable_payload() == frozen
    with pytest.raises(ScenarioLabError, match="expected one"):
        recalculate_scenario(
            decision,
            scenario_name="unknown",
            annual_revenue_growth=Decimal("0.1"),
            terminal_margin=Decimal("0.1"),
            multiple_change_factor=Decimal("1"),
            equity_bridge_factor=Decimal("1"),
        )


def test_human_disposition_and_cache_key_do_not_change_engine_decision(
    dashboard: DashboardData,
) -> None:
    decision = dashboard.decision("amber")
    context = build_question_context(
        dashboard,
        scope=QuestionScope.COMPANY,
        question="Why review Amber?",
        company_ids=("amber",),
    )
    disposition = record_disposition(
        decision,
        disposition="deferred",
        note="Await debt evidence.",
        recorded_at=decision.decision_date,
    )

    assert disposition.engine_action == decision.final_portfolio_action
    assert disposition.decision_snapshot_sha256 == PHASE5_HASH
    assert answer_cache_key(context) == answer_cache_key(context)


def _answer_payload(context: object) -> dict[str, object]:
    from enam_assessment.intelligence import QuestionContext

    assert isinstance(context, QuestionContext)
    claim = {
        "text": "The frozen decision requires review because the cited evidence is incomplete.",
        "evidence_ids": [context.included_evidence_ids[0]],
        "category": "deterministic_explanation",
    }
    return {
        "scope": context.scope.value,
        "company_ids": list(context.company_ids),
        "decision_snapshot_sha256": context.decision_snapshot_sha256,
        "context_hash": context.context_hash,
        "answer_contract_version": ANSWER_CONTRACT_VERSION,
        "prompt_version": ANSWER_PROMPT_VERSION,
        "direct_answer": claim,
        "supporting_points": [claim],
        "counterpoints": [],
        "relevant_unknowns": [],
        "change_conditions": [],
    }
