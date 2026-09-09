"""Build the Phase 5 decision snapshot and recommendation report offline."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from enam_assessment.decision_engine import (
    CompanyDecisionSnapshot,
    PortfolioDecisionSnapshot,
    build_decisions,
    load_decision_configuration,
    write_decision_snapshot,
)
from enam_assessment.evidence import EvidenceSnapshot
from enam_assessment.evidence_io import read_snapshot
from enam_assessment.phase5_consistency import (
    read_phase3_open_holdings,
    reconcile_working_holdings,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "evidence" / "normalized_snapshot.json"
HISTORICAL_PATH = ROOT / "evidence" / "historical_comparisons.json"
CONFIG_PATH = ROOT / "config" / "decision_engine.json"
OUTPUT_PATH = ROOT / "decision" / "decision_snapshot.json"
REPORT_PATH = ROOT / "docs" / "CURRENT_RECOMMENDATIONS.md"
HISTORICAL_REPORT_PATH = ROOT / "docs" / "HISTORICAL_ANALYSIS.md"

COMPANY_IDS = {
    "Amber Enterprises": "amber",
    "Dilip Buildcon": "dbl",
    "Welspun Living": "welspun",
    "Zee Entertainment Enterprises": "zee",
}


def main() -> None:
    """Read frozen artifacts, build decisions, and persist deterministic outputs."""
    evidence = read_snapshot(EVIDENCE_PATH)
    config, specs = load_decision_configuration(CONFIG_PATH)
    reconcile_working_holdings(specs, read_phase3_open_holdings(HISTORICAL_REPORT_PATH))
    historical_context = _historical_context(HISTORICAL_PATH)
    result = build_decisions(evidence, specs, config, historical_context=historical_context)
    write_decision_snapshot(result, OUTPUT_PATH)
    REPORT_PATH.write_text(render_recommendations(result, evidence), encoding="utf-8")
    print(f"decision_snapshot_sha256={result.snapshot_sha256}")
    print(f"wrote={OUTPUT_PATH.relative_to(ROOT)}")
    print(f"wrote={REPORT_PATH.relative_to(ROOT)}")


def _historical_context(path: Path) -> dict[str, dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        COMPANY_IDS[item["company"]]: item
        for item in raw["summary"]
        if item["company"] in COMPANY_IDS
    }


def render_recommendations(result: PortfolioDecisionSnapshot, evidence: EvidenceSnapshot) -> str:
    """Render the complete human-readable decision artifact."""
    descriptions = _evidence_descriptions(evidence)
    lines = [
        "# Current Recommendations",
        "",
        f"Decision date: **{result.decision_date.isoformat()}**  ",
        f"Evidence manifest SHA-256: `{result.evidence_manifest_sha256}`  ",
        f"Decision snapshot SHA-256: `{result.snapshot_sha256}`  ",
        f"Engine/configuration: `{result.engine_version}` / `{result.configuration_version}`",
        "",
        "> **Working-holdings warning:** " + result.provisional_holdings_warning,
        "",
        "These are deterministic assessment outputs, not trade instructions. A final action of "
        "REVIEW_REQUIRED means a person must resolve the stated approval or evidence issue.",
        "",
        "## Decision summary",
        "",
        "| Company | Stance | Final action | Score | Current | Target | Bear value/CAGR | "
        "Base value/CAGR | Bull value/CAGR |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for company in result.companies:
        scenarios = {item.input.name: item for item in company.scenarios}
        lines.append(
            f"| {company.company_name} | {company.underlying_stance.value.upper()} | "
            f"{company.final_action.value.upper()} | {_score(company.weighted_principle_score)} | "
            f"{_pct(company.working_current_weight)} | {_pct(company.target_weight)} | "
            f"{_money(scenarios['bear'].target_price)} / {_pct(scenarios['bear'].price_cagr)} | "
            f"{_money(scenarios['base'].target_price)} / {_pct(scenarios['base'].price_cagr)} | "
            f"{_money(scenarios['bull'].target_price)} / {_pct(scenarios['bull'].price_cagr)} |"
        )

    lines.extend(
        [
            "",
            "## Working portfolio",
            "",
            f"The four provisional open-lot positions have an approximate market value of "
            f"INR {_money(sum(item.approximate_market_value for item in result.companies))}. "
            f"The proposed assessment sleeve retains {_pct(result.cash_target_weight)} cash.",
            "",
            "| Metric | Current working sleeve | Target risky sleeve |",
            "|---|---:|---:|",
            _portfolio_metric_row(result, "Largest name", "largest_weight"),
            _portfolio_metric_row(result, "Top two", "top_two_weight"),
            _portfolio_metric_row(result, "Top three", "top_three_weight"),
            _portfolio_metric_row(result, "HHI", "hhi", percent=False),
            _portfolio_metric_row(
                result, "Effective positions", "effective_positions", percent=False
            ),
            "",
            f"Target bear-case portfolio-at-risk is {_pct(result.target_bear_portfolio_at_risk)} "
            "of the represented sleeve. It is the sum of each absolute target weight times that "
            "company's bear-case downside; it is not VaR and excludes cash and "
            "unrepresented assets.",
            "",
            "Current concentration breaches the prototype review conventions: "
            + ", ".join(result.current_concentration.review_reasons)
            + ". Target risky-capital concentration is shown conditional on invested capital; "
            "the large cash allocation is reported separately.",
            "",
            "## Benchmark context",
            "",
            f"The intended primary benchmark `{result.primary_benchmark_id}` remains "
            f"**{result.primary_benchmark_status}**. `{result.secondary_benchmark_id}` is "
            f"**{result.secondary_benchmark_status}**. The NIFTY comparison below is historical "
            "context only and does not enter any gate, score, scenario, target, stance, or action.",
        ]
    )
    for company in result.companies:
        context = company.historical_benchmark_context
        relative = context.get("cost_weighted_secondary_relative_return")
        matched = context.get("secondary_benchmark_matched_lots")
        eligible = context.get("eligible_lots")
        lines.append(
            f"- {company.company_name}: NIFTY 500 TRI matched-period relative return "
            f"{_pct(Decimal(str(relative))) if relative is not None else 'unavailable'} "
            f"across {matched}/{eligible} eligible realized lots."
        )

    for company in result.companies:
        lines.extend(_company_section(company, descriptions))

    lines.extend(
        [
            "",
            "## Limitations and approval boundary",
            "",
            "- Provisional open lots are not verified current holdings. Current values, weights, "
            "and all material rebalances require owner confirmation.",
            "- The scenario model is a relative operating-value sensitivity, not an independent "
            "absolute valuation. It assumes a stable share translation and uses explicit multiple "
            "and equity-bridge factors instead of inventing missing diluted share counts.",
            "- Scenario assumptions are prototype judgments, not facts or analyst targets. Bear, "
            "base, and bull cases are not probability-weighted.",
            "- Price history is provider-adjusted and corporate actions were not independently "
            "reconstructed. The primary BSE TRI series remains unavailable.",
            "- The four-company sleeve omits cash balances, other securities, liabilities, taxes, "
            "fees, dividends, and complete NAV. Target cash is a model residual, not a verified "
            "account balance.",
            "- No recommendation uses evidence after 2026-09-08, an LLM, live network data, or "
            "the historical benchmark result as a scoring input.",
            "",
        ]
    )
    return "\n".join(lines)


def _company_section(company: CompanyDecisionSnapshot, descriptions: dict[str, str]) -> list[str]:
    scenarios = {item.input.name: item for item in company.scenarios}
    strongest = max(
        (score for score in company.principle_scores if score.score is not None),
        key=lambda item: item.score or Decimal("0"),
    )
    weakest = min(
        (score for score in company.principle_scores if score.score is not None),
        key=lambda item: item.score or Decimal("0"),
    )
    counter_ids = weakest.counter_evidence_ids or weakest.evidence_ids
    lines = [
        "",
        f"## {company.company_name}",
        "",
        f"**{company.underlying_stance.value.upper()} / "
        f"{company.final_action.value.upper()} final action.** Current price INR "
        f"{_money(company.current_price)} on {company.price_date.isoformat()} "
        f"({company.price_age_days} days old); working shares "
        f"{_decimal(company.working_shares, 3)}, "
        f"cost basis INR {_money(company.working_cost_basis)}, approximate market value INR "
        f"{_money(company.approximate_market_value)}, current weight "
        f"{_pct(company.working_current_weight)}, and target {_pct(company.target_weight)}.",
        "",
        f"The weighted principle score is {_score(company.weighted_principle_score)} / 5. "
        f"Bear/base/bull targets are INR {_money(scenarios['bear'].target_price)}, "
        f"INR {_money(scenarios['base'].target_price)}, and "
        f"INR {_money(scenarios['bull'].target_price)}, with three-year CAGRs of "
        f"{_pct(scenarios['bear'].price_cagr)}, {_pct(scenarios['base'].price_cagr)}, "
        f"and {_pct(scenarios['bull'].price_cagr)}.",
        "",
        "### Hard gates",
        "",
        "| Gate | Status | Consequence | Explanation | Evidence |",
        "|---|---|---|---|---|",
    ]
    for gate in company.gates:
        lines.append(
            f"| `{gate.code}` | {gate.status.value} | {gate.consequence.value} | "
            f"{gate.explanation} | {', '.join(f'`{item}`' for item in gate.evidence_ids)} |"
        )
    lines.extend(
        [
            "",
            "### Principle scores",
            "",
            "| Dimension | Weight | Score | Quality | Rule |",
            "|---|---:|---:|---|---|",
        ]
    )
    for score in company.principle_scores:
        lines.append(
            f"| {score.dimension.replace('_', ' ')} | {_pct(score.weight)} | "
            f"{_score(score.score)} | {score.data_quality.value} | {score.rule} |"
        )
    lines.extend(
        [
            "",
            f"**Strongest support ({strongest.dimension.replace('_', ' ')}):** "
            + "; ".join(descriptions[item] for item in strongest.evidence_ids),
            "",
            f"**Strongest counter-evidence ({weakest.dimension.replace('_', ' ')}):** "
            + "; ".join(descriptions[item] for item in counter_ids),
            "",
            "**Warnings:** "
            + (
                "; ".join(company.human_review_reasons)
                if company.human_review_reasons
                else "No portfolio approval overlay triggered."
            ),
            "",
            "**What would change the result:** " + "; ".join(company.change_triggers) + ".",
            "",
            "**Missing information:** "
            + ("; ".join(company.missing_data_flags) if company.missing_data_flags else "none")
            + ".",
            "",
            "**Cited evidence and availability dates:** "
            + "; ".join(
                f"`{evidence_id}` ({available.isoformat()})"
                for evidence_id, available in company.evidence_dates
            )
            + ".",
        ]
    )
    return lines


def _evidence_descriptions(snapshot: EvidenceSnapshot) -> dict[str, str]:
    result = {
        item.evidence_id: f"{item.metric_name} {item.value} {item.unit} (`{item.evidence_id}`)"
        for item in snapshot.fundamentals
    }
    result.update(
        {item.evidence_id: f"{item.claim} (`{item.evidence_id}`)" for item in snapshot.research}
    )
    result.update(
        {
            item.evidence_id: (
                f"adjusted close {item.adjusted_close or item.close} (`{item.evidence_id}`)"
            )
            for item in snapshot.prices
        }
    )
    return result


def _target_metric(result: PortfolioDecisionSnapshot, field: str, *, percent: bool = True) -> str:
    if result.target_concentration is None:
        return "n/a"
    value = getattr(result.target_concentration, field)
    return _pct(value) if percent else _decimal(value, 3 if field == "hhi" else 2)


def _portfolio_metric_row(
    result: PortfolioDecisionSnapshot,
    label: str,
    field: str,
    *,
    percent: bool = True,
) -> str:
    current_value = getattr(result.current_concentration, field)
    places = 3 if field == "hhi" else 2
    current = _pct(current_value) if percent else _decimal(current_value, places)
    target = _target_metric(result, field, percent=percent)
    return f"| {label} | {current} | {target} |"


def _pct(value: Decimal) -> str:
    return f"{value * 100:.1f}%"


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def _decimal(value: Decimal, places: int) -> str:
    return f"{value:,.{places}f}"


def _score(value: Decimal | None) -> str:
    return "unavailable" if value is None else f"{value:.2f}"


if __name__ == "__main__":
    main()
