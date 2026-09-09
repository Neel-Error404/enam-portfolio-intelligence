from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from enam_assessment.evidence import CorporateActionStatus, PriceObservation
from enam_assessment.ingestion import IngestionResult, LotClassification, TradeLotRecord
from enam_assessment.market_analysis import compare_realized_lots

RETRIEVED_AT = datetime(2026, 9, 8, tzinfo=UTC)


def lot(*, row: int = 4, sale_date: date = date(2024, 2, 1)) -> TradeLotRecord:
    return TradeLotRecord(
        company="Amber",
        purchase_date=date(2024, 1, 2),
        purchase_quantity=Decimal("10"),
        purchase_rate=Decimal("100"),
        purchase_amount=Decimal("1000"),
        sale_date=sale_date,
        sale_quantity=Decimal("10"),
        sale_rate=Decimal("120"),
        sale_amount=Decimal("1200"),
        classification=LotClassification.VALID_REALIZED,
        source_sheet="Amber",
        source_row=row,
        validation_results=(),
    )


def price(instrument: str, on: date, value: str) -> PriceObservation:
    number = Decimal(value)
    return PriceObservation(
        evidence_id=f"price-{instrument}-{on.isoformat()}",
        instrument_id=instrument,
        trading_date=on,
        open=number,
        high=number,
        low=number,
        close=number,
        adjusted_close=number,
        volume=Decimal("100"),
        corporate_action_status=(
            CorporateActionStatus.NOT_APPLICABLE
            if instrument.endswith("tri")
            else CorporateActionStatus.ADJUSTED_BY_SOURCE
        ),
        source_id="fixture",
        retrieval_timestamp=RETRIEVED_AT,
    )


def test_market_comparison_uses_only_realized_pre_cutoff_lots_and_is_deterministic() -> None:
    realized = lot()
    open_lot = replace(
        realized,
        sale_date=None,
        sale_quantity=None,
        sale_rate=None,
        sale_amount=None,
        classification=LotClassification.PROVISIONALLY_OPEN,
        source_row=5,
    )
    after_cutoff = lot(row=6, sale_date=date(2026, 9, 9))
    observations = (
        price("amber", date(2024, 2, 1), "120"),
        price("nifty-500-tri", date(2024, 2, 1), "1100"),
        price("bse-500-tri", date(2024, 1, 2), "2000"),
        price("amber", date(2024, 1, 2), "100"),
        price("nifty-500-tri", date(2024, 1, 2), "1000"),
        price("bse-500-tri", date(2024, 2, 1), "2300"),
    )
    first = compare_realized_lots(
        IngestionResult(records=(after_cutoff, open_lot, realized)),
        prices=observations,
        company_instruments={"Amber": "amber"},
        primary_benchmark_id="bse-500-tri",
        secondary_benchmark_id="nifty-500-tri",
        analysis_as_of=date(2026, 9, 8),
    )
    second = compare_realized_lots(
        IngestionResult(records=(realized, after_cutoff, open_lot)),
        prices=tuple(reversed(observations)),
        company_instruments={"Amber": "amber"},
        primary_benchmark_id="bse-500-tri",
        secondary_benchmark_id="nifty-500-tri",
        analysis_as_of=date(2026, 9, 8),
    )

    assert first == second
    assert len(first) == 1
    assert first[0].stock_return == Decimal("0.2")
    assert first[0].primary_benchmark_return == Decimal("0.15")
    assert first[0].primary_relative_return == Decimal("0.05")
    assert first[0].secondary_benchmark_return == Decimal("0.1")
    assert first[0].secondary_relative_return == Decimal("0.1")


def test_market_comparison_marks_unknown_gaps_unmatched_without_future_fill() -> None:
    comparison = compare_realized_lots(
        IngestionResult(records=(lot(),)),
        prices=(
            price("amber", date(2024, 1, 3), "101"),
            price("amber", date(2024, 2, 1), "120"),
        ),
        company_instruments={"Amber": "amber"},
        primary_benchmark_id="bse-500-tri",
        secondary_benchmark_id="nifty-500-tri",
        analysis_as_of=date(2026, 9, 8),
    )[0]

    assert comparison.stock_return is None
    assert comparison.primary_benchmark_return is None
    assert comparison.secondary_benchmark_return is None
    assert comparison.validation_status == "unmatched"
    assert "2024-01-02" in comparison.reason
