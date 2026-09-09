from dataclasses import replace
from datetime import date
from decimal import Decimal

from enam_assessment.analytics import (
    AnalysisConfig,
    ConfidenceLevel,
    analyze_history,
    render_historical_analysis,
)
from enam_assessment.ingestion import IngestionResult, LotClassification, TradeLotRecord


def trade_record(
    *,
    company: str = "Company A",
    purchase_date: date | None = date(2024, 1, 1),
    purchase_quantity: str | None = "10",
    purchase_rate: str | None = "10",
    purchase_amount: str | None = "100",
    sale_date: date | None = date(2024, 6, 1),
    sale_quantity: str | None = "10",
    sale_rate: str | None = "12",
    sale_amount: str | None = "120",
    classification: LotClassification = LotClassification.VALID_REALIZED,
    source_row: int = 4,
) -> TradeLotRecord:
    def decimal_or_none(value: str | None) -> Decimal | None:
        return Decimal(value) if value is not None else None

    return TradeLotRecord(
        company=company,
        purchase_date=purchase_date,
        purchase_quantity=decimal_or_none(purchase_quantity),
        purchase_rate=decimal_or_none(purchase_rate),
        purchase_amount=decimal_or_none(purchase_amount),
        sale_date=sale_date,
        sale_quantity=decimal_or_none(sale_quantity),
        sale_rate=decimal_or_none(sale_rate),
        sale_amount=decimal_or_none(sale_amount),
        classification=classification,
        source_sheet=company,
        source_row=source_row,
        validation_results=(),
    )


def test_pipeline_applies_cutoff_and_classification_boundaries() -> None:
    realized = trade_record()
    open_lot = trade_record(
        purchase_date=date(2025, 1, 1),
        purchase_quantity="20",
        purchase_rate="10",
        purchase_amount="200",
        sale_date=None,
        sale_quantity=None,
        sale_rate=None,
        sale_amount=None,
        classification=LotClassification.PROVISIONALLY_OPEN,
        source_row=5,
    )
    quarantined = replace(
        realized,
        classification=LotClassification.QUARANTINED_INVALID,
        source_row=6,
    )
    structural = replace(
        realized,
        classification=LotClassification.IGNORED_STRUCTURAL,
        source_row=7,
    )
    after_cutoff = replace(
        realized,
        sale_date=date(2025, 12, 13),
        source_row=8,
    )
    after_stated_period = replace(
        realized,
        sale_date=date(2025, 4, 1),
        source_row=9,
    )

    analysis = analyze_history(
        IngestionResult(
            records=(
                after_cutoff,
                structural,
                open_lot,
                quarantined,
                realized,
                after_stated_period,
            )
        ),
        AnalysisConfig(cutoff_date=date(2025, 12, 12)),
    )

    assert analysis.config.cutoff_date == date(2025, 12, 12)
    assert analysis.coverage.input_records == 6
    assert analysis.coverage.realized_lots == 2
    assert analysis.coverage.provisionally_open_lots == 1
    assert analysis.coverage.quarantined_rows == 1
    assert analysis.coverage.structural_rows == 1
    assert analysis.coverage.after_cutoff_rows == 1
    assert analysis.coverage.after_stated_period_rows == 1
    assert analysis.overall_performance.purchase_cost == Decimal("200")
    assert analysis.overall_performance.sale_proceeds == Decimal("240")
    assert analysis.open_cost.total_purchase_cost == Decimal("200")
    assert analysis.open_cost.total_quantity == Decimal("20")
    assert analysis.open_cost.oldest_lot_age_days == 345


def test_pipeline_summarizes_company_sizing_profit_and_open_cost_concentration() -> None:
    records = (
        trade_record(company="Company A", source_row=4),
        trade_record(
            company="Company A",
            purchase_date=date(2025, 1, 1),
            purchase_quantity="20",
            purchase_rate="10",
            purchase_amount="200",
            sale_date=None,
            sale_quantity=None,
            sale_rate=None,
            sale_amount=None,
            classification=LotClassification.PROVISIONALLY_OPEN,
            source_row=5,
        ),
        trade_record(
            company="Company B",
            purchase_quantity="30",
            purchase_rate="10",
            purchase_amount="300",
            sale_quantity="30",
            sale_rate="9",
            sale_amount="270",
            source_row=4,
        ),
        trade_record(
            company="Company B",
            purchase_date=date(2025, 6, 1),
            purchase_amount="100",
            sale_date=None,
            sale_quantity=None,
            sale_rate=None,
            sale_amount=None,
            classification=LotClassification.PROVISIONALLY_OPEN,
            source_row=5,
        ),
    )

    analysis = analyze_history(
        IngestionResult(records=records),
        AnalysisConfig(cutoff_date=date(2025, 12, 12)),
    )

    company = {summary.label: summary for summary in analysis.company_performance}
    assert company["Company A"].net_realized_profit == Decimal("20")
    assert company["Company B"].net_realized_profit == Decimal("-30")
    assert company["Company A"].profit_contribution == Decimal("-2")
    assert company["Company B"].profit_contribution == Decimal("3")

    assert analysis.purchase_sizing.lot_count == 4
    assert analysis.purchase_sizing.median_purchase_lot == Decimal("150")
    assert analysis.purchase_sizing.largest_purchase_lot == Decimal("300")
    assert dict(analysis.purchase_sizing.company_cost_weights) == {
        "Company A": Decimal("3") / Decimal("7"),
        "Company B": Decimal("4") / Decimal("7"),
    }
    assert analysis.purchase_sizing.gross_profit_weights == (("Company A", Decimal("1")),)

    assert dict(analysis.open_cost.company_cost_weights) == {
        "Company A": Decimal("2") / Decimal("3"),
        "Company B": Decimal("1") / Decimal("3"),
    }
    assert analysis.open_cost.hhi == Decimal("5") / Decimal("9")
    assert analysis.open_cost.effective_position_count == Decimal("1.8")


def test_inferred_daily_events_preserve_totals_and_are_order_independent() -> None:
    records = (
        trade_record(
            purchase_date=date(2024, 1, 1),
            purchase_quantity="4",
            purchase_rate="10",
            purchase_amount="40",
            sale_date=date(2024, 6, 1),
            sale_quantity="4",
            sale_rate="12",
            sale_amount="48",
            source_row=4,
        ),
        trade_record(
            purchase_date=date(2024, 1, 1),
            purchase_quantity="6",
            purchase_rate="10",
            purchase_amount="60",
            sale_date=date(2024, 6, 1),
            sale_quantity="6",
            sale_rate="12",
            sale_amount="72",
            source_row=5,
        ),
        trade_record(
            purchase_date=date(2024, 2, 1),
            purchase_quantity="5",
            purchase_rate="9",
            purchase_amount="45",
            sale_date=None,
            sale_quantity=None,
            sale_rate=None,
            sale_amount=None,
            classification=LotClassification.PROVISIONALLY_OPEN,
            source_row=6,
        ),
    )
    config = AnalysisConfig(cutoff_date=date(2025, 12, 12))

    forward = analyze_history(IngestionResult(records=records), config)
    reversed_result = analyze_history(IngestionResult(records=tuple(reversed(records))), config)

    assert forward == reversed_result
    purchase_events = tuple(event for event in forward.inferred_events if event.side == "purchase")
    sale_events = tuple(event for event in forward.inferred_events if event.side == "sale")
    assert [(event.event_date, event.quantity, event.amount) for event in purchase_events] == [
        (date(2024, 1, 1), Decimal("10"), Decimal("100")),
        (date(2024, 2, 1), Decimal("5"), Decimal("45")),
    ]
    assert [(event.event_date, event.quantity, event.amount) for event in sale_events] == [
        (date(2024, 6, 1), Decimal("10"), Decimal("120")),
    ]
    assert sum((event.quantity for event in purchase_events), Decimal("0")) == Decimal("15")
    assert sum((event.amount for event in purchase_events), Decimal("0")) == Decimal("145")

    pattern = forward.trading_patterns[0]
    assert pattern.purchase_event_count == 2
    assert pattern.sale_event_count == 1
    assert pattern.scaling_purchase_events == 1
    assert pattern.later_purchase_lower_rate == 1
    assert pattern.partial_sale_events == 1
    assert pattern.complete_exit_events == 0
    assert pattern.reentry_events == 0


def test_weak_evidence_never_becomes_a_high_confidence_behaviour_claim() -> None:
    records = (
        trade_record(source_row=4),
        trade_record(
            purchase_date=date(2025, 1, 1),
            purchase_amount="100",
            sale_date=None,
            sale_quantity=None,
            sale_rate=None,
            sale_amount=None,
            classification=LotClassification.PROVISIONALLY_OPEN,
            source_row=5,
        ),
    )

    analysis = analyze_history(
        IngestionResult(records=records),
        AnalysisConfig(cutoff_date=date(2025, 12, 12)),
    )

    assert analysis.winner_loser_holding.winner_lots == 1
    assert analysis.winner_loser_holding.loser_lots == 0
    asymmetry = next(
        finding for finding in analysis.behaviour_findings if finding.code == "holding_asymmetry"
    )
    assert asymmetry.confidence is ConfidenceLevel.LOW
    assert "1 winner and 0 loser lots" in asymmetry.evidence
    assert all(
        finding.confidence is not ConfidenceLevel.HIGH for finding in analysis.behaviour_findings
    )
    assert all(finding.counter_evidence for finding in analysis.behaviour_findings)
    assert all(finding.limitation for finding in analysis.behaviour_findings)
    scaling = next(
        finding for finding in analysis.behaviour_findings if finding.code == "inferred_scaling"
    )
    sizing = next(
        finding for finding in analysis.behaviour_findings if finding.code == "purchase_sizing"
    )
    assert scaling.observed_pattern.startswith("No scaling")
    assert "consistent" in sizing.observed_pattern


def test_report_states_cutoff_methodology_and_unavailable_metrics() -> None:
    records = (
        trade_record(source_row=4),
        trade_record(
            purchase_date=date(2025, 1, 1),
            purchase_amount="100",
            sale_date=None,
            sale_quantity=None,
            sale_rate=None,
            sale_amount=None,
            classification=LotClassification.PROVISIONALLY_OPEN,
            source_row=5,
        ),
    )
    analysis = analyze_history(
        IngestionResult(records=records),
        AnalysisConfig(cutoff_date=date(2025, 12, 12)),
    )

    report = render_historical_analysis(analysis)

    assert "Analysis cutoff: **2025-12-12**" in report
    assert "gross, price-only" in report
    assert "## Realized performance" in report
    assert "## Partial open-cost concentration" in report
    assert "No unrealized return is calculated" in report
    assert "S&P BSE 500 TRI" in report
    assert "Inferred daily events are not original broker orders" in report
