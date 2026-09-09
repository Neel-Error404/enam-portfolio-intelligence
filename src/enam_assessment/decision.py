"""Deterministic investment-decision calculations and contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .errors import InvalidDecisionInputError


class GateStatus(StrEnum):
    """Outcome of evaluating one hard gate."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class GateConsequence(StrEnum):
    """Deterministic action caused by a non-passing gate."""

    NONE = "none"
    REVIEW_REQUIRED = "review_required"
    SELL = "sell"


class InvestmentStance(StrEnum):
    """Company-level investment conclusion before portfolio approval."""

    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    REVIEW_REQUIRED = "review_required"


class DataQuality(StrEnum):
    """Decision-layer assessment of evidence sufficiency."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class HardGateResult:
    """Traceable result for one mandatory decision gate."""

    code: str
    status: GateStatus
    evidence_ids: tuple[str, ...]
    explanation: str
    consequence: GateConsequence


@dataclass(frozen=True, slots=True)
class RatioGateEvaluation:
    """Decimal evaluation for a ratio that fails only above its upper bound."""

    numerator: Decimal
    denominator: Decimal
    ratio: Decimal
    threshold: Decimal
    status: GateStatus


@dataclass(frozen=True, slots=True)
class PrincipleScore:
    """One weighted investment-principle assessment with evidence lineage."""

    dimension: str
    score: Decimal | None
    weight: Decimal
    evidence_ids: tuple[str, ...]
    counter_evidence_ids: tuple[str, ...]
    missing_information: tuple[str, ...]
    rule: str
    data_quality: DataQuality


@dataclass(frozen=True, slots=True)
class ScenarioInput:
    """Inputs to the transparent relative operating-value model."""

    name: str
    starting_price: Decimal
    starting_revenue: Decimal
    starting_operating_metric: Decimal
    annual_revenue_growth: Decimal
    terminal_margin: Decimal
    multiple_change_factor: Decimal
    equity_bridge_factor: Decimal
    horizon_years: int
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Calculated scenario value and price CAGR."""

    input: ScenarioInput
    terminal_revenue: Decimal
    terminal_operating_metric: Decimal
    target_price: Decimal
    price_cagr: Decimal


@dataclass(frozen=True, slots=True)
class ConcentrationThresholds:
    """Prototype conventions that trigger human concentration review."""

    single_name: Decimal
    top_two: Decimal
    hhi: Decimal


@dataclass(frozen=True, slots=True)
class ConcentrationResult:
    """Portfolio concentration metrics for the represented sleeve."""

    largest_weight: Decimal
    top_two_weight: Decimal
    top_three_weight: Decimal
    hhi: Decimal
    effective_positions: Decimal
    requires_review: bool
    review_reasons: tuple[str, ...]


def resolve_gate_stance(gates: tuple[HardGateResult, ...]) -> InvestmentStance | None:
    """Resolve blocking gates, with an explicit sell consequence taking priority."""
    active = tuple(gate for gate in gates if gate.status is not GateStatus.PASS)
    if any(gate.consequence is GateConsequence.SELL for gate in active):
        return InvestmentStance.SELL
    if any(gate.consequence is GateConsequence.REVIEW_REQUIRED for gate in active):
        return InvestmentStance.REVIEW_REQUIRED
    return None


def calculate_upper_bound_ratio_gate(
    *, numerator: Decimal, denominator: Decimal, threshold: Decimal
) -> RatioGateEvaluation:
    """Evaluate an explicit ratio with a strict greater-than failure boundary."""
    if numerator < 0:
        raise InvalidDecisionInputError("Ratio-gate numerator cannot be negative.")
    if denominator <= 0:
        raise InvalidDecisionInputError("Ratio-gate denominator must be positive.")
    if threshold < 0:
        raise InvalidDecisionInputError("Ratio-gate threshold cannot be negative.")
    ratio = numerator / denominator
    return RatioGateEvaluation(
        numerator=numerator,
        denominator=denominator,
        ratio=ratio,
        threshold=threshold,
        status=GateStatus.FAIL if ratio > threshold else GateStatus.PASS,
    )


def weighted_principle_score(scores: tuple[PrincipleScore, ...]) -> Decimal | None:
    """Return the weighted 0-5 score, or unavailable when any dimension is missing."""
    if not scores:
        raise InvalidDecisionInputError("At least one principle score is required.")
    if any(item.weight <= 0 for item in scores):
        raise InvalidDecisionInputError("Principle weights must be positive.")
    if sum((item.weight for item in scores), Decimal("0")) != Decimal("1"):
        raise InvalidDecisionInputError("Principle weights must sum to 1.")
    if any(item.score is None for item in scores):
        return None
    values = tuple(item.score for item in scores if item.score is not None)
    if any(value < 0 or value > 5 for value in values):
        raise InvalidDecisionInputError("Principle scores must be between 0 and 5.")
    return sum(
        (item.score * item.weight for item in scores if item.score is not None),
        Decimal("0"),
    )


def calculate_scenario(item: ScenarioInput) -> ScenarioResult:
    """Calculate a three-step relative operating-value scenario without false precision."""
    if item.starting_price <= 0:
        raise InvalidDecisionInputError("Scenario starting price must be positive.")
    if item.starting_revenue <= 0 or item.starting_operating_metric <= 0:
        raise InvalidDecisionInputError("Starting revenue and operating metric must be positive.")
    if item.annual_revenue_growth <= Decimal("-1"):
        raise InvalidDecisionInputError("Annual revenue growth must be greater than -100%.")
    if item.terminal_margin <= 0:
        raise InvalidDecisionInputError("Terminal margin must be positive.")
    if item.multiple_change_factor <= 0 or item.equity_bridge_factor <= 0:
        raise InvalidDecisionInputError("Valuation factors must be positive.")
    if item.horizon_years <= 0:
        raise InvalidDecisionInputError("Scenario horizon must be positive.")
    terminal_revenue = (
        item.starting_revenue * (Decimal("1") + item.annual_revenue_growth) ** item.horizon_years
    )
    terminal_operating_metric = terminal_revenue * item.terminal_margin
    operating_growth_factor = terminal_operating_metric / item.starting_operating_metric
    target_price = (
        item.starting_price
        * operating_growth_factor
        * item.multiple_change_factor
        * item.equity_bridge_factor
    )
    price_cagr = (target_price / item.starting_price) ** (
        Decimal("1") / Decimal(item.horizon_years)
    ) - Decimal("1")
    return ScenarioResult(
        input=item,
        terminal_revenue=terminal_revenue,
        terminal_operating_metric=terminal_operating_metric,
        target_price=target_price,
        price_cagr=price_cagr,
    )


def calculate_portfolio_weights(values: dict[str, Decimal]) -> dict[str, Decimal]:
    """Normalize non-negative market values into deterministic weights."""
    if not values or any(value < 0 for value in values.values()):
        raise InvalidDecisionInputError("Portfolio values must be non-negative and non-empty.")
    total = sum(values.values(), Decimal("0"))
    if total <= 0:
        raise InvalidDecisionInputError("Portfolio values must have a positive total.")
    return {name: values[name] / total for name in sorted(values)}


def calculate_cash_weight(target_weights: dict[str, Decimal]) -> Decimal:
    """Return residual cash after non-negative target allocations."""
    if any(value < 0 for value in target_weights.values()):
        raise InvalidDecisionInputError("Target weights cannot be negative.")
    allocated = sum(target_weights.values(), Decimal("0"))
    if allocated > 1:
        raise InvalidDecisionInputError("Target weights cannot exceed 1 in total.")
    return Decimal("1") - allocated


def calculate_concentration(
    weights: dict[str, Decimal], *, thresholds: ConcentrationThresholds
) -> ConcentrationResult:
    """Calculate HHI/effective positions and prototype review triggers."""
    if not weights or any(value < 0 or value > 1 for value in weights.values()):
        raise InvalidDecisionInputError("Concentration weights must be within 0 and 1.")
    total = sum(weights.values(), Decimal("0"))
    if total <= 0 or total > 1:
        raise InvalidDecisionInputError("Concentration weights must have a total in (0, 1].")
    ordered = sorted(weights.values(), reverse=True)
    largest = ordered[0]
    top_two = sum(ordered[:2], Decimal("0"))
    top_three = sum(ordered[:3], Decimal("0"))
    hhi = sum((weight * weight for weight in ordered), Decimal("0"))
    reasons: list[str] = []
    if largest > thresholds.single_name:
        reasons.append("single_name")
    if top_two > thresholds.top_two:
        reasons.append("top_two")
    if hhi > thresholds.hhi:
        reasons.append("hhi")
    return ConcentrationResult(
        largest_weight=largest,
        top_two_weight=top_two,
        top_three_weight=top_three,
        hhi=hhi,
        effective_positions=Decimal("1") / hhi,
        requires_review=bool(reasons),
        review_reasons=tuple(reasons),
    )


def portfolio_at_risk(weight: Decimal, bear_case_return: Decimal) -> Decimal:
    """Return weight multiplied by documented bear-case downside."""
    if weight < 0 or weight > 1:
        raise InvalidDecisionInputError("Portfolio weight must be within 0 and 1.")
    if bear_case_return < Decimal("-1"):
        raise InvalidDecisionInputError("Bear-case return cannot be below -100%.")
    return weight * max(-bear_case_return, Decimal("0"))


def map_investment_stance(
    *,
    gate_stance: InvestmentStance | None,
    quality_pass: bool,
    base_cagr: Decimal,
    current_weight: Decimal,
    target_weight: Decimal,
    buy_hurdle: Decimal = Decimal("0.25"),
    rebalance_band: Decimal = Decimal("0.05"),
) -> InvestmentStance:
    """Map gates, quality, valuation, and exposure into a company stance."""
    for name, value in (("current", current_weight), ("target", target_weight)):
        if value < 0 or value > 1:
            raise InvalidDecisionInputError(f"{name.title()} weight must be within 0 and 1.")
    if gate_stance is not None:
        return gate_stance
    if not quality_pass or base_cagr <= 0:
        return InvestmentStance.SELL
    change = target_weight - current_weight
    if change <= -rebalance_band:
        return InvestmentStance.SELL
    if base_cagr > buy_hurdle and change >= rebalance_band:
        return InvestmentStance.BUY
    return InvestmentStance.HOLD


def map_final_action(
    stance: InvestmentStance,
    *,
    requires_human_review: bool,
    current_weight: Decimal | None = None,
    target_weight: Decimal | None = None,
    rebalance_band: Decimal = Decimal("0.05"),
    force_sell: bool = False,
) -> InvestmentStance:
    """Apply approval and no-trade-band rules without hiding the underlying stance."""
    if stance is InvestmentStance.REVIEW_REQUIRED or requires_human_review:
        return InvestmentStance.REVIEW_REQUIRED
    if (
        stance is InvestmentStance.SELL
        and not force_sell
        and current_weight is not None
        and target_weight is not None
        and current_weight - target_weight < rebalance_band
    ):
        return InvestmentStance.HOLD
    return stance
