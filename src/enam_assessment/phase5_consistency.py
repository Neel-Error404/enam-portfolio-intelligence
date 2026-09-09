"""Narrow consistency checks over frozen Phase 3 and Phase 5 artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .decision_engine import CompanyDecisionSpec
from .errors import DecisionConsistencyError


@dataclass(frozen=True, slots=True)
class HistoricalOpenHolding:
    """Provisional quantity and purchase cost published by Phase 3."""

    company_id: str
    shares: Decimal
    cost_basis: Decimal


_COMPANY_IDS = {
    "Amber Enterprises": "amber",
    "Dilip Buildcon": "dbl",
    "Welspun Living": "welspun",
    "Zee Entertainment Enterprises": "zee",
}


def read_phase3_open_holdings(path: Path) -> dict[str, HistoricalOpenHolding]:
    """Read the frozen Phase 3 open-cost table without reopening the workbook."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise DecisionConsistencyError(f"Cannot read Phase 3 artifact {path}.") from error
    holdings: dict[str, HistoricalOpenHolding] = {}
    for line in lines:
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if len(cells) != 7 or cells[0] not in _COMPANY_IDS:
            continue
        company_id = _COMPANY_IDS[cells[0]]
        try:
            shares = Decimal(cells[2].replace(",", ""))
            cost_basis = Decimal(cells[3].replace(",", ""))
        except InvalidOperation as error:
            raise DecisionConsistencyError(
                f"Invalid Phase 3 holdings values for {company_id} in {path}."
            ) from error
        holdings[company_id] = HistoricalOpenHolding(company_id, shares, cost_basis)
    missing = sorted(set(_COMPANY_IDS.values()) - holdings.keys())
    if missing:
        raise DecisionConsistencyError(
            f"Phase 3 open-cost table is missing companies: {', '.join(missing)}."
        )
    return holdings


def reconcile_working_holdings(
    specs: tuple[CompanyDecisionSpec, ...],
    expected: dict[str, HistoricalOpenHolding],
) -> None:
    """Raise an exact field-level error when Phase 5 working holdings drift."""
    actual = {item.company_id: item for item in specs}
    if set(actual) != set(expected):
        raise DecisionConsistencyError(
            "Working-holdings companies differ between Phase 3 and Phase 5."
        )
    for company_id in sorted(expected):
        reference = expected[company_id]
        spec = actual[company_id]
        for field, expected_value, actual_value in (
            ("working_shares", reference.shares, spec.working_shares),
            ("working_cost_basis", reference.cost_basis, spec.working_cost_basis),
        ):
            if actual_value != expected_value:
                raise DecisionConsistencyError(
                    f"{company_id} {field} does not reconcile: expected {expected_value}, "
                    f"received {actual_value}."
                )
