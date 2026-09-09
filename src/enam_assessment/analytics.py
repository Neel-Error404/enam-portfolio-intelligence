"""Deterministic historical analytics over normalized trade-lot records."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum
from statistics import mean, median

from .errors import InvalidAnalysisInputError, UnsupportedRecordError
from .ingestion import (
    STATED_PERIOD_END,
    IngestionResult,
    LotClassification,
    TradeLotRecord,
)

HISTORICAL_ANALYSIS_CUTOFF = date(2025, 12, 12)


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    """Explicit, deterministic boundaries for historical analysis."""

    cutoff_date: date = HISTORICAL_ANALYSIS_CUTOFF


class HoldingPeriodBand(StrEnum):
    """Transparent day-based holding-period bands."""

    LESS_THAN_ONE_YEAR = "less_than_one_year"
    ONE_TO_THREE_YEARS = "one_to_three_years"
    THREE_TO_FIVE_YEARS = "three_to_five_years"
    MORE_THAN_FIVE_YEARS = "more_than_five_years"


class ConfidenceLevel(StrEnum):
    """Evidence strength for bounded behavioural interpretations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class RealizedLotMetrics:
    """Calculated gross, price-only metrics for one accepted realized lot."""

    record: TradeLotRecord
    purchase_cost: Decimal
    sale_proceeds: Decimal
    realized_profit: Decimal
    simple_return: Decimal
    holding_days: int
    annualized_return: Decimal | None
    holding_period_band: HoldingPeriodBand


@dataclass(frozen=True, slots=True)
class RealizedPerformanceSummary:
    """Cost-weighted realized performance and lot-level diagnostics."""

    label: str
    realized_lots: int
    purchase_cost: Decimal
    sale_proceeds: Decimal
    net_realized_profit: Decimal
    gross_profits: Decimal
    gross_losses: Decimal
    cost_weighted_return: Decimal
    winning_lots: int
    losing_lots: int
    breakeven_lots: int
    win_rate: Decimal
    mean_lot_return: Decimal
    median_lot_return: Decimal
    mean_holding_days: Decimal
    median_holding_days: Decimal
    profit_contribution: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ConcentrationMetrics:
    """Weights and concentration derived from positive cost-basis values."""

    weights: tuple[tuple[str, Decimal], ...]
    hhi: Decimal
    effective_position_count: Decimal


@dataclass(frozen=True, slots=True)
class HoldingPeriodSummary:
    """Realized performance within one holding-period band."""

    band: HoldingPeriodBand
    eligible_lots: int
    purchase_cost: Decimal
    realized_profit: Decimal
    cost_weighted_return: Decimal | None
    win_rate: Decimal | None
    median_holding_days: Decimal | None


@dataclass(frozen=True, slots=True)
class AnalysisCoverage:
    """Counts of included and excluded normalized source records."""

    input_records: int
    realized_lots: int
    provisionally_open_lots: int
    quarantined_rows: int
    structural_rows: int
    after_cutoff_rows: int
    after_stated_period_rows: int


@dataclass(frozen=True, slots=True)
class OpenCostAnalysis:
    """Partial cost-basis facts for provisionally open lots."""

    lot_count: int
    total_quantity: Decimal
    total_purchase_cost: Decimal
    median_lot_age_days: Decimal
    oldest_lot_age_days: int
    company_cost_weights: tuple[tuple[str, Decimal], ...]
    hhi: Decimal
    effective_position_count: Decimal
    company_summaries: tuple[OpenCompanySummary, ...]


@dataclass(frozen=True, slots=True)
class OpenCompanySummary:
    """Quantity, purchase cost, and age for one company's provisional open lots."""

    company: str
    lot_count: int
    quantity: Decimal
    purchase_cost: Decimal
    median_age_days: Decimal
    oldest_lot_age_days: int


@dataclass(frozen=True, slots=True)
class PurchaseSizingAnalysis:
    """Accepted purchase-lot sizes and cost-basis concentration."""

    lot_count: int
    total_purchase_cost: Decimal
    median_purchase_lot: Decimal
    largest_purchase_lot: Decimal
    company_cost_weights: tuple[tuple[str, Decimal], ...]
    gross_profit_weights: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True, slots=True)
class InferredEvent:
    """Daily grouped fragments; not an asserted original broker order."""

    company: str
    side: str
    event_date: date
    quantity: Decimal
    amount: Decimal
    weighted_rate: Decimal
    source_rows: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class TradingPatternSummary:
    """Conservative event-pattern counts for one company."""

    company: str
    purchase_event_count: int
    sale_event_count: int
    scaling_purchase_events: int
    later_purchase_higher_rate: int
    later_purchase_lower_rate: int
    later_purchase_equal_rate: int
    partial_sale_events: int
    complete_exit_events: int
    reentry_events: int
    ambiguous_same_day_events: int
    quantity_break_events: int


@dataclass(frozen=True, slots=True)
class WinnerLoserHoldingComparison:
    """Holding-duration comparison without a psychological diagnosis."""

    winner_lots: int
    loser_lots: int
    mean_winner_holding_days: Decimal | None
    median_winner_holding_days: Decimal | None
    mean_loser_holding_days: Decimal | None
    median_loser_holding_days: Decimal | None


@dataclass(frozen=True, slots=True)
class BehaviourFinding:
    """An evidence-bounded historical pattern with counter-evidence and caveat."""

    code: str
    observed_pattern: str
    evidence: str
    counter_evidence: str
    confidence: ConfidenceLevel
    limitation: str


@dataclass(frozen=True, slots=True)
class HistoricalAnalysis:
    """Deterministic historical analysis derived only from normalized records."""

    config: AnalysisConfig
    coverage: AnalysisCoverage
    realized_lots: tuple[RealizedLotMetrics, ...]
    overall_performance: RealizedPerformanceSummary
    company_performance: tuple[RealizedPerformanceSummary, ...]
    holding_periods: tuple[HoldingPeriodSummary, ...]
    purchase_sizing: PurchaseSizingAnalysis
    open_cost: OpenCostAnalysis
    inferred_events: tuple[InferredEvent, ...]
    trading_patterns: tuple[TradingPatternSummary, ...]
    winner_loser_holding: WinnerLoserHoldingComparison
    behaviour_findings: tuple[BehaviourFinding, ...]


def calculate_realized_lot(record: TradeLotRecord) -> RealizedLotMetrics:
    """Calculate metrics for a complete normalized realized lot."""
    if record.classification is not LotClassification.VALID_REALIZED:
        raise UnsupportedRecordError("Realized-lot calculations require a valid realized record.")
    if (
        record.purchase_date is None
        or record.sale_date is None
        or record.purchase_quantity is None
        or record.sale_quantity is None
        or record.purchase_amount is None
        or record.sale_amount is None
    ):
        raise UnsupportedRecordError(
            "A realized record requires purchase and sale dates, quantities, and amounts."
        )
    if record.purchase_quantity != record.sale_quantity:
        raise UnsupportedRecordError(
            "Realized-lot calculations require equal purchase and sale quantities."
        )
    if record.purchase_amount <= 0:
        raise InvalidAnalysisInputError("Realized purchase amount must be greater than zero.")
    if record.sale_amount <= 0:
        raise InvalidAnalysisInputError("Realized sale amount must be greater than zero.")

    holding_days = (record.sale_date - record.purchase_date).days
    if holding_days < 0:
        raise InvalidAnalysisInputError("Realized holding days cannot be negative.")
    simple_return = (record.sale_amount / record.purchase_amount) - Decimal("1")
    annualized_return = simple_return if holding_days == 365 else None
    if holding_days > 365:
        annualized_return = (
            (record.sale_amount / record.purchase_amount)
            ** (Decimal("365") / Decimal(holding_days))
        ) - Decimal("1")
    return RealizedLotMetrics(
        record=record,
        purchase_cost=record.purchase_amount,
        sale_proceeds=record.sale_amount,
        realized_profit=record.sale_amount - record.purchase_amount,
        simple_return=simple_return,
        holding_days=holding_days,
        annualized_return=annualized_return,
        holding_period_band=holding_period_band(holding_days),
    )


def holding_period_band(holding_days: int) -> HoldingPeriodBand:
    """Map a non-negative holding period to a documented day-based band."""
    if holding_days < 0:
        raise InvalidAnalysisInputError("Holding days cannot be negative.")
    if holding_days < 365:
        return HoldingPeriodBand.LESS_THAN_ONE_YEAR
    if holding_days < 1_095:
        return HoldingPeriodBand.ONE_TO_THREE_YEARS
    if holding_days <= 1_825:
        return HoldingPeriodBand.THREE_TO_FIVE_YEARS
    return HoldingPeriodBand.MORE_THAN_FIVE_YEARS


def summarize_realized_lots(
    metrics: tuple[RealizedLotMetrics, ...], *, label: str
) -> RealizedPerformanceSummary:
    """Aggregate realized lots without using an unweighted headline return."""
    if not metrics:
        raise ValueError("At least one realized lot is required for a performance summary.")

    purchase_cost = sum(
        (metric.purchase_cost for metric in metrics),
        start=Decimal("0"),
    )
    sale_proceeds = sum(
        (metric.sale_proceeds for metric in metrics),
        start=Decimal("0"),
    )
    if purchase_cost <= 0:
        raise ValueError("Realized purchase cost must be greater than zero.")

    profits = tuple(metric.realized_profit for metric in metrics)
    returns = tuple(metric.simple_return for metric in metrics)
    holding_days = tuple(Decimal(metric.holding_days) for metric in metrics)
    winning_lots = sum(profit > 0 for profit in profits)
    losing_lots = sum(profit < 0 for profit in profits)
    breakeven_lots = len(metrics) - winning_lots - losing_lots
    net_profit = sum(profits, start=Decimal("0"))

    return RealizedPerformanceSummary(
        label=label,
        realized_lots=len(metrics),
        purchase_cost=purchase_cost,
        sale_proceeds=sale_proceeds,
        net_realized_profit=net_profit,
        gross_profits=sum((profit for profit in profits if profit > 0), start=Decimal("0")),
        gross_losses=sum((-profit for profit in profits if profit < 0), start=Decimal("0")),
        cost_weighted_return=calculate_cost_weighted_return(net_profit, purchase_cost),
        winning_lots=winning_lots,
        losing_lots=losing_lots,
        breakeven_lots=breakeven_lots,
        win_rate=Decimal(winning_lots) / Decimal(len(metrics)),
        mean_lot_return=mean(returns),
        median_lot_return=median(returns),
        mean_holding_days=mean(holding_days),
        median_holding_days=median(holding_days),
    )


def calculate_cost_weighted_return(net_profit: Decimal, purchase_cost: Decimal) -> Decimal:
    """Return aggregate profit divided by aggregate purchase cost."""
    if purchase_cost <= 0:
        raise InvalidAnalysisInputError("Total purchase cost must be greater than zero.")
    return net_profit / purchase_cost


def calculate_profit_contribution(
    company_net_profit: Decimal, total_net_profit: Decimal
) -> Decimal:
    """Return a company's signed contribution to the overall net realized result."""
    if total_net_profit == 0:
        raise InvalidAnalysisInputError(
            "Profit contribution is undefined because total net profit is zero."
        )
    return company_net_profit / total_net_profit


def calculate_concentration(costs: dict[str, Decimal]) -> ConcentrationMetrics:
    """Calculate sorted cost weights, HHI, and effective position count."""
    if not costs or any(value <= 0 for value in costs.values()):
        raise InvalidAnalysisInputError(
            "Concentration requires one or more strictly positive values."
        )
    total = sum(costs.values(), start=Decimal("0"))
    weights = tuple(sorted((label, value / total) for label, value in costs.items()))
    hhi = sum((weight * weight for _, weight in weights), start=Decimal("0"))
    return ConcentrationMetrics(
        weights=weights,
        hhi=hhi,
        effective_position_count=Decimal("1") / hhi,
    )


def summarize_holding_periods(
    metrics: tuple[RealizedLotMetrics, ...],
) -> tuple[HoldingPeriodSummary, ...]:
    """Summarize all declared bands, leaving empty-band ratios unavailable."""
    summaries: list[HoldingPeriodSummary] = []
    for band in HoldingPeriodBand:
        eligible = tuple(metric for metric in metrics if metric.holding_period_band is band)
        purchase_cost = sum((metric.purchase_cost for metric in eligible), start=Decimal("0"))
        realized_profit = sum((metric.realized_profit for metric in eligible), start=Decimal("0"))
        wins = sum(metric.realized_profit > 0 for metric in eligible)
        summaries.append(
            HoldingPeriodSummary(
                band=band,
                eligible_lots=len(eligible),
                purchase_cost=purchase_cost,
                realized_profit=realized_profit,
                cost_weighted_return=(
                    calculate_cost_weighted_return(realized_profit, purchase_cost)
                    if eligible
                    else None
                ),
                win_rate=(Decimal(wins) / Decimal(len(eligible)) if eligible else None),
                median_holding_days=(
                    median(tuple(Decimal(metric.holding_days) for metric in eligible))
                    if eligible
                    else None
                ),
            )
        )
    return tuple(summaries)


def analyze_history(result: IngestionResult, config: AnalysisConfig) -> HistoricalAnalysis:
    """Analyze accepted normalized lots at or before the configured cutoff."""
    quarantined_rows = sum(
        record.classification is LotClassification.QUARANTINED_INVALID for record in result.records
    )
    structural_rows = sum(
        record.classification is LotClassification.IGNORED_STRUCTURAL for record in result.records
    )
    accepted = tuple(
        sorted(
            (
                record
                for record in result.records
                if record.classification
                in {
                    LotClassification.VALID_REALIZED,
                    LotClassification.PROVISIONALLY_OPEN,
                }
                and not _is_after_cutoff(record, config.cutoff_date)
            ),
            key=_record_sort_key,
        )
    )
    after_cutoff_rows = sum(
        record.classification
        in {LotClassification.VALID_REALIZED, LotClassification.PROVISIONALLY_OPEN}
        and _is_after_cutoff(record, config.cutoff_date)
        for record in result.records
    )
    after_stated_period_rows = sum(
        _is_after_cutoff(record, STATED_PERIOD_END) for record in accepted
    )
    realized_records = tuple(
        record for record in accepted if record.classification is LotClassification.VALID_REALIZED
    )
    open_records = tuple(
        record
        for record in accepted
        if record.classification is LotClassification.PROVISIONALLY_OPEN
    )
    realized_metrics = tuple(calculate_realized_lot(record) for record in realized_records)

    overall_performance = summarize_realized_lots(realized_metrics, label="Overall")
    company_metrics = {
        company: tuple(metric for metric in realized_metrics if metric.record.company == company)
        for company in sorted({metric.record.company for metric in realized_metrics})
    }
    company_performance = tuple(
        replace(
            summarize_realized_lots(metrics, label=company),
            profit_contribution=(
                calculate_profit_contribution(
                    sum(
                        (metric.realized_profit for metric in metrics),
                        start=Decimal("0"),
                    ),
                    overall_performance.net_realized_profit,
                )
                if overall_performance.net_realized_profit != 0
                else None
            ),
        )
        for company, metrics in company_metrics.items()
    )

    accepted_costs_by_company: dict[str, Decimal] = {}
    accepted_purchase_costs: list[Decimal] = []
    for record in accepted:
        purchase_amount = _required_purchase_amount(record)
        accepted_purchase_costs.append(purchase_amount)
        accepted_costs_by_company[record.company] = (
            accepted_costs_by_company.get(record.company, Decimal("0")) + purchase_amount
        )
    accepted_concentration = calculate_concentration(accepted_costs_by_company)

    positive_profit_by_company = {
        summary.label: summary.gross_profits
        for summary in company_performance
        if summary.gross_profits > 0
    }
    gross_profit_weights = (
        calculate_concentration(positive_profit_by_company).weights
        if positive_profit_by_company
        else ()
    )

    open_quantities: list[Decimal] = []
    open_costs: list[Decimal] = []
    open_ages: list[Decimal] = []
    open_records_by_company: dict[str, list[TradeLotRecord]] = {}
    for record in open_records:
        if (
            record.purchase_date is None
            or record.purchase_quantity is None
            or record.purchase_amount is None
        ):
            raise UnsupportedRecordError(
                "Provisionally open analysis requires purchase date, quantity, and amount."
            )
        open_quantities.append(record.purchase_quantity)
        open_costs.append(record.purchase_amount)
        open_ages.append(Decimal((config.cutoff_date - record.purchase_date).days))
        open_records_by_company.setdefault(record.company, []).append(record)

    if not open_ages:
        raise UnsupportedRecordError(
            "Historical analysis requires at least one provisionally open lot."
        )

    open_company_summaries: list[OpenCompanySummary] = []
    open_costs_by_company: dict[str, Decimal] = {}
    for company, company_records in sorted(open_records_by_company.items()):
        quantities = tuple(_required_purchase_quantity(record) for record in company_records)
        costs = tuple(_required_purchase_amount(record) for record in company_records)
        ages = tuple(
            Decimal((config.cutoff_date - _required_purchase_date(record)).days)
            for record in company_records
        )
        company_cost = sum(costs, start=Decimal("0"))
        open_costs_by_company[company] = company_cost
        open_company_summaries.append(
            OpenCompanySummary(
                company=company,
                lot_count=len(company_records),
                quantity=sum(quantities, start=Decimal("0")),
                purchase_cost=company_cost,
                median_age_days=median(ages),
                oldest_lot_age_days=int(max(ages)),
            )
        )
    open_concentration = calculate_concentration(open_costs_by_company)
    inferred_events = infer_daily_events(accepted)

    purchase_sizing = PurchaseSizingAnalysis(
        lot_count=len(accepted),
        total_purchase_cost=sum(accepted_purchase_costs, start=Decimal("0")),
        median_purchase_lot=median(accepted_purchase_costs),
        largest_purchase_lot=max(accepted_purchase_costs),
        company_cost_weights=accepted_concentration.weights,
        gross_profit_weights=gross_profit_weights,
    )
    open_cost = OpenCostAnalysis(
        lot_count=len(open_records),
        total_quantity=sum(open_quantities, start=Decimal("0")),
        total_purchase_cost=sum(open_costs, start=Decimal("0")),
        median_lot_age_days=median(open_ages),
        oldest_lot_age_days=int(max(open_ages)),
        company_cost_weights=open_concentration.weights,
        hhi=open_concentration.hhi,
        effective_position_count=open_concentration.effective_position_count,
        company_summaries=tuple(open_company_summaries),
    )
    trading_patterns = summarize_trading_patterns(inferred_events)
    winner_loser_holding = compare_winner_loser_holding(realized_metrics)

    return HistoricalAnalysis(
        config=config,
        coverage=AnalysisCoverage(
            input_records=len(result.records),
            realized_lots=len(realized_records),
            provisionally_open_lots=len(open_records),
            quarantined_rows=quarantined_rows,
            structural_rows=structural_rows,
            after_cutoff_rows=after_cutoff_rows,
            after_stated_period_rows=after_stated_period_rows,
        ),
        realized_lots=realized_metrics,
        overall_performance=overall_performance,
        company_performance=company_performance,
        holding_periods=summarize_holding_periods(realized_metrics),
        purchase_sizing=purchase_sizing,
        open_cost=open_cost,
        inferred_events=inferred_events,
        trading_patterns=trading_patterns,
        winner_loser_holding=winner_loser_holding,
        behaviour_findings=_build_behaviour_findings(
            winner_loser_holding,
            purchase_sizing,
            open_cost,
            trading_patterns,
        ),
    )


def _is_after_cutoff(record: TradeLotRecord, cutoff_date: date) -> bool:
    return any(
        transaction_date is not None and transaction_date > cutoff_date
        for transaction_date in (record.purchase_date, record.sale_date)
    )


def _record_sort_key(record: TradeLotRecord) -> tuple[str, date, date, str, int]:
    return (
        record.company,
        record.purchase_date or date.min,
        record.sale_date or date.max,
        record.source_sheet,
        record.source_row,
    )


def _required_purchase_amount(record: TradeLotRecord) -> Decimal:
    if record.purchase_amount is None or record.purchase_amount <= 0:
        raise UnsupportedRecordError(
            "Accepted purchase-cost analysis requires a positive purchase amount."
        )
    return record.purchase_amount


def _required_purchase_quantity(record: TradeLotRecord) -> Decimal:
    if record.purchase_quantity is None or record.purchase_quantity <= 0:
        raise UnsupportedRecordError("Open-cost analysis requires a positive purchase quantity.")
    return record.purchase_quantity


def _required_purchase_date(record: TradeLotRecord) -> date:
    if record.purchase_date is None:
        raise UnsupportedRecordError("Open-cost analysis requires a purchase date.")
    return record.purchase_date


def infer_daily_events(records: tuple[TradeLotRecord, ...]) -> tuple[InferredEvent, ...]:
    """Group accepted FIFO fragments by company, side, and date without double-counting."""
    grouped: dict[tuple[str, str, date], list[tuple[Decimal, Decimal, tuple[str, int]]]] = {}
    for record in records:
        purchase_date = _required_purchase_date(record)
        purchase_quantity = _required_purchase_quantity(record)
        purchase_amount = _required_purchase_amount(record)
        grouped.setdefault((record.company, "purchase", purchase_date), []).append(
            (purchase_quantity, purchase_amount, (record.source_sheet, record.source_row))
        )

        if record.classification is LotClassification.VALID_REALIZED:
            if (
                record.sale_date is None
                or record.sale_quantity is None
                or record.sale_amount is None
            ):
                raise UnsupportedRecordError(
                    "Inferred sale events require sale date, quantity, and amount."
                )
            grouped.setdefault((record.company, "sale", record.sale_date), []).append(
                (
                    record.sale_quantity,
                    record.sale_amount,
                    (record.source_sheet, record.source_row),
                )
            )

    events: list[InferredEvent] = []
    for (company, side, event_date), fragments in sorted(grouped.items()):
        quantity = sum((fragment[0] for fragment in fragments), start=Decimal("0"))
        amount = sum((fragment[1] for fragment in fragments), start=Decimal("0"))
        if quantity <= 0:
            raise InvalidAnalysisInputError("Inferred event quantity must be greater than zero.")
        events.append(
            InferredEvent(
                company=company,
                side=side,
                event_date=event_date,
                quantity=quantity,
                amount=amount,
                weighted_rate=amount / quantity,
                source_rows=tuple(sorted(fragment[2] for fragment in fragments)),
            )
        )
    return tuple(events)


def summarize_trading_patterns(
    events: tuple[InferredEvent, ...],
) -> tuple[TradingPatternSummary, ...]:
    """Infer bounded pattern counts from daily events without asserting order-level intent."""
    summaries: list[TradingPatternSummary] = []
    companies = sorted({event.company for event in events})
    for company in companies:
        company_events = tuple(event for event in events if event.company == company)
        purchase_events = tuple(event for event in company_events if event.side == "purchase")
        sale_events = tuple(event for event in company_events if event.side == "sale")
        events_by_date = {
            event_date: tuple(event for event in company_events if event.event_date == event_date)
            for event_date in sorted({event.event_date for event in company_events})
        }

        balance = Decimal("0")
        last_purchase_rate: Decimal | None = None
        ever_exited = False
        scaling = higher = lower = equal = 0
        partial_sales = complete_exits = reentries = ambiguous = quantity_breaks = 0

        for daily_events in events_by_date.values():
            purchase = next((event for event in daily_events if event.side == "purchase"), None)
            sale = next((event for event in daily_events if event.side == "sale"), None)
            if purchase is not None and sale is not None:
                ambiguous += 1
                balance += purchase.quantity - sale.quantity
                if balance < 0:
                    quantity_breaks += 1
                last_purchase_rate = purchase.weighted_rate
                continue

            if purchase is not None:
                if balance > 0:
                    scaling += 1
                    if last_purchase_rate is not None:
                        if purchase.weighted_rate > last_purchase_rate:
                            higher += 1
                        elif purchase.weighted_rate < last_purchase_rate:
                            lower += 1
                        else:
                            equal += 1
                elif ever_exited:
                    reentries += 1
                balance += purchase.quantity
                last_purchase_rate = purchase.weighted_rate
                continue

            if sale is not None:
                if sale.quantity < balance:
                    partial_sales += 1
                elif sale.quantity == balance:
                    complete_exits += 1
                    ever_exited = True
                else:
                    quantity_breaks += 1
                balance -= sale.quantity

        summaries.append(
            TradingPatternSummary(
                company=company,
                purchase_event_count=len(purchase_events),
                sale_event_count=len(sale_events),
                scaling_purchase_events=scaling,
                later_purchase_higher_rate=higher,
                later_purchase_lower_rate=lower,
                later_purchase_equal_rate=equal,
                partial_sale_events=partial_sales,
                complete_exit_events=complete_exits,
                reentry_events=reentries,
                ambiguous_same_day_events=ambiguous,
                quantity_break_events=quantity_breaks,
            )
        )
    return tuple(summaries)


def compare_winner_loser_holding(
    metrics: tuple[RealizedLotMetrics, ...],
) -> WinnerLoserHoldingComparison:
    """Compare profitable and loss-making holding durations; omit breakeven lots."""
    winner_days = tuple(
        Decimal(metric.holding_days) for metric in metrics if metric.realized_profit > 0
    )
    loser_days = tuple(
        Decimal(metric.holding_days) for metric in metrics if metric.realized_profit < 0
    )
    return WinnerLoserHoldingComparison(
        winner_lots=len(winner_days),
        loser_lots=len(loser_days),
        mean_winner_holding_days=mean(winner_days) if winner_days else None,
        median_winner_holding_days=median(winner_days) if winner_days else None,
        mean_loser_holding_days=mean(loser_days) if loser_days else None,
        median_loser_holding_days=median(loser_days) if loser_days else None,
    )


def _build_behaviour_findings(
    holding: WinnerLoserHoldingComparison,
    sizing: PurchaseSizingAnalysis,
    open_cost: OpenCostAnalysis,
    patterns: tuple[TradingPatternSummary, ...],
) -> tuple[BehaviourFinding, ...]:
    if (
        holding.median_winner_holding_days is not None
        and holding.median_loser_holding_days is not None
    ):
        difference = holding.median_loser_holding_days - holding.median_winner_holding_days
        if difference > 0:
            holding_pattern = (
                "Loss-making realized lots were held longer at the median than winning lots."
            )
        elif difference < 0:
            holding_pattern = (
                "Loss-making realized lots were held shorter at the median than winning lots."
            )
        else:
            holding_pattern = (
                "Winning and loss-making realized lots had the same median holding period."
            )
        holding_counter = (
            "Mean holding durations and company mix may differ from the median comparison."
        )
    else:
        holding_pattern = "Winner-versus-loser holding asymmetry is unavailable."
        holding_counter = "At least one outcome group has no eligible realized lots."
    holding_confidence = (
        ConfidenceLevel.MEDIUM
        if min(holding.winner_lots, holding.loser_lots) >= 10
        else ConfidenceLevel.LOW
    )
    holding_finding = BehaviourFinding(
        code="holding_asymmetry",
        observed_pattern=holding_pattern,
        evidence=(
            f"Eligible sample: {holding.winner_lots} winner and {holding.loser_lots} loser lots."
        ),
        counter_evidence=holding_counter,
        confidence=holding_confidence,
        limitation=(
            "Without contemporaneous values for sold and retained positions, this is not a "
            "formal disposition-effect test."
        ),
    )

    top_company, top_weight = max(open_cost.company_cost_weights, key=lambda item: item[1])
    concentration_finding = BehaviourFinding(
        code="open_cost_concentration",
        observed_pattern=(f"Provisional open purchase cost is most concentrated in {top_company}."),
        evidence=(
            f"{open_cost.lot_count} provisional lots; top cost share {_percent(top_weight)}; "
            f"HHI {_decimal_text(open_cost.hhi)}; effective positions "
            f"{_decimal_text(open_cost.effective_position_count)}."
        ),
        counter_evidence=(
            f"Other companies account for {_percent(Decimal('1') - top_weight)} of provisional "
            "open cost."
        ),
        confidence=(ConfidenceLevel.MEDIUM if open_cost.lot_count >= 20 else ConfidenceLevel.LOW),
        limitation=(
            "This is partial cost-basis concentration, not current portfolio weight; cash, "
            "other securities, current prices, and complete NAV are unknown."
        ),
    )

    lot_ratio = sizing.largest_purchase_lot / sizing.median_purchase_lot
    sizing_pattern = (
        "Accepted purchase-lot sizes are consistent at the median and maximum."
        if lot_ratio == 1
        else "Accepted purchase-lot sizes are not uniform."
    )
    sizing_finding = BehaviourFinding(
        code="purchase_sizing",
        observed_pattern=sizing_pattern,
        evidence=(
            f"{sizing.lot_count} accepted lots; largest purchase cost is "
            f"{_decimal_text(lot_ratio)} times the median."
        ),
        counter_evidence="FIFO fragmentation can make lot-size dispersion differ from order size.",
        confidence=(ConfidenceLevel.MEDIUM if sizing.lot_count >= 20 else ConfidenceLevel.LOW),
        limitation="Matched lot fragments are not original broker orders.",
    )

    scaling_count = sum(pattern.scaling_purchase_events for pattern in patterns)
    higher_count = sum(pattern.later_purchase_higher_rate for pattern in patterns)
    lower_count = sum(pattern.later_purchase_lower_rate for pattern in patterns)
    ambiguous_count = sum(pattern.ambiguous_same_day_events for pattern in patterns)
    scaling_pattern = (
        "Daily grouped records suggest repeated scaling while positions were open."
        if scaling_count
        else "No scaling purchase days were inferred from the daily grouped records."
    )
    scaling_finding = BehaviourFinding(
        code="inferred_scaling",
        observed_pattern=scaling_pattern,
        evidence=(
            f"{scaling_count} inferred scaling purchase days: {higher_count} at a higher and "
            f"{lower_count} at a lower weighted rate than the preceding purchase day."
        ),
        counter_evidence=f"{ambiguous_count} dates contain both inferred purchases and sales.",
        confidence=ConfidenceLevel.LOW,
        limitation=(
            "Daily groups merge FIFO fragments and may combine multiple orders; intent such as "
            "averaging down cannot be established."
        ),
    )
    return holding_finding, concentration_finding, sizing_finding, scaling_finding


def _percent(value: Decimal) -> str:
    return f"{value * Decimal('100'):.1f}%"


def _decimal_text(value: Decimal) -> str:
    return f"{value:.2f}"


def render_historical_analysis(analysis: HistoricalAnalysis) -> str:
    """Render the deterministic analysis as a self-contained Markdown report."""
    coverage = analysis.coverage
    overall = analysis.overall_performance
    lines = [
        "# Historical Performance and Investor-Behaviour Analysis",
        "",
        f"Analysis cutoff: **{analysis.config.cutoff_date.isoformat()}**.",
        "",
        (
            "Results use only normalized `IngestionResult` records. They are gross, price-only "
            "results before fees, taxes, dividends, and corporate actions. Transactions after "
            "the workbook's stated 2025-03-31 endpoint are retained through the declared cutoff."
        ),
        "",
        "## Coverage and exclusions",
        "",
        (
            "| Input records | Realized lots | Provisional open lots | Quarantined | "
            "Structural | After stated period | After cutoff |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {coverage.input_records} | {coverage.realized_lots} | "
            f"{coverage.provisionally_open_lots} | {coverage.quarantined_rows} | "
            f"{coverage.structural_rows} | {coverage.after_stated_period_rows} | "
            f"{coverage.after_cutoff_rows} |"
        ),
        "",
        (
            "Quarantined, structural, and post-cutoff records are excluded from every calculation. "
            "Provisional open lots are excluded from realized-return calculations."
        ),
        "",
        "## Methodology",
        "",
        "- Lot profit = sale amount minus purchase amount.",
        "- Lot simple return = sale amount divided by purchase amount, minus one.",
        (
            "- Headline cost-weighted return = total net realized profit divided by total "
            "realized purchase cost."
        ),
        "- Annualized return is calculated only at 365 holding days or longer as "
        "`(sale amount / purchase amount)^(365 / holding days) - 1`.",
        (
            "- Gross profits sum positive lot profits; gross losses are the positive magnitude "
            "of negative lot profits."
        ),
        (
            "- Win rate divides winning lots by all eligible realized lots, including breakeven "
            "lots in the denominator."
        ),
        (
            "- Profit contribution = company net realized profit divided by overall net realized "
            "profit; it is unavailable when overall net profit is zero."
        ),
        "- Holding bands use days: `<365`, `365-1094`, `1095-1825`, and `>1825`.",
        "",
        "## Realized performance",
        "",
        (
            "| Scope | Lots | Purchase cost | Sale proceeds | Net profit | Gross profits | "
            "Gross losses | Cost-weighted return | W/L/B | Win rate | Mean lot return | "
            "Median lot return | Mean days | Median days | Profit contribution |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        _performance_row(overall),
    ]
    lines.extend(
        _performance_row(company_summary) for company_summary in analysis.company_performance
    )

    lines.extend(
        [
            "",
            (
                "The cost-weighted return is the headline realized-return measure. Mean and "
                "median lot returns are shown only as lot-level diagnostics."
            ),
            "",
            "## Holding-period results",
            "",
            (
                "| Band | Lots | Purchase cost | Realized profit | Cost-weighted return | "
                "Win rate | Median days |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for band_summary in analysis.holding_periods:
        lines.append(
            f"| {_holding_band_label(band_summary.band)} | {band_summary.eligible_lots} | "
            f"{_money(band_summary.purchase_cost)} | "
            f"{_money(band_summary.realized_profit)} | "
            f"{_optional_percent(band_summary.cost_weighted_return)} | "
            f"{_optional_percent(band_summary.win_rate)} | "
            f"{_optional_decimal(band_summary.median_holding_days)} |"
        )

    holding = analysis.winner_loser_holding
    lines.extend(
        [
            "",
            "### Winners versus losers",
            "",
            "| Outcome | Lots | Mean holding days | Median holding days |",
            "|---|---:|---:|---:|",
            f"| Winners | {holding.winner_lots} | "
            f"{_optional_decimal(holding.mean_winner_holding_days)} | "
            f"{_optional_decimal(holding.median_winner_holding_days)} |",
            f"| Losers | {holding.loser_lots} | "
            f"{_optional_decimal(holding.mean_loser_holding_days)} | "
            f"{_optional_decimal(holding.median_loser_holding_days)} |",
            "",
            (
                "This comparison can show holding asymmetry, but it is not a formal disposition-"
                "effect test because contemporaneous values of sold and retained positions are "
                "unavailable."
            ),
            "",
            "## Position sizing and concentration",
            "",
            f"- Accepted purchase lots: {analysis.purchase_sizing.lot_count}",
            f"- Accepted purchase cost: {_money(analysis.purchase_sizing.total_purchase_cost)}",
            f"- Median purchase-lot cost: {_money(analysis.purchase_sizing.median_purchase_lot)}",
            f"- Largest purchase-lot cost: {_money(analysis.purchase_sizing.largest_purchase_lot)}",
            "",
            "| Company | Accepted purchase-cost share | Gross-positive-profit share |",
            "|---|---:|---:|",
        ]
    )
    gross_profit_weights = dict(analysis.purchase_sizing.gross_profit_weights)
    for company, weight in analysis.purchase_sizing.company_cost_weights:
        lines.append(
            f"| {company} | {_percent(weight)} | "
            f"{_optional_percent(gross_profit_weights.get(company))} |"
        )

    lines.extend(
        [
            "",
            "## Partial open-cost concentration",
            "",
            (
                "Open lots are provisional rather than verified current holdings. No unrealized "
                "return is calculated without a dated market price."
            ),
            "",
            (
                "| Company | Lots | Quantity | Purchase cost | Open-cost share | Median age days | "
                "Oldest age days |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    open_weights = dict(analysis.open_cost.company_cost_weights)
    for open_summary in analysis.open_cost.company_summaries:
        lines.append(
            f"| {open_summary.company} | {open_summary.lot_count} | "
            f"{_quantity(open_summary.quantity)} | {_money(open_summary.purchase_cost)} | "
            f"{_percent(open_weights[open_summary.company])} | "
            f"{_decimal_text(open_summary.median_age_days)} | "
            f"{open_summary.oldest_lot_age_days} |"
        )
    lines.extend(
        [
            "",
            (
                f"Open-cost HHI: **{_decimal_text(analysis.open_cost.hhi)}**. Effective number of "
                "cost-basis positions: "
                f"**{_decimal_text(analysis.open_cost.effective_position_count)}**."
            ),
            (
                "These are partial cost-basis measures, not complete or market-value portfolio "
                "weights."
            ),
            "",
            "## Inferred trading patterns",
            "",
            (
                "Inferred daily events are not original broker orders. All accepted FIFO fragments "
                "with the same company, side, and date are grouped; quantity and amount are summed "
                "once and the event rate is amount divided by quantity. Dates containing both "
                "sides are treated as sequence-ambiguous."
            ),
            "",
            (
                "| Company | Purchase days | Sale days | Scaling buys | Higher-rate | Lower-rate | "
                "Partial sales | Complete exits | Re-entries | Same-day ambiguous | "
                "Quantity breaks |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for pattern in analysis.trading_patterns:
        lines.append(
            f"| {pattern.company} | {pattern.purchase_event_count} | "
            f"{pattern.sale_event_count} | {pattern.scaling_purchase_events} | "
            f"{pattern.later_purchase_higher_rate} | {pattern.later_purchase_lower_rate} | "
            f"{pattern.partial_sale_events} | {pattern.complete_exit_events} | "
            f"{pattern.reentry_events} | {pattern.ambiguous_same_day_events} | "
            f"{pattern.quantity_break_events} |"
        )

    lines.extend(["", "## Evidence-backed behaviour findings", ""])
    for finding in analysis.behaviour_findings:
        lines.extend(
            [
                (
                    f"### {finding.code.replace('_', ' ').title()} — "
                    f"{finding.confidence.value} confidence"
                ),
                "",
                f"- Observed pattern: {finding.observed_pattern}",
                f"- Evidence: {finding.evidence}",
                f"- Counter-evidence: {finding.counter_evidence}",
                f"- Limitation: {finding.limitation}",
                "",
            ]
        )

    lines.extend(
        [
            "## Metrics not supported by this dataset",
            "",
            (
                "Portfolio NAV return, drawdown, Sharpe ratio, XIRR, complete attribution, "
                "current market-value weights, unrealized returns, formal disposition effect, "
                "premature selling, market-timing skill, alpha, and benchmark outperformance are "
                "not calculated."
            ),
            "",
            (
                "The workbook lacks complete cash balances, other securities, dated market "
                "values, fees, taxes, dividends, corporate actions, and original execution/order "
                "history."
            ),
            "",
            "## Deferred benchmark and point-in-time questions",
            "",
            "- Primary future benchmark: S&P BSE 500 TRI.",
            "- Secondary cross-check: NIFTY 500 TRI.",
            (
                "- Obtain dated benchmark and security-price histories before measuring relative "
                "returns or post-sale outcomes."
            ),
            (
                "- Establish point-in-time corporate-action, dividend, fee, tax, cash, and "
                "portfolio-universe treatment before broader attribution."
            ),
            "- Do not use the supplied 2026 analyst reports to explain historical transactions.",
            "",
        ]
    )
    return "\n".join(lines)


def _performance_row(summary: RealizedPerformanceSummary) -> str:
    return (
        f"| {summary.label} | {summary.realized_lots} | {_money(summary.purchase_cost)} | "
        f"{_money(summary.sale_proceeds)} | {_money(summary.net_realized_profit)} | "
        f"{_money(summary.gross_profits)} | {_money(summary.gross_losses)} | "
        f"{_percent(summary.cost_weighted_return)} | "
        f"{summary.winning_lots}/{summary.losing_lots}/{summary.breakeven_lots} | "
        f"{_percent(summary.win_rate)} | {_percent(summary.mean_lot_return)} | "
        f"{_percent(summary.median_lot_return)} | {_decimal_text(summary.mean_holding_days)} | "
        f"{_decimal_text(summary.median_holding_days)} | "
        f"{_optional_percent(summary.profit_contribution)} |"
    )


def _holding_band_label(band: HoldingPeriodBand) -> str:
    return {
        HoldingPeriodBand.LESS_THAN_ONE_YEAR: "Less than one year",
        HoldingPeriodBand.ONE_TO_THREE_YEARS: "One to three years",
        HoldingPeriodBand.THREE_TO_FIVE_YEARS: "Three to five years",
        HoldingPeriodBand.MORE_THAN_FIVE_YEARS: "More than five years",
    }[band]


def _money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    return "0.00" if rounded == 0 else f"{rounded:,.2f}"


def _quantity(value: Decimal) -> str:
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def _optional_percent(value: Decimal | None) -> str:
    return "n/a" if value is None else _percent(value)


def _optional_decimal(value: Decimal | None) -> str:
    return "n/a" if value is None else _decimal_text(value)
