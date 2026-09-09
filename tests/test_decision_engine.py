from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from enam_assessment.decision import (
    ConcentrationThresholds,
    DataQuality,
    GateConsequence,
    GateStatus,
    HardGateResult,
    InvestmentStance,
    PrincipleScore,
    ScenarioInput,
)
from enam_assessment.decision_engine import (
    CompanyDecisionSpec,
    DecisionEngineConfig,
    build_decisions,
)
from enam_assessment.errors import EvidenceReferenceError
from enam_assessment.evidence import (
    CorporateActionStatus,
    DataState,
    EvidenceSnapshot,
    EvidenceType,
    ExtractionConfidence,
    FundamentalFact,
    PriceObservation,
)

COMPANIES = ("amber", "dbl", "zee", "welspun")


def evidence_snapshot(*, reverse: bool = False) -> EvidenceSnapshot:
    facts = tuple(
        FundamentalFact(
            evidence_id=f"fact-{company}",
            company_id=company,
            metric_name="revenue",
            value=Decimal("1000"),
            unit="INR crore",
            reporting_period="FY2026",
            period_end=date(2026, 3, 31),
            publication_date=date(2026, 5, 1),
            source_id=f"source-{company}",
            source_locator="page 1",
            evidence_type=EvidenceType.REPORTED_FACT,
            retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
            extraction_confidence=ExtractionConfidence.HIGH,
        )
        for company in COMPANIES
    ) + (
        FundamentalFact(
            evidence_id="fundamental-dbl-consolidated-net-debt-fy26",
            company_id="dbl",
            metric_name="consolidated_net_debt",
            value=Decimal("500"),
            unit="INR crore",
            reporting_period="FY2026",
            period_end=date(2026, 3, 31),
            publication_date=date(2026, 5, 1),
            source_id="source-dbl",
            source_locator="page 2",
            evidence_type=EvidenceType.REPORTED_FACT,
            retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
            extraction_confidence=ExtractionConfidence.HIGH,
        ),
        FundamentalFact(
            evidence_id="fundamental-c02d7f1564a6c6e4",
            company_id="dbl",
            metric_name="consolidated_ebitda",
            value=Decimal("100"),
            unit="INR crore",
            reporting_period="FY2026",
            period_end=date(2026, 3, 31),
            publication_date=date(2026, 5, 1),
            source_id="source-dbl",
            source_locator="page 2",
            evidence_type=EvidenceType.REPORTED_FACT,
            retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
            extraction_confidence=ExtractionConfidence.HIGH,
        ),
    )
    prices = tuple(
        PriceObservation(
            evidence_id=f"price-{company}",
            instrument_id=company,
            trading_date=date(2026, 9, 8),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            adjusted_close=Decimal("100"),
            volume=Decimal("1000"),
            corporate_action_status=CorporateActionStatus.ADJUSTED_BY_SOURCE,
            source_id=f"prices-{company}",
            retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
            validation_status=DataState.AVAILABLE,
        )
        for company in COMPANIES
    )
    if reverse:
        facts, prices = tuple(reversed(facts)), tuple(reversed(prices))
    return EvidenceSnapshot.create(
        analysis_as_of=date(2026, 9, 8), fundamentals=facts, prices=prices
    )


def spec(company: str, *, sell_gate: bool = False) -> CompanyDecisionSpec:
    evidence_ids = (
        (
            "fundamental-dbl-consolidated-net-debt-fy26",
            "fundamental-c02d7f1564a6c6e4",
        )
        if company == "dbl"
        else (f"fact-{company}",)
    )
    gates = (
        HardGateResult(
            code="balance_sheet_liquidity_and_funding",
            status=GateStatus.FAIL if sell_gate else GateStatus.PASS,
            evidence_ids=evidence_ids,
            explanation="Synthetic balance gate.",
            consequence=GateConsequence.SELL if sell_gate else GateConsequence.NONE,
        ),
    )
    dimensions = tuple(
        PrincipleScore(
            name,
            Decimal("4"),
            weight,
            evidence_ids,
            (),
            (),
            "Synthetic rule.",
            DataQuality.HIGH,
        )
        for name, weight in (
            ("business_quality", Decimal("0.20")),
            ("management", Decimal("0.15")),
            ("runway", Decimal("0.15")),
            ("growth", Decimal("0.15")),
            ("balance_sheet", Decimal("0.20")),
            ("valuation", Decimal("0.15")),
        )
    )
    scenarios = tuple(
        ScenarioInput(
            name=name,
            starting_price=Decimal("100"),
            starting_revenue=Decimal("1000"),
            starting_operating_metric=Decimal("100"),
            annual_revenue_growth=growth,
            terminal_margin=margin,
            multiple_change_factor=multiple,
            equity_bridge_factor=Decimal("1"),
            horizon_years=3,
            evidence_ids=(f"fact-{company}", f"price-{company}"),
        )
        for name, growth, margin, multiple in (
            ("bear", Decimal("-0.05"), Decimal("0.08"), Decimal("0.8")),
            ("base", Decimal("0.20"), Decimal("0.12"), Decimal("1")),
            ("bull", Decimal("0.30"), Decimal("0.14"), Decimal("1.1")),
        )
    )
    return CompanyDecisionSpec(
        company_id=company,
        company_name=company.title(),
        working_shares=Decimal("10"),
        working_cost_basis=Decimal("800"),
        gates=gates,
        principle_scores=dimensions,
        scenarios=scenarios,
        confidence_factor=Decimal("0.8"),
        change_triggers=("New results",),
        common_drivers=("synthetic",),
    )


def engine_config() -> DecisionEngineConfig:
    return DecisionEngineConfig(
        decision_date=date(2026, 9, 8),
        engine_version="1.0.0",
        configuration_version="test",
        quality_threshold=Decimal("3"),
        buy_hurdle=Decimal("0.25"),
        rebalance_band=Decimal("0.05"),
        position_bear_loss_budget=Decimal("0.04"),
        minimum_sizing_downside=Decimal("0.10"),
        dbl_net_debt_to_ebitda_sell_threshold=Decimal("4.0"),
        concentration_thresholds=ConcentrationThresholds(
            single_name=Decimal("0.45"),
            top_two=Decimal("0.75"),
            hhi=Decimal("0.35"),
        ),
        primary_benchmark_id="bse-500-tri",
        primary_benchmark_status="unavailable_authentication_required",
        secondary_benchmark_id="nifty-500-tri",
        secondary_benchmark_status="available_context_only",
    )


def test_pipeline_is_deterministic_traceable_and_gate_safe() -> None:
    specs = tuple(spec(company, sell_gate=company == "dbl") for company in COMPANIES)
    first = build_decisions(evidence_snapshot(), specs, engine_config(), historical_context={})
    second = build_decisions(
        evidence_snapshot(reverse=True),
        tuple(reversed(specs)),
        engine_config(),
        historical_context={},
    )

    assert first.snapshot_sha256 == second.snapshot_sha256
    assert first.primary_benchmark_status == "unavailable_authentication_required"
    assert first.secondary_benchmark_status == "available_context_only"
    assert first.company("dbl").underlying_stance is InvestmentStance.SELL
    assert first.company("dbl").weighted_principle_score == Decimal("4.00")
    valid_ids = {
        item.evidence_id for item in evidence_snapshot().fundamentals + evidence_snapshot().prices
    }
    assert set(first.company("amber").evidence_ids) <= valid_ids


def test_missing_or_post_decision_evidence_cannot_enter_decision() -> None:
    bad_score = replace(spec("amber").principle_scores[0], evidence_ids=("future-or-missing",))
    bad = replace(
        spec("amber"),
        principle_scores=(bad_score,) + spec("amber").principle_scores[1:],
    )
    specs = (bad,) + tuple(spec(company) for company in COMPANIES[1:])
    with pytest.raises(EvidenceReferenceError, match="future-or-missing"):
        build_decisions(evidence_snapshot(), specs, engine_config(), historical_context={})


def test_concentration_approval_and_provisional_holdings_cannot_silently_buy() -> None:
    specs = tuple(
        replace(
            spec(company), working_shares=Decimal("1000") if company == "amber" else Decimal("1")
        )
        for company in COMPANIES
    )
    result = build_decisions(evidence_snapshot(), specs, engine_config(), historical_context={})

    assert result.current_concentration.requires_review is True
    assert result.company("amber").final_action is InvestmentStance.REVIEW_REQUIRED
    assert result.company("amber").provisional_holdings is True
    assert result.cash_target_weight >= 0


def test_missing_dimension_forces_review_and_conflicts_remain_visible() -> None:
    original = spec("amber")
    unavailable = replace(
        original.principle_scores[0],
        score=None,
        counter_evidence_ids=("fact-amber",),
        missing_information=("critical metric",),
        data_quality=DataQuality.UNAVAILABLE,
    )
    amber = replace(
        original,
        principle_scores=(unavailable,) + original.principle_scores[1:],
    )
    specs = (amber,) + tuple(spec(company) for company in COMPANIES[1:])
    result = build_decisions(evidence_snapshot(), specs, engine_config(), historical_context={})

    decision = result.company("amber")
    assert decision.weighted_principle_score is None
    assert decision.underlying_stance is InvestmentStance.REVIEW_REQUIRED
    business_quality = next(
        item for item in decision.principle_scores if item.dimension == "business_quality"
    )
    assert business_quality.counter_evidence_ids == ("fact-amber",)
    assert "critical metric" in decision.missing_data_flags


def test_secondary_benchmark_context_never_changes_decision_outputs() -> None:
    specs = tuple(spec(company) for company in COMPANIES)
    baseline = build_decisions(evidence_snapshot(), specs, engine_config(), historical_context={})
    contextual = build_decisions(
        evidence_snapshot(),
        specs,
        engine_config(),
        historical_context={"amber": {"relative_return": "999"}},
    )

    assert (
        baseline.company("amber").underlying_stance == contextual.company("amber").underlying_stance
    )
    assert baseline.company("amber").target_weight == contextual.company("amber").target_weight
