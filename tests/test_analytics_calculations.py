from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from enam_assessment.analytics import (
    HoldingPeriodBand,
    calculate_concentration,
    calculate_cost_weighted_return,
    calculate_profit_contribution,
    calculate_realized_lot,
    holding_period_band,
    summarize_holding_periods,
    summarize_realized_lots,
)
from enam_assessment.errors import InvalidAnalysisInputError, UnsupportedRecordError
from enam_assessment.ingestion import LotClassification, TradeLotRecord


def realized_record(
    *,
    purchase_date: date,
    sale_date: date,
    purchase_amount: str,
    sale_amount: str,
) -> TradeLotRecord:
    quantity = Decimal("10")
    return TradeLotRecord(
        company="Example Company",
        purchase_date=purchase_date,
        purchase_quantity=quantity,
        purchase_rate=Decimal(purchase_amount) / quantity,
        purchase_amount=Decimal(purchase_amount),
        sale_date=sale_date,
        sale_quantity=quantity,
        sale_rate=Decimal(sale_amount) / quantity,
        sale_amount=Decimal(sale_amount),
        classification=LotClassification.VALID_REALIZED,
        source_sheet="Example",
        source_row=4,
        validation_results=(),
    )


def test_calculates_realized_lot_and_annualizes_only_from_one_year() -> None:
    one_year = calculate_realized_lot(
        realized_record(
            purchase_date=date(2023, 1, 1),
            sale_date=date(2024, 1, 1),
            purchase_amount="1000",
            sale_amount="1210",
        )
    )
    short = calculate_realized_lot(
        realized_record(
            purchase_date=date(2023, 1, 2),
            sale_date=date(2024, 1, 1),
            purchase_amount="1000",
            sale_amount="1100",
        )
    )

    assert one_year.realized_profit == Decimal("210")
    assert one_year.simple_return == Decimal("0.21")
    assert one_year.holding_days == 365
    assert one_year.holding_period_band is HoldingPeriodBand.ONE_TO_THREE_YEARS
    assert one_year.annualized_return == Decimal("0.21")

    assert short.holding_days == 364
    assert short.holding_period_band is HoldingPeriodBand.LESS_THAN_ONE_YEAR
    assert short.annualized_return is None


def test_summarizes_realized_lots_with_cost_weighted_headline_return() -> None:
    metrics = tuple(
        calculate_realized_lot(record)
        for record in (
            realized_record(
                purchase_date=date(2023, 1, 1),
                sale_date=date(2024, 1, 1),
                purchase_amount="1000",
                sale_amount="1200",
            ),
            realized_record(
                purchase_date=date(2023, 1, 1),
                sale_date=date(2023, 4, 11),
                purchase_amount="2000",
                sale_amount="1500",
            ),
            realized_record(
                purchase_date=date(2023, 1, 1),
                sale_date=date(2023, 1, 11),
                purchase_amount="500",
                sale_amount="500",
            ),
        )
    )

    summary = summarize_realized_lots(metrics, label="Overall")

    assert summary.purchase_cost == Decimal("3500")
    assert summary.sale_proceeds == Decimal("3200")
    assert summary.net_realized_profit == Decimal("-300")
    assert summary.gross_profits == Decimal("200")
    assert summary.gross_losses == Decimal("500")
    assert summary.cost_weighted_return == Decimal("-300") / Decimal("3500")
    assert summary.winning_lots == 1
    assert summary.losing_lots == 1
    assert summary.breakeven_lots == 1
    assert summary.win_rate == Decimal("1") / Decimal("3")
    assert summary.mean_lot_return == Decimal("-0.05") / Decimal("3")
    assert summary.median_lot_return == Decimal("0")
    assert summary.mean_holding_days == Decimal("475") / Decimal("3")
    assert summary.median_holding_days == Decimal("100")


def test_holding_period_bands_have_explicit_day_boundaries() -> None:
    assert holding_period_band(364) is HoldingPeriodBand.LESS_THAN_ONE_YEAR
    assert holding_period_band(365) is HoldingPeriodBand.ONE_TO_THREE_YEARS
    assert holding_period_band(1_094) is HoldingPeriodBand.ONE_TO_THREE_YEARS
    assert holding_period_band(1_095) is HoldingPeriodBand.THREE_TO_FIVE_YEARS
    assert holding_period_band(1_825) is HoldingPeriodBand.THREE_TO_FIVE_YEARS
    assert holding_period_band(1_826) is HoldingPeriodBand.MORE_THAN_FIVE_YEARS

    with pytest.raises(InvalidAnalysisInputError, match="cannot be negative"):
        holding_period_band(-1)


def test_contribution_and_concentration_handle_positive_negative_and_zero_totals() -> None:
    assert calculate_profit_contribution(Decimal("300"), Decimal("600")) == Decimal("0.5")
    assert calculate_profit_contribution(Decimal("-600"), Decimal("-1000")) == Decimal("0.6")
    assert calculate_profit_contribution(Decimal("200"), Decimal("-1000")) == Decimal("-0.2")

    with pytest.raises(InvalidAnalysisInputError, match="total net profit is zero"):
        calculate_profit_contribution(Decimal("1"), Decimal("0"))
    with pytest.raises(InvalidAnalysisInputError, match="purchase cost must be greater"):
        calculate_cost_weighted_return(Decimal("1"), Decimal("0"))

    concentration = calculate_concentration(
        {"Company B": Decimal("400"), "Company A": Decimal("600")}
    )
    assert concentration.weights == (
        ("Company A", Decimal("0.6")),
        ("Company B", Decimal("0.4")),
    )
    assert concentration.hhi == Decimal("0.52")
    assert concentration.effective_position_count == Decimal("1") / Decimal("0.52")

    with pytest.raises(InvalidAnalysisInputError, match="positive values"):
        calculate_concentration({"Company A": Decimal("0")})


def test_realized_calculation_rejects_unsupported_records_and_denominators() -> None:
    valid = realized_record(
        purchase_date=date(2024, 1, 1),
        sale_date=date(2024, 2, 1),
        purchase_amount="1000",
        sale_amount="1100",
    )

    with pytest.raises(UnsupportedRecordError, match="valid realized"):
        calculate_realized_lot(replace(valid, classification=LotClassification.PROVISIONALLY_OPEN))
    with pytest.raises(UnsupportedRecordError, match="equal purchase and sale quantities"):
        calculate_realized_lot(replace(valid, sale_quantity=Decimal("9")))
    with pytest.raises(InvalidAnalysisInputError, match="purchase amount must be greater"):
        calculate_realized_lot(replace(valid, purchase_amount=Decimal("0")))


def test_summarizes_each_holding_period_band_without_inventing_empty_metrics() -> None:
    metrics = tuple(
        calculate_realized_lot(record)
        for record in (
            realized_record(
                purchase_date=date(2024, 1, 1),
                sale_date=date(2024, 1, 11),
                purchase_amount="100",
                sale_amount="110",
            ),
            realized_record(
                purchase_date=date(2024, 1, 1),
                sale_date=date(2024, 4, 10),
                purchase_amount="200",
                sale_amount="150",
            ),
            realized_record(
                purchase_date=date(2023, 1, 1),
                sale_date=date(2024, 1, 1),
                purchase_amount="100",
                sale_amount="120",
            ),
        )
    )

    summaries = {summary.band: summary for summary in summarize_holding_periods(metrics)}
    short = summaries[HoldingPeriodBand.LESS_THAN_ONE_YEAR]
    assert short.eligible_lots == 2
    assert short.purchase_cost == Decimal("300")
    assert short.realized_profit == Decimal("-40")
    assert short.cost_weighted_return == Decimal("-40") / Decimal("300")
    assert short.win_rate == Decimal("0.5")
    assert short.median_holding_days == Decimal("55")

    empty = summaries[HoldingPeriodBand.MORE_THAN_FIVE_YEARS]
    assert empty.eligible_lots == 0
    assert empty.purchase_cost == Decimal("0")
    assert empty.cost_weighted_return is None
    assert empty.win_rate is None
    assert empty.median_holding_days is None
