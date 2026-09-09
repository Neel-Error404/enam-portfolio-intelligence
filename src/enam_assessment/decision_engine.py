"""Offline orchestration for traceable investment and portfolio decisions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from .decision import (
    ConcentrationResult,
    ConcentrationThresholds,
    DataQuality,
    GateConsequence,
    GateStatus,
    HardGateResult,
    InvestmentStance,
    PrincipleScore,
    ScenarioInput,
    ScenarioResult,
    calculate_cash_weight,
    calculate_concentration,
    calculate_portfolio_weights,
    calculate_scenario,
    calculate_upper_bound_ratio_gate,
    map_final_action,
    map_investment_stance,
    portfolio_at_risk,
    resolve_gate_stance,
    weighted_principle_score,
)
from .errors import EvidenceReferenceError, InvalidDecisionInputError
from .evidence import DataState, EvidenceSnapshot, FundamentalFact, PriceObservation

DECISION_DATE = date(2026, 9, 8)


@dataclass(frozen=True, slots=True)
class DecisionEngineConfig:
    """Versioned prototype thresholds and benchmark declarations."""

    decision_date: date
    engine_version: str
    configuration_version: str
    quality_threshold: Decimal
    buy_hurdle: Decimal
    rebalance_band: Decimal
    position_bear_loss_budget: Decimal
    minimum_sizing_downside: Decimal
    dbl_net_debt_to_ebitda_sell_threshold: Decimal
    concentration_thresholds: ConcentrationThresholds
    primary_benchmark_id: str
    primary_benchmark_status: str
    secondary_benchmark_id: str
    secondary_benchmark_status: str


@dataclass(frozen=True, slots=True)
class CompanyDecisionSpec:
    """Human-readable, evidence-linked assumptions for one company."""

    company_id: str
    company_name: str
    working_shares: Decimal
    working_cost_basis: Decimal
    gates: tuple[HardGateResult, ...]
    principle_scores: tuple[PrincipleScore, ...]
    scenarios: tuple[ScenarioInput, ...]
    confidence_factor: Decimal
    change_triggers: tuple[str, ...]
    common_drivers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompanyDecisionSnapshot:
    """One complete company decision with evidence and portfolio lineage."""

    company_id: str
    company_name: str
    decision_date: date
    evidence_manifest_sha256: str
    working_shares: Decimal
    working_cost_basis: Decimal
    current_price: Decimal
    price_date: date
    price_age_days: int
    approximate_market_value: Decimal
    working_current_weight: Decimal
    provisional_holdings: bool
    gates: tuple[HardGateResult, ...]
    principle_scores: tuple[PrincipleScore, ...]
    weighted_principle_score: Decimal | None
    scenarios: tuple[ScenarioResult, ...]
    target_weight: Decimal
    position_bear_portfolio_at_risk: Decimal
    historical_benchmark_context: dict[str, object]
    underlying_stance: InvestmentStance
    final_action: InvestmentStance
    confidence: DataQuality
    missing_data_flags: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence_dates: tuple[tuple[str, date], ...]
    engine_version: str
    configuration_version: str
    human_review_required: bool
    human_review_reasons: tuple[str, ...]
    change_triggers: tuple[str, ...]
    common_drivers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioDecisionSnapshot:
    """Four-company working sleeve and deterministic decision results."""

    decision_date: date
    evidence_manifest_sha256: str
    engine_version: str
    configuration_version: str
    companies: tuple[CompanyDecisionSnapshot, ...]
    cash_target_weight: Decimal
    current_concentration: ConcentrationResult
    target_concentration: ConcentrationResult | None
    target_bear_portfolio_at_risk: Decimal
    primary_benchmark_id: str
    primary_benchmark_status: str
    secondary_benchmark_id: str
    secondary_benchmark_status: str
    provisional_holdings_warning: str

    def company(self, company_id: str) -> CompanyDecisionSnapshot:
        """Return a company result or raise an actionable error."""
        for item in self.companies:
            if item.company_id == company_id:
                return item
        raise KeyError(f"Decision snapshot has no company {company_id!r}.")

    def stable_payload(self) -> dict[str, object]:
        """Return JSON-compatible content used for persistence and replay hashing."""
        return cast(dict[str, object], _json_value(asdict(self)))

    @property
    def snapshot_sha256(self) -> str:
        """Hash the canonical decision payload for deterministic replay checks."""
        encoded = json.dumps(
            self.stable_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


def build_decisions(
    evidence: EvidenceSnapshot,
    specs: tuple[CompanyDecisionSpec, ...],
    config: DecisionEngineConfig,
    *,
    historical_context: dict[str, dict[str, object]],
) -> PortfolioDecisionSnapshot:
    """Build four decisions using only the supplied frozen evidence and specs."""
    _validate_config(config)
    if evidence.analysis_as_of != config.decision_date:
        raise InvalidDecisionInputError(
            "Evidence snapshot as-of date must equal the configured decision date."
        )
    if len(specs) != 4 or len({item.company_id for item in specs}) != 4:
        raise InvalidDecisionInputError("Exactly four unique company decision specs are required.")

    specs = _apply_calculated_dbl_gate(specs, evidence, config)

    evidence_dates = _evidence_dates(evidence)
    prices: dict[str, PriceObservation] = {}
    scenario_results: dict[str, tuple[ScenarioResult, ...]] = {}
    totals: dict[str, Decimal | None] = {}
    for spec in specs:
        _validate_spec(spec, evidence_dates, config)
        price = _latest_price(evidence, spec.company_id, config.decision_date)
        decision_price = _decision_price(price)
        if any(item.starting_price != decision_price for item in spec.scenarios):
            raise InvalidDecisionInputError(
                f"{spec.company_id}: every scenario starting price must equal the latest "
                f"validated price {decision_price} on {price.trading_date.isoformat()}."
            )
        prices[spec.company_id] = price
        calculated = tuple(
            calculate_scenario(item)
            for item in sorted(spec.scenarios, key=lambda value: value.name)
        )
        scenario_results[spec.company_id] = calculated
        totals[spec.company_id] = weighted_principle_score(spec.principle_scores)

    market_values = {
        spec.company_id: spec.working_shares * _decision_price(prices[spec.company_id])
        for spec in specs
    }
    current_weights = calculate_portfolio_weights(market_values)
    current_concentration = calculate_concentration(
        current_weights, thresholds=config.concentration_thresholds
    )
    target_weights = _target_weights(specs, scenario_results, totals, config)
    cash_weight = calculate_cash_weight(target_weights)
    invested = sum(target_weights.values(), Decimal("0"))
    target_concentration = (
        calculate_concentration(
            {name: value / invested for name, value in target_weights.items() if value > 0},
            thresholds=config.concentration_thresholds,
        )
        if invested > 0
        else None
    )

    company_results: list[CompanyDecisionSnapshot] = []
    for spec in sorted(specs, key=lambda item: item.company_id):
        price = prices[spec.company_id]
        results = scenario_results[spec.company_id]
        by_name = {item.input.name: item for item in results}
        total = totals[spec.company_id]
        gate_stance = resolve_gate_stance(spec.gates)
        if total is None and gate_stance is None:
            gate_stance = InvestmentStance.REVIEW_REQUIRED
        quality_pass = total is not None and total >= config.quality_threshold
        underlying = map_investment_stance(
            gate_stance=gate_stance,
            quality_pass=quality_pass,
            base_cagr=by_name["base"].price_cagr,
            current_weight=current_weights[spec.company_id],
            target_weight=target_weights[spec.company_id],
            buy_hurdle=config.buy_hurdle,
            rebalance_band=config.rebalance_band,
        )
        review_reasons: list[str] = []
        material_change = (
            abs(target_weights[spec.company_id] - current_weights[spec.company_id])
            >= config.rebalance_band
        )
        if material_change:
            review_reasons.append("provisional_holdings_material_to_rebalance")
        if (
            underlying is InvestmentStance.BUY
            and target_concentration is not None
            and target_concentration.requires_review
        ):
            review_reasons.append("target_concentration_requires_approval")
        if gate_stance is InvestmentStance.REVIEW_REQUIRED:
            review_reasons.append("blocking_gate_requires_review")
        sell_gate = any(
            gate.status is not GateStatus.PASS and gate.consequence is GateConsequence.SELL
            for gate in spec.gates
        )
        final_action = map_final_action(
            underlying,
            requires_human_review=bool(review_reasons),
            current_weight=current_weights[spec.company_id],
            target_weight=target_weights[spec.company_id],
            rebalance_band=config.rebalance_band,
            force_sell=sell_gate,
        )
        cited_ids = _spec_evidence_ids(spec) | {price.evidence_id}
        missing_flags = tuple(
            sorted(
                {
                    missing
                    for score in spec.principle_scores
                    for missing in score.missing_information
                }
            )
        )
        quality_values = tuple(score.data_quality for score in spec.principle_scores)
        confidence = _lowest_quality(quality_values)
        company_results.append(
            CompanyDecisionSnapshot(
                company_id=spec.company_id,
                company_name=spec.company_name,
                decision_date=config.decision_date,
                evidence_manifest_sha256=evidence.manifest_sha256,
                working_shares=spec.working_shares,
                working_cost_basis=spec.working_cost_basis,
                current_price=_decision_price(price),
                price_date=price.trading_date,
                price_age_days=(config.decision_date - price.trading_date).days,
                approximate_market_value=market_values[spec.company_id],
                working_current_weight=current_weights[spec.company_id],
                provisional_holdings=True,
                gates=tuple(sorted(spec.gates, key=lambda item: item.code)),
                principle_scores=tuple(
                    sorted(spec.principle_scores, key=lambda item: item.dimension)
                ),
                weighted_principle_score=total,
                scenarios=results,
                target_weight=target_weights[spec.company_id],
                position_bear_portfolio_at_risk=portfolio_at_risk(
                    target_weights[spec.company_id], by_name["bear"].price_cagr
                ),
                historical_benchmark_context=historical_context.get(spec.company_id, {}),
                underlying_stance=underlying,
                final_action=final_action,
                confidence=confidence,
                missing_data_flags=missing_flags,
                evidence_ids=tuple(sorted(cited_ids)),
                evidence_dates=tuple(
                    (evidence_id, evidence_dates[evidence_id]) for evidence_id in sorted(cited_ids)
                ),
                engine_version=config.engine_version,
                configuration_version=config.configuration_version,
                human_review_required=bool(review_reasons),
                human_review_reasons=tuple(review_reasons),
                change_triggers=spec.change_triggers,
                common_drivers=spec.common_drivers,
            )
        )
    return PortfolioDecisionSnapshot(
        decision_date=config.decision_date,
        evidence_manifest_sha256=evidence.manifest_sha256,
        engine_version=config.engine_version,
        configuration_version=config.configuration_version,
        companies=tuple(company_results),
        cash_target_weight=cash_weight,
        current_concentration=current_concentration,
        target_concentration=target_concentration,
        target_bear_portfolio_at_risk=sum(
            (item.position_bear_portfolio_at_risk for item in company_results), Decimal("0")
        ),
        primary_benchmark_id=config.primary_benchmark_id,
        primary_benchmark_status=config.primary_benchmark_status,
        secondary_benchmark_id=config.secondary_benchmark_id,
        secondary_benchmark_status=config.secondary_benchmark_status,
        provisional_holdings_warning=(
            "Workbook open lots are an unverified working holdings proxy; weights and actions "
            "are approximate and require owner confirmation before trading."
        ),
    )


def load_decision_configuration(
    path: Path,
) -> tuple[DecisionEngineConfig, tuple[CompanyDecisionSpec, ...]]:
    """Load the explicit JSON rules and assumptions used by the offline engine."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        thresholds = raw["thresholds"]
        benchmarks = raw["benchmarks"]
        config = DecisionEngineConfig(
            decision_date=date.fromisoformat(raw["decision_date"]),
            engine_version=str(raw["engine_version"]),
            configuration_version=str(raw["configuration_version"]),
            quality_threshold=Decimal(str(thresholds["quality_threshold"])),
            buy_hurdle=Decimal(str(thresholds["buy_hurdle"])),
            rebalance_band=Decimal(str(thresholds["rebalance_band"])),
            position_bear_loss_budget=Decimal(str(thresholds["position_bear_loss_budget"])),
            minimum_sizing_downside=Decimal(str(thresholds["minimum_sizing_downside"])),
            dbl_net_debt_to_ebitda_sell_threshold=Decimal(
                str(thresholds["dbl_net_debt_to_ebitda_sell_threshold"])
            ),
            concentration_thresholds=ConcentrationThresholds(
                single_name=Decimal(str(thresholds["concentration"]["single_name"])),
                top_two=Decimal(str(thresholds["concentration"]["top_two"])),
                hhi=Decimal(str(thresholds["concentration"]["hhi"])),
            ),
            primary_benchmark_id=str(benchmarks["primary"]["instrument_id"]),
            primary_benchmark_status=str(benchmarks["primary"]["status"]),
            secondary_benchmark_id=str(benchmarks["secondary"]["instrument_id"]),
            secondary_benchmark_status=str(benchmarks["secondary"]["status"]),
        )
        specs = tuple(_company_spec_from_dict(item) for item in raw["companies"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise InvalidDecisionInputError(
            f"Invalid decision configuration {path}: {error}"
        ) from error
    return config, tuple(sorted(specs, key=lambda item: item.company_id))


def write_decision_snapshot(snapshot: PortfolioDecisionSnapshot, path: Path) -> None:
    """Persist canonical decision results plus their replay hash."""
    payload = snapshot.stable_payload()
    payload["snapshot_sha256"] = snapshot.snapshot_sha256
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _company_spec_from_dict(item: dict[str, object]) -> CompanyDecisionSpec:
    gates = tuple(
        HardGateResult(
            code=str(gate["code"]),
            status=GateStatus(str(gate["status"])),
            evidence_ids=_strings(gate["evidence_ids"]),
            explanation=str(gate["explanation"]),
            consequence=GateConsequence(str(gate["consequence"])),
        )
        for gate in _objects(item["gates"])
    )
    scores = tuple(
        PrincipleScore(
            dimension=str(score["dimension"]),
            score=None if score.get("score") is None else Decimal(str(score["score"])),
            weight=Decimal(str(score["weight"])),
            evidence_ids=_strings(score["evidence_ids"]),
            counter_evidence_ids=_strings(score["counter_evidence_ids"]),
            missing_information=_strings(score["missing_information"]),
            rule=str(score["rule"]),
            data_quality=DataQuality(str(score["data_quality"])),
        )
        for score in _objects(item["principle_scores"])
    )
    scenarios = tuple(
        ScenarioInput(
            name=str(scenario["name"]),
            starting_price=Decimal(str(scenario["starting_price"])),
            starting_revenue=Decimal(str(scenario["starting_revenue"])),
            starting_operating_metric=Decimal(str(scenario["starting_operating_metric"])),
            annual_revenue_growth=Decimal(str(scenario["annual_revenue_growth"])),
            terminal_margin=Decimal(str(scenario["terminal_margin"])),
            multiple_change_factor=Decimal(str(scenario["multiple_change_factor"])),
            equity_bridge_factor=Decimal(str(scenario["equity_bridge_factor"])),
            horizon_years=int(str(scenario["horizon_years"])),
            evidence_ids=_strings(scenario["evidence_ids"]),
        )
        for scenario in _objects(item["scenarios"])
    )
    return CompanyDecisionSpec(
        company_id=str(item["company_id"]),
        company_name=str(item["company_name"]),
        working_shares=Decimal(str(item["working_shares"])),
        working_cost_basis=Decimal(str(item["working_cost_basis"])),
        gates=gates,
        principle_scores=scores,
        scenarios=scenarios,
        confidence_factor=Decimal(str(item["confidence_factor"])),
        change_triggers=_strings(item["change_triggers"]),
        common_drivers=_strings(item["common_drivers"]),
    )


def _objects(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError("expected a list of objects")
    return tuple(value)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("expected a list of strings")
    return tuple(value)


def _validate_config(config: DecisionEngineConfig) -> None:
    if config.decision_date != DECISION_DATE:
        raise InvalidDecisionInputError("Phase 5 decision date must be 2026-09-08.")
    for name, value in (
        ("quality threshold", config.quality_threshold),
        ("buy hurdle", config.buy_hurdle),
        ("rebalance band", config.rebalance_band),
        ("position bear loss budget", config.position_bear_loss_budget),
        ("minimum sizing downside", config.minimum_sizing_downside),
        (
            "DBL net-debt-to-EBITDA sell threshold",
            config.dbl_net_debt_to_ebitda_sell_threshold,
        ),
    ):
        if value <= 0:
            raise InvalidDecisionInputError(f"{name.title()} must be positive.")


def _apply_calculated_dbl_gate(
    specs: tuple[CompanyDecisionSpec, ...],
    evidence: EvidenceSnapshot,
    config: DecisionEngineConfig,
) -> tuple[CompanyDecisionSpec, ...]:
    net_debt_id = "fundamental-dbl-consolidated-net-debt-fy26"
    ebitda_id = "fundamental-c02d7f1564a6c6e4"
    net_debt = _required_decimal_fact(evidence, net_debt_id, "consolidated_net_debt")
    ebitda = _required_decimal_fact(evidence, ebitda_id, "consolidated_ebitda")
    if net_debt.unit != ebitda.unit or net_debt.unit != "INR crore":
        raise InvalidDecisionInputError(
            "DBL ratio gate requires consolidated net debt and EBITDA in INR crore."
        )
    evaluation = calculate_upper_bound_ratio_gate(
        numerator=cast(Decimal, net_debt.value),
        denominator=cast(Decimal, ebitda.value),
        threshold=config.dbl_net_debt_to_ebitda_sell_threshold,
    )
    updated: list[CompanyDecisionSpec] = []
    for spec in specs:
        if spec.company_id != "dbl":
            updated.append(spec)
            continue
        matched = False
        gates: list[HardGateResult] = []
        for gate in spec.gates:
            if gate.code != "balance_sheet_liquidity_and_funding":
                gates.append(gate)
                continue
            matched = True
            status = evaluation.status
            gates.append(
                HardGateResult(
                    code=gate.code,
                    status=status,
                    evidence_ids=(net_debt_id, ebitda_id, *gate.evidence_ids[2:]),
                    explanation=(
                        f"Consolidated net debt is {evaluation.ratio:.2f} times FY26 EBITDA, "
                        f"{'above' if status is GateStatus.FAIL else 'not above'} the prototype "
                        f"{evaluation.threshold:.1f}-times sell threshold, with 131 "
                        "working-capital days."
                    ),
                    consequence=(
                        GateConsequence.SELL if status is GateStatus.FAIL else GateConsequence.NONE
                    ),
                )
            )
        if not matched:
            raise InvalidDecisionInputError(
                "DBL decision spec is missing balance_sheet_liquidity_and_funding gate."
            )
        updated.append(replace(spec, gates=tuple(gates)))
    return tuple(updated)


def _required_decimal_fact(
    evidence: EvidenceSnapshot, evidence_id: str, metric_name: str
) -> FundamentalFact:
    matches = tuple(item for item in evidence.fundamentals if item.evidence_id == evidence_id)
    if len(matches) != 1:
        raise EvidenceReferenceError(
            f"DBL ratio gate requires exactly one evidence record {evidence_id!r}."
        )
    fact = matches[0]
    if fact.company_id != "dbl" or fact.metric_name != metric_name:
        raise InvalidDecisionInputError(
            f"DBL ratio evidence {evidence_id!r} has incompatible company or metric scope."
        )
    if not isinstance(fact.value, Decimal):
        raise InvalidDecisionInputError(
            f"DBL ratio evidence {evidence_id!r} must contain a Decimal value."
        )
    return fact


def _validate_spec(
    spec: CompanyDecisionSpec,
    evidence_dates: dict[str, date],
    config: DecisionEngineConfig,
) -> None:
    if spec.working_shares < 0 or spec.working_cost_basis < 0:
        raise InvalidDecisionInputError(f"{spec.company_id}: holdings values cannot be negative.")
    if spec.confidence_factor < 0 or spec.confidence_factor > 1:
        raise InvalidDecisionInputError(f"{spec.company_id}: confidence factor must be in [0, 1].")
    scenario_names = {item.name for item in spec.scenarios}
    if scenario_names != {"bear", "base", "bull"}:
        raise InvalidDecisionInputError(
            f"{spec.company_id}: scenarios must contain bear, base, and bull exactly once."
        )
    for evidence_id in sorted(_spec_evidence_ids(spec)):
        if evidence_id not in evidence_dates:
            raise EvidenceReferenceError(
                f"{spec.company_id}: evidence ID {evidence_id!r} is absent from the "
                "frozen snapshot."
            )
        if evidence_dates[evidence_id] > config.decision_date:
            raise EvidenceReferenceError(
                f"{spec.company_id}: evidence ID {evidence_id!r} is after the decision date."
            )


def _target_weights(
    specs: tuple[CompanyDecisionSpec, ...],
    scenarios: dict[str, tuple[ScenarioResult, ...]],
    totals: dict[str, Decimal | None],
    config: DecisionEngineConfig,
) -> dict[str, Decimal]:
    raw: dict[str, Decimal] = {}
    for spec in specs:
        total = totals[spec.company_id]
        gate_stance = resolve_gate_stance(spec.gates)
        by_name = {item.input.name: item for item in scenarios[spec.company_id]}
        base_cagr = by_name["base"].price_cagr
        if (
            gate_stance is not None
            or total is None
            or total < config.quality_threshold
            or base_cagr <= 0
        ):
            raw[spec.company_id] = Decimal("0")
            continue
        downside = max(-by_name["bear"].price_cagr, config.minimum_sizing_downside)
        return_factor = min(base_cagr / config.buy_hurdle, Decimal("1"))
        raw[spec.company_id] = (
            config.position_bear_loss_budget
            / downside
            * (total / Decimal("5"))
            * spec.confidence_factor
            * return_factor
        )
    total_raw = sum(raw.values(), Decimal("0"))
    scale = Decimal("1") / total_raw if total_raw > 1 else Decimal("1")
    return {company_id: raw[company_id] * scale for company_id in sorted(raw)}


def _latest_price(
    snapshot: EvidenceSnapshot, company_id: str, decision_date: date
) -> PriceObservation:
    candidates = tuple(
        item
        for item in snapshot.prices
        if item.instrument_id == company_id
        and item.trading_date <= decision_date
        and item.validation_status is DataState.AVAILABLE
        and _decision_price(item) > 0
    )
    if not candidates:
        raise InvalidDecisionInputError(
            f"{company_id}: no valid price is available on or before {decision_date.isoformat()}."
        )
    return max(candidates, key=lambda item: (item.trading_date, item.evidence_id))


def _decision_price(price: PriceObservation) -> Decimal:
    return price.adjusted_close if price.adjusted_close is not None else price.close


def _evidence_dates(snapshot: EvidenceSnapshot) -> dict[str, date]:
    dates = {item.evidence_id: item.publication_date for item in snapshot.fundamentals}
    dates.update({item.evidence_id: item.publication_date for item in snapshot.research})
    dates.update({item.evidence_id: item.trading_date for item in snapshot.prices})
    return dates


def _spec_evidence_ids(spec: CompanyDecisionSpec) -> set[str]:
    return {
        evidence_id
        for evidence_ids in (
            *(item.evidence_ids for item in spec.gates),
            *(item.evidence_ids for item in spec.principle_scores),
            *(item.counter_evidence_ids for item in spec.principle_scores),
            *(item.evidence_ids for item in spec.scenarios),
        )
        for evidence_id in evidence_ids
    }


def _lowest_quality(values: tuple[DataQuality, ...]) -> DataQuality:
    rank = {
        DataQuality.HIGH: 3,
        DataQuality.MEDIUM: 2,
        DataQuality.LOW: 1,
        DataQuality.UNAVAILABLE: 0,
    }
    return min(values, key=lambda item: rank[item])


def _json_value(value: object) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value
