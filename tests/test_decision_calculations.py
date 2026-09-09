from dataclasses import replace
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
    calculate_cash_weight,
    calculate_concentration,
    calculate_portfolio_weights,
    calculate_scenario,
    map_final_action,
    map_investment_stance,
    portfolio_at_risk,
    resolve_gate_stance,
    weighted_principle_score,
)
from enam_assessment.errors import InvalidDecisionInputError


def gate(status: GateStatus, consequence: GateConsequence) -> HardGateResult:
    return HardGateResult(
        code="test_gate",
        status=status,
        evidence_ids=("evidence-1",),
        explanation="Synthetic gate.",
        consequence=consequence,
    )


def test_hard_gate_truth_table_prioritizes_sell_over_review() -> None:
    assert resolve_gate_stance((gate(GateStatus.PASS, GateConsequence.NONE),)) is None
    assert (
        resolve_gate_stance((gate(GateStatus.UNKNOWN, GateConsequence.REVIEW_REQUIRED),))
        is InvestmentStance.REVIEW_REQUIRED
    )
    assert (
        resolve_gate_stance((gate(GateStatus.FAIL, GateConsequence.REVIEW_REQUIRED),))
        is InvestmentStance.REVIEW_REQUIRED
    )
    assert (
        resolve_gate_stance(
            (
                gate(GateStatus.UNKNOWN, GateConsequence.REVIEW_REQUIRED),
                gate(GateStatus.FAIL, GateConsequence.SELL),
            )
        )
        is InvestmentStance.SELL
    )


def test_principle_score_is_weighted_and_missing_is_not_neutral() -> None:
    scores = (
        PrincipleScore(
            "quality", Decimal("4"), Decimal("0.6"), ("e1",), (), (), "rule", DataQuality.HIGH
        ),
        PrincipleScore(
            "balance", Decimal("2"), Decimal("0.4"), ("e2",), (), (), "rule", DataQuality.MEDIUM
        ),
    )
    assert weighted_principle_score(scores) == Decimal("3.2")
    unavailable = PrincipleScore(
        "valuation",
        None,
        Decimal("1"),
        (),
        (),
        ("current earnings",),
        "rule",
        DataQuality.UNAVAILABLE,
    )
    assert weighted_principle_score((unavailable,)) is None
    with pytest.raises(InvalidDecisionInputError, match="weights must sum to 1"):
        weighted_principle_score((scores[0],))


def test_relative_operating_valuation_and_three_year_cagr() -> None:
    result = calculate_scenario(
        ScenarioInput(
            name="base",
            starting_price=Decimal("100"),
            starting_revenue=Decimal("1000"),
            starting_operating_metric=Decimal("100"),
            annual_revenue_growth=Decimal("0.10"),
            terminal_margin=Decimal("0.12"),
            multiple_change_factor=Decimal("1.1"),
            equity_bridge_factor=Decimal("0.95"),
            horizon_years=3,
            evidence_ids=("e1",),
        )
    )
    assert result.target_price.quantize(Decimal("0.01")) == Decimal("166.91")
    assert result.price_cagr.quantize(Decimal("0.0001")) == Decimal("0.1862")
    with pytest.raises(InvalidDecisionInputError, match="starting price"):
        calculate_scenario(replace(result.input, starting_price=Decimal("0")))


def test_weights_cash_concentration_and_bear_portfolio_at_risk() -> None:
    weights = calculate_portfolio_weights({"a": Decimal("60"), "b": Decimal("40")})
    assert weights == {"a": Decimal("0.6"), "b": Decimal("0.4")}
    assert calculate_cash_weight({"a": Decimal("0.6"), "b": Decimal("0.2")}) == Decimal("0.2")
    concentration = calculate_concentration(
        weights,
        thresholds=ConcentrationThresholds(
            single_name=Decimal("0.55"), top_two=Decimal("0.85"), hhi=Decimal("0.50")
        ),
    )
    assert concentration.hhi == Decimal("0.52")
    assert concentration.effective_positions.quantize(Decimal("0.01")) == Decimal("1.92")
    assert concentration.requires_review is True
    assert portfolio_at_risk(Decimal("0.20"), Decimal("-0.35")) == Decimal("0.070")
    with pytest.raises(InvalidDecisionInputError, match="positive total"):
        calculate_portfolio_weights({"a": Decimal("0")})
    with pytest.raises(InvalidDecisionInputError, match="cannot exceed 1"):
        calculate_cash_weight({"a": Decimal("0.8"), "b": Decimal("0.3")})


def test_action_mapping_has_strict_hurdle_rebalance_band_and_review_overlay() -> None:
    assert (
        map_investment_stance(
            gate_stance=None,
            quality_pass=True,
            base_cagr=Decimal("0.251"),
            current_weight=Decimal("0.10"),
            target_weight=Decimal("0.151"),
        )
        is InvestmentStance.BUY
    )
    assert (
        map_investment_stance(
            gate_stance=None,
            quality_pass=True,
            base_cagr=Decimal("0.25"),
            current_weight=Decimal("0.10"),
            target_weight=Decimal("0.20"),
        )
        is InvestmentStance.HOLD
    )
    assert (
        map_investment_stance(
            gate_stance=None,
            quality_pass=True,
            base_cagr=Decimal("0.40"),
            current_weight=Decimal("0.10"),
            target_weight=Decimal("0.149"),
        )
        is InvestmentStance.HOLD
    )
    assert (
        map_investment_stance(
            gate_stance=InvestmentStance.SELL,
            quality_pass=True,
            base_cagr=Decimal("0.80"),
            current_weight=Decimal("0.10"),
            target_weight=Decimal("0"),
        )
        is InvestmentStance.SELL
    )
    assert (
        map_final_action(InvestmentStance.BUY, requires_human_review=True)
        is InvestmentStance.REVIEW_REQUIRED
    )
    assert (
        map_final_action(InvestmentStance.SELL, requires_human_review=False)
        is InvestmentStance.SELL
    )
    assert (
        map_final_action(
            InvestmentStance.SELL,
            requires_human_review=False,
            current_weight=Decimal("0.01"),
            target_weight=Decimal("0"),
        )
        is InvestmentStance.HOLD
    )
