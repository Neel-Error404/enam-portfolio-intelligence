"""Exact-date market comparisons for accepted realized trade lots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from .errors import MissingEvidenceError, UnsupportedIdentifierError
from .evidence import PriceObservation, match_price_date
from .ingestion import IngestionResult, LotClassification, TradeLotRecord


class ComparisonStatus(StrEnum):
    """Availability of a lot-level market comparison."""

    MATCHED = "matched"
    PARTIAL = "partial"
    UNMATCHED = "unmatched"


@dataclass(frozen=True, slots=True)
class MarketComparison:
    """Stock and benchmark return over one realized lot's exact date interval."""

    company: str
    source_sheet: str
    source_row: int
    purchase_date: date
    sale_date: date
    purchase_cost: Decimal
    stock_return: Decimal | None
    primary_benchmark_return: Decimal | None
    primary_relative_return: Decimal | None
    secondary_benchmark_return: Decimal | None
    secondary_relative_return: Decimal | None
    validation_status: ComparisonStatus
    reason: str


def compare_realized_lots(
    result: IngestionResult,
    *,
    prices: tuple[PriceObservation, ...],
    company_instruments: dict[str, str],
    primary_benchmark_id: str,
    secondary_benchmark_id: str,
    analysis_as_of: date,
) -> tuple[MarketComparison, ...]:
    """Compare valid realized lots using exact trading dates and adjusted closes."""
    eligible = tuple(
        sorted(
            (
                record
                for record in result.records
                if record.classification is LotClassification.VALID_REALIZED
                and record.sale_date is not None
                and record.sale_date <= analysis_as_of
            ),
            key=_lot_key,
        )
    )
    comparisons = tuple(
        _compare_lot(
            record,
            prices=prices,
            instrument_id=_company_instrument(record.company, company_instruments),
            primary_benchmark_id=primary_benchmark_id,
            secondary_benchmark_id=secondary_benchmark_id,
        )
        for record in eligible
    )
    return comparisons


def _company_instrument(company: str, mapping: dict[str, str]) -> str:
    try:
        return mapping[company]
    except KeyError as exc:
        raise UnsupportedIdentifierError(
            f"No verified market identifier is configured for company {company!r}."
        ) from exc


def _compare_lot(
    record: TradeLotRecord,
    *,
    prices: tuple[PriceObservation, ...],
    instrument_id: str,
    primary_benchmark_id: str,
    secondary_benchmark_id: str,
) -> MarketComparison:
    if record.purchase_date is None or record.sale_date is None:
        raise ValueError("Eligible realized lots require purchase and sale dates")
    if record.purchase_amount is None or record.purchase_amount <= 0:
        raise ValueError("Eligible realized lots require a positive purchase amount")
    reasons: list[str] = []
    stock_return = _interval_return(
        prices,
        instrument_id,
        record.purchase_date,
        record.sale_date,
        reasons,
    )
    primary_return = _interval_return(
        prices,
        primary_benchmark_id,
        record.purchase_date,
        record.sale_date,
        reasons,
    )
    secondary_return = _interval_return(
        prices,
        secondary_benchmark_id,
        record.purchase_date,
        record.sale_date,
        reasons,
    )
    if stock_return is None:
        status = ComparisonStatus.UNMATCHED
    elif primary_return is not None and secondary_return is not None:
        status = ComparisonStatus.MATCHED
    else:
        status = ComparisonStatus.PARTIAL
    return MarketComparison(
        company=record.company,
        source_sheet=record.source_sheet,
        source_row=record.source_row,
        purchase_date=record.purchase_date,
        sale_date=record.sale_date,
        purchase_cost=record.purchase_amount,
        stock_return=stock_return,
        primary_benchmark_return=primary_return,
        primary_relative_return=(
            stock_return - primary_return
            if stock_return is not None and primary_return is not None
            else None
        ),
        secondary_benchmark_return=secondary_return,
        secondary_relative_return=(
            stock_return - secondary_return
            if stock_return is not None and secondary_return is not None
            else None
        ),
        validation_status=status,
        reason="; ".join(reasons),
    )


def _interval_return(
    prices: tuple[PriceObservation, ...],
    instrument_id: str,
    start: date,
    end: date,
    reasons: list[str],
) -> Decimal | None:
    try:
        entry = match_price_date(prices, instrument_id=instrument_id, target=start)
        exit_ = match_price_date(prices, instrument_id=instrument_id, target=end)
    except MissingEvidenceError as exc:
        reasons.append(str(exc))
        return None
    entry_value = entry.adjusted_close
    exit_value = exit_.adjusted_close
    if entry_value is None or exit_value is None:
        reasons.append(
            f"Adjusted close is unavailable for {instrument_id!r} over "
            f"{start.isoformat()} to {end.isoformat()}."
        )
        return None
    return (exit_value / entry_value) - Decimal("1")


def _lot_key(record: TradeLotRecord) -> tuple[str, date, date, str, int]:
    if record.purchase_date is None or record.sale_date is None:
        raise ValueError("Eligible realized lots require purchase and sale dates")
    return (
        record.company,
        record.purchase_date,
        record.sale_date,
        record.source_sheet,
        record.source_row,
    )
