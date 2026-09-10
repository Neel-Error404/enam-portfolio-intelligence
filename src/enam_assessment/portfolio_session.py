"""Deterministic session overlays for holdings, scenarios, and human disposition."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

from .decision import (
    ConcentrationResult,
    ConcentrationThresholds,
    ScenarioInput,
    ScenarioResult,
    calculate_concentration,
    calculate_scenario,
)
from .errors import HoldingsOverlayError, ScenarioLabError
from .memo import DecisionMemoInput

Disposition = Literal["accepted", "rejected", "deferred"]
HoldingSource = Literal["supplied_workbook", "user_entered"]
CashSource = Literal["assumed_zero", "user_entered"]


@dataclass(frozen=True, slots=True)
class HoldingInput:
    """One session-local working holding with explicit provenance."""

    company_id: str
    shares: Decimal
    price: Decimal
    source: HoldingSource


@dataclass(frozen=True, slots=True)
class HoldingsOverlay:
    """A session-only working portfolio that never mutates the frozen snapshot."""

    holdings: tuple[HoldingInput, ...]
    available_cash: Decimal
    cash_source: CashSource
    company_values: dict[str, Decimal]
    company_weights: dict[str, Decimal]
    cash_weight: Decimal
    total_value: Decimal
    concentration: ConcentrationResult
    uses_session_values: bool

    @property
    def uses_verified_values(self) -> bool:
        """Compatibility alias; session entries are not independent verification."""
        return self.uses_session_values


@dataclass(frozen=True, slots=True)
class ScenarioDelta:
    """Frozen baseline and deterministic recalculation for one supported scenario."""

    company_id: str
    scenario_name: str
    baseline: ScenarioResult
    recalculated: ScenarioResult
    overrides: dict[str, str]
    target_price_delta: Decimal
    price_cagr_delta: Decimal

    def stable_payload(self) -> dict[str, object]:
        return cast(dict[str, object], _json_value(asdict(self)))


@dataclass(frozen=True, slots=True)
class HumanDisposition:
    """A supervised session record that does not alter the engine decision."""

    company_id: str
    disposition: Disposition
    note: str
    recorded_at: datetime
    decision_snapshot_sha256: str
    engine_stance: str
    engine_action: str

    def stable_payload(self) -> dict[str, object]:
        return cast(dict[str, object], _json_value(asdict(self)))


def calculate_holdings_overlay(
    decisions: tuple[DecisionMemoInput, ...],
    *,
    share_overrides: dict[str, Decimal] | None = None,
    available_cash: Decimal | None = None,
    thresholds: ConcentrationThresholds = ConcentrationThresholds(
        single_name=Decimal("0.35"),
        top_two=Decimal("0.60"),
        hhi=Decimal("0.30"),
    ),
) -> HoldingsOverlay:
    """Value supplied-data defaults or session entries without changing the snapshot."""
    cash = Decimal("0") if available_cash is None else available_cash
    if cash < 0:
        raise HoldingsOverlayError("Available cash cannot be negative.")
    overrides = share_overrides or {}
    known = {item.company_id for item in decisions}
    unknown = set(overrides) - known
    if unknown:
        raise HoldingsOverlayError(f"Unknown company share overrides: {sorted(unknown)}.")

    holdings: list[HoldingInput] = []
    values: dict[str, Decimal] = {}
    for decision in decisions:
        baseline = _holding_decimal(
            decision.working_shares, f"{decision.company_id} baseline shares"
        )
        shares = overrides.get(decision.company_id, baseline)
        if shares < 0:
            raise HoldingsOverlayError(f"{decision.company_id} shares cannot be negative.")
        price = _holding_decimal(decision.current_price, f"{decision.company_id} price")
        source: HoldingSource = (
            "user_entered" if decision.company_id in overrides else "supplied_workbook"
        )
        holdings.append(HoldingInput(decision.company_id, shares, price, source))
        values[decision.company_id] = shares * price

    total_value = sum(values.values(), Decimal("0")) + cash
    if total_value <= 0:
        raise HoldingsOverlayError("Holdings and available cash must have a positive total value.")
    weights = {company_id: value / total_value for company_id, value in sorted(values.items())}
    concentration = calculate_concentration(weights, thresholds=thresholds)
    return HoldingsOverlay(
        holdings=tuple(holdings),
        available_cash=cash,
        cash_source="assumed_zero" if available_cash is None else "user_entered",
        company_values=values,
        company_weights=weights,
        cash_weight=cash / total_value,
        total_value=total_value,
        concentration=concentration,
        uses_session_values=bool(overrides) or available_cash is not None,
    )


def recalculate_scenario(
    decision: DecisionMemoInput,
    *,
    scenario_name: str,
    annual_revenue_growth: Decimal,
    terminal_margin: Decimal,
    multiple_change_factor: Decimal,
    equity_bridge_factor: Decimal,
) -> ScenarioDelta:
    """Recalculate supported scenario inputs through the existing Phase 5 function."""
    matches = [item for item in decision.scenarios if _scenario_name(item) == scenario_name]
    if len(matches) != 1:
        raise ScenarioLabError(
            f"{decision.company_id}: expected one {scenario_name!r} scenario, found {len(matches)}."
        )
    raw = matches[0]
    raw_input = _object(raw.get("input"), "scenario input")
    baseline_input = _scenario_input(raw_input)
    baseline = calculate_scenario(baseline_input)
    stored_target = _scenario_decimal(str(raw.get("target_price")), "stored target price")
    stored_cagr = _scenario_decimal(str(raw.get("price_cagr")), "stored price CAGR")
    if baseline.target_price != stored_target or baseline.price_cagr != stored_cagr:
        raise ScenarioLabError(
            f"{decision.company_id}: frozen {scenario_name} scenario no longer reproduces."
        )
    updated_input = replace(
        baseline_input,
        annual_revenue_growth=annual_revenue_growth,
        terminal_margin=terminal_margin,
        multiple_change_factor=multiple_change_factor,
        equity_bridge_factor=equity_bridge_factor,
    )
    try:
        recalculated = calculate_scenario(updated_input)
    except Exception as exc:
        raise ScenarioLabError(
            f"{decision.company_id}: unsupported scenario override: {exc}"
        ) from exc
    return ScenarioDelta(
        company_id=decision.company_id,
        scenario_name=scenario_name,
        baseline=baseline,
        recalculated=recalculated,
        overrides={
            "annual_revenue_growth": str(annual_revenue_growth),
            "terminal_margin": str(terminal_margin),
            "multiple_change_factor": str(multiple_change_factor),
            "equity_bridge_factor": str(equity_bridge_factor),
        },
        target_price_delta=recalculated.target_price - baseline.target_price,
        price_cagr_delta=recalculated.price_cagr - baseline.price_cagr,
    )


def record_disposition(
    decision: DecisionMemoInput,
    *,
    disposition: Disposition,
    note: str,
    recorded_at: datetime,
) -> HumanDisposition:
    """Create one auditable human decision without changing the engine output."""
    if disposition not in {"accepted", "rejected", "deferred"}:
        raise HoldingsOverlayError("Disposition must be accepted, rejected, or deferred.")
    return HumanDisposition(
        company_id=decision.company_id,
        disposition=disposition,
        note=note.strip(),
        recorded_at=recorded_at,
        decision_snapshot_sha256=decision.decision_snapshot_sha256,
        engine_stance=decision.underlying_stance,
        engine_action=decision.final_portfolio_action,
    )


def _scenario_input(raw: dict[str, object]) -> ScenarioInput:
    return ScenarioInput(
        name=str(raw["name"]),
        starting_price=_scenario_decimal(str(raw["starting_price"]), "starting price"),
        starting_revenue=_scenario_decimal(str(raw["starting_revenue"]), "starting revenue"),
        starting_operating_metric=_scenario_decimal(
            str(raw["starting_operating_metric"]), "starting operating metric"
        ),
        annual_revenue_growth=_scenario_decimal(
            str(raw["annual_revenue_growth"]), "annual revenue growth"
        ),
        terminal_margin=_scenario_decimal(str(raw["terminal_margin"]), "terminal margin"),
        multiple_change_factor=_scenario_decimal(
            str(raw["multiple_change_factor"]), "multiple change factor"
        ),
        equity_bridge_factor=_scenario_decimal(
            str(raw["equity_bridge_factor"]), "equity bridge factor"
        ),
        horizon_years=int(str(raw["horizon_years"])),
        evidence_ids=tuple(str(item) for item in cast(list[object], raw["evidence_ids"])),
    )


def _scenario_name(raw: dict[str, object]) -> str:
    return str(_object(raw.get("input"), "scenario input")["name"])


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ScenarioLabError(f"{label} must be an object.")
    return cast(dict[str, object], value)


def _holding_decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise HoldingsOverlayError(f"Invalid decimal for {label}: {value!r}.") from exc


def _scenario_decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ScenarioLabError(f"Invalid decimal for {label}: {value!r}.") from exc


def _json_value(value: object) -> object:
    if isinstance(value, (Decimal, datetime)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value
