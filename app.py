"""Local Streamlit entry point for the Portfolio Intelligence application."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import cast

import streamlit as st

from enam_assessment.errors import UIArtifactError
from enam_assessment.memo import MEMO_SECTION_NAMES, MemoClaim
from enam_assessment.memo_generation import MemoStatus
from enam_assessment.portfolio_ui import (
    DashboardData,
    allocation_rows,
    company_snapshot_payload,
    format_date,
    format_inr,
    format_percentage,
    load_dashboard_data,
    memo_state_presentation,
    ordered_scenarios,
)

ROOT = Path(__file__).resolve().parent
VIEWS = ("Investor Behaviour", "Current Portfolio", "Company Intelligence", "Assumptions & Audit")


@st.cache_data
def _load_data() -> DashboardData:
    return load_dashboard_data(ROOT)


def main() -> None:
    st.set_page_config(
        page_title="Portfolio Intelligence",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="auto",
    )
    _styles()
    try:
        data = _load_data()
    except UIArtifactError as exc:
        st.error(f"Portfolio artifacts could not be loaded: {exc}")
        st.stop()

    with st.sidebar:
        st.markdown('<p class="brand-mark">PORTFOLIO INTELLIGENCE</p>', unsafe_allow_html=True)
        st.caption("Decision support · evidence first")
        requested_view = st.query_params.get("view", VIEWS[0])
        view_index = VIEWS.index(requested_view) if requested_view in VIEWS else 0
        view = st.radio("Workspace", VIEWS, index=view_index, label_visibility="collapsed")
        if view != requested_view:
            st.query_params["view"] = view
        st.divider()
        st.caption("Frozen local snapshot")
        st.code(str(data.portfolio["snapshot_sha256"]), language=None)

    _header(data)
    if view == "Investor Behaviour":
        _investor_behaviour(data)
    elif view == "Current Portfolio":
        _current_portfolio(data)
    elif view == "Company Intelligence":
        _company_intelligence(data)
    else:
        _assumptions_and_audit(data)


def _header(data: DashboardData) -> None:
    generated = sum(memo.status is MemoStatus.GENERATED for memo in data.memos)
    review_count = sum(item.human_review_required for item in data.decisions)
    st.markdown('<p class="eyebrow">DECISION SUPPORT · FROZEN SNAPSHOT</p>', unsafe_allow_html=True)
    st.title("Portfolio Intelligence")
    st.markdown(
        "A clear view of historical behaviour, current exposure, company evidence, and "
        "deterministic portfolio decisions."
    )
    cols = st.columns(4)
    cols[0].metric("Decision date", format_date(str(data.portfolio["decision_date"])))
    cols[1].metric("Companies", str(len(data.decisions)))
    cols[2].metric("Human review", f"{review_count} required")
    cols[3].metric("Validated memos", f"{generated} of {len(data.memos)}")
    st.warning(
        "Provisional holdings · " + str(data.portfolio["provisional_holdings_warning"]),
        icon="⚠️",
    )


def _investor_behaviour(data: DashboardData) -> None:
    st.header("Investor Behaviour")
    st.caption("What the accepted FIFO-matched lots show through 12 December 2025.")
    historical = data.historical
    realized = _records(historical, "realized_performance")
    overall = realized[0]
    coverage = _mapping(historical["coverage"], "coverage")
    sizing = _mapping(historical["purchase_sizing"], "purchase sizing")
    metrics = st.columns(4)
    metrics[0].metric("Realized net profit", format_inr(str(overall["net_profit"])))
    metrics[1].metric(
        "Cost-weighted return", format_percentage(str(overall["cost_weighted_return"]))
    )
    metrics[2].metric("Win rate", format_percentage(str(overall["win_rate"])))
    metrics[3].metric("Accepted lots", f"{int(str(sizing['accepted_lots'])):,}")

    st.subheader("Where realized results came from")
    company_realized = [item for item in realized if item["company_id"] != "overall"]
    st.bar_chart(
        {
            "Company": [str(item["company"]) for item in company_realized],
            "Profit contribution (%)": [
                float(Decimal(str(item["profit_contribution"])) * 100) for item in company_realized
            ],
        },
        x="Company",
        y="Profit contribution (%)",
        horizontal=True,
        color="#0f766e",
    )
    st.dataframe(
        [
            {
                "Company": item["company"],
                "Lots": item["lots"],
                "Purchase cost": format_inr(str(item["purchase_cost"])),
                "Net profit": format_inr(str(item["net_profit"])),
                "Cost-weighted return": format_percentage(str(item["cost_weighted_return"])),
                "Win rate": format_percentage(str(item["win_rate"])),
            }
            for item in company_realized
        ],
        hide_index=True,
        width="stretch",
    )

    left, right = st.columns((1.15, 0.85))
    with left:
        st.subheader("Holding period")
        periods = _records(historical, "holding_periods")
        st.bar_chart(
            {
                "Band": [str(item["band"]) for item in periods],
                "Realized return (%)": [
                    float(Decimal(str(item["cost_weighted_return"])) * 100) for item in periods
                ],
            },
            x="Band",
            y="Realized return (%)",
            color="#0f766e",
        )
        st.caption(
            "Winners: 807 median holding days · Losers: 446.5 days. This is holding "
            "asymmetry, not proof of a disposition effect."
        )
    with right:
        st.subheader("Sizing & open-cost concentration")
        open_cost = _mapping(historical["open_cost"], "open cost")
        st.metric("Median accepted lot", format_inr(str(sizing["median_purchase_lot_cost"])))
        st.metric("Largest accepted lot", format_inr(str(sizing["largest_purchase_lot_cost"])))
        st.metric("Open-cost HHI", str(open_cost["hhi"]))
        st.metric("Effective positions", str(open_cost["effective_positions"]))
        st.caption("Partial cost-basis concentration—not complete market-value portfolio weights.")
        open_companies = cast(list[dict[str, object]], open_cost["companies"])
        st.bar_chart(
            {
                "Company": [str(item["company"]) for item in open_companies],
                "Open-cost share (%)": [
                    float(Decimal(str(item["share"])) * 100) for item in open_companies
                ],
            },
            x="Company",
            y="Open-cost share (%)",
            horizontal=True,
            color="#b7791f",
        )

    st.subheader("Observed patterns")
    for finding in _records(historical, "findings"):
        with st.expander(f"{finding['title']} · {str(finding['confidence']).upper()} confidence"):
            st.write(str(finding["observed"]))
            st.markdown(f"**Evidence:** {finding['evidence']}")
            st.markdown(f"**Counter-evidence:** {finding['counter_evidence']}")
            st.caption(str(finding["limitation"]))

    st.subheader("Historical benchmark context")
    st.dataframe(
        [
            {
                "Company": decision.company_name,
                "NIFTY matched lots": decision.historical_benchmark_context.get(
                    "secondary_benchmark_matched_lots", 0
                ),
                "Eligible lots": decision.historical_benchmark_context.get("eligible_lots", 0),
                "Relative return": (
                    format_percentage(
                        str(
                            decision.historical_benchmark_context[
                                "cost_weighted_secondary_relative_return"
                            ]
                        )
                    )
                    if decision.historical_benchmark_context.get(
                        "cost_weighted_secondary_relative_return"
                    )
                    is not None
                    else "Unavailable"
                ),
            }
            for decision in data.decisions
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "S&P BSE 500 TRI remains unavailable. NIFTY 500 TRI is a secondary historical "
        "cross-check and does not drive current decisions."
    )

    with st.expander("Inferred scaling, trimming, exits and re-entry"):
        st.dataframe(_records(historical, "trading_patterns"), hide_index=True)
        st.caption(
            "Daily groups merge FIFO fragments. They are not original broker orders and cannot "
            "establish averaging, trimming, re-entry, or thesis intent with high confidence."
        )
    st.info(
        f"Coverage: {coverage['realized_lots']} realized, "
        f"{coverage['provisional_open_lots']} provisional open, "
        f"{coverage['quarantined']} quarantined, and {coverage['structural']} structural rows."
    )
    for limitation in cast(list[object], historical["limitations"]):
        st.caption(f"• {limitation}")


def _current_portfolio(data: DashboardData) -> None:
    st.header("Current Portfolio")
    st.caption("Working exposure from provisional open lots, valued at the frozen decision prices.")
    rows = allocation_rows(data)
    company_values = [company_snapshot_payload(data, row.company_id) for row in rows]
    total_value = sum(
        (Decimal(str(item["approximate_market_value"])) for item in company_values), Decimal("0")
    )
    current_concentration = _mapping(
        data.portfolio["current_concentration"], "current concentration"
    )
    metrics = st.columns(4)
    metrics[0].metric("Represented sleeve", format_inr(total_value))
    metrics[1].metric("Target cash", format_percentage(str(data.portfolio["cash_target_weight"])))
    metrics[2].metric("Current HHI", f"{Decimal(str(current_concentration['hhi'])):.3f}")
    metrics[3].metric(
        "Effective positions", f"{Decimal(str(current_concentration['effective_positions'])):.2f}"
    )

    st.subheader("Current versus target allocation")
    st.bar_chart(
        {
            "Company": [row.company_name for row in rows],
            "Current (%)": [float(row.current_weight * 100) for row in rows],
            "Target (%)": [float(row.target_weight * 100) for row in rows],
        },
        x="Company",
        y=["Current (%)", "Target (%)"],
        horizontal=True,
        color=["#1f3a5f", "#0f766e"],
    )
    st.dataframe(
        [
            {
                "Company": row.company_name,
                "Current": format_percentage(row.current_weight),
                "Target": format_percentage(row.target_weight),
                "Stance": row.underlying_stance.upper(),
                "Portfolio action": row.final_action.upper(),
                "Approval": "Required" if row.human_review_required else "Not required",
                "Bear risk": format_percentage(row.bear_portfolio_at_risk),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )

    concentration_cols = st.columns(4)
    concentration_cols[0].metric(
        "Largest name", format_percentage(str(current_concentration["largest_weight"]))
    )
    concentration_cols[1].metric(
        "Top two", format_percentage(str(current_concentration["top_two_weight"]))
    )
    concentration_cols[2].metric(
        "Top three", format_percentage(str(current_concentration["top_three_weight"]))
    )
    concentration_cols[3].metric(
        "Target bear risk",
        format_percentage(str(data.portfolio["target_bear_portfolio_at_risk"])),
    )
    target_concentration = data.portfolio.get("target_concentration")
    if isinstance(target_concentration, dict):
        st.dataframe(
            [
                {
                    "Basis": "Current working sleeve",
                    "Top two": format_percentage(str(current_concentration["top_two_weight"])),
                    "Top three": format_percentage(str(current_concentration["top_three_weight"])),
                    "HHI": f"{Decimal(str(current_concentration['hhi'])):.3f}",
                    "Effective positions": (
                        f"{Decimal(str(current_concentration['effective_positions'])):.2f}"
                    ),
                },
                {
                    "Basis": "Target invested capital",
                    "Top two": format_percentage(str(target_concentration["top_two_weight"])),
                    "Top three": format_percentage(str(target_concentration["top_three_weight"])),
                    "HHI": f"{Decimal(str(target_concentration['hhi'])):.3f}",
                    "Effective positions": (
                        f"{Decimal(str(target_concentration['effective_positions'])):.2f}"
                    ),
                },
            ],
            hide_index=True,
            width="stretch",
        )
    st.subheader("Common drivers")
    for decision in data.decisions:
        st.markdown(f"**{decision.company_name}:** " + " · ".join(decision.common_drivers))
    st.warning(str(data.portfolio["provisional_holdings_warning"]), icon="⚠️")


def _company_intelligence(data: DashboardData) -> None:
    st.header("Company Intelligence")
    company_names = {item.company_name: item.company_id for item in data.decisions}
    requested_company = st.query_params.get("company", "")
    name_options = tuple(company_names)
    selected_index = next(
        (
            index
            for index, name in enumerate(name_options)
            if company_names[name] == requested_company
        ),
        0,
    )
    selected_name = st.selectbox(
        "Company", name_options, index=selected_index, key="company_selector"
    )
    if company_names[selected_name] != requested_company:
        st.query_params["company"] = company_names[selected_name]
    decision = data.decision(company_names[selected_name])
    memo = data.memo(decision.company_id)
    raw_company = company_snapshot_payload(data, decision.company_id)
    cols = st.columns(5)
    cols[0].metric("Stance", decision.underlying_stance.upper())
    cols[1].metric("Portfolio action", decision.final_portfolio_action.upper())
    cols[2].metric("Current weight", format_percentage(decision.working_current_weight))
    cols[3].metric("Target weight", format_percentage(decision.target_weight))
    cols[4].metric("Principle score", f"{decision.weighted_principle_score} / 5")
    st.markdown(
        "**Decision labels:** "
        f"stance `{decision.underlying_stance.upper()}` · "
        f"final portfolio action `{decision.final_portfolio_action.upper()}`"
    )
    if decision.human_review_required:
        st.warning("Human review required · " + ", ".join(decision.human_review_reasons))
    else:
        st.success("No portfolio-approval overlay is active for this company.")

    left, right = st.columns((1, 1))
    with left:
        st.subheader("Six investment principles")
        st.dataframe(
            [
                {
                    "Dimension": str(item["dimension"]).replace("_", " ").title(),
                    "Score": item["score"],
                    "Weight": format_percentage(str(item["weight"])),
                    "Quality": str(item["data_quality"]).upper(),
                    "Rule": item["rule"],
                }
                for item in decision.principle_scores
            ],
            hide_index=True,
            width="stretch",
        )
    with right:
        st.subheader("Hard gates")
        st.dataframe(
            [
                {
                    "Gate": item["code"],
                    "Status": str(item["status"]).upper(),
                    "Consequence": str(item["consequence"]).upper(),
                    "Explanation": item["explanation"],
                }
                for item in decision.hard_gates
            ],
            hide_index=True,
            width="stretch",
        )

    st.subheader("Three-year valuation scenarios")
    st.dataframe(
        [
            {
                "Scenario": str(_mapping(item["input"], "scenario")["name"]).title(),
                "Target value": format_inr(str(item["target_price"])),
                "Price CAGR": format_percentage(str(item["price_cagr"])),
                "Revenue growth": format_percentage(
                    str(_mapping(item["input"], "scenario")["annual_revenue_growth"])
                ),
                "Terminal margin": format_percentage(
                    str(_mapping(item["input"], "scenario")["terminal_margin"])
                ),
            }
            for item in ordered_scenarios(decision)
        ],
        hide_index=True,
        width="stretch",
    )

    scored = [item for item in decision.principle_scores if item["score"] is not None]
    strongest = max(scored, key=lambda item: Decimal(str(item["score"])))
    weakest = min(scored, key=lambda item: Decimal(str(item["score"])))
    support_ids = cast(list[str], strongest["evidence_ids"])
    counter_ids = cast(list[str], weakest["counter_evidence_ids"] or weakest["evidence_ids"])
    st.subheader("Evidence balance")
    support_col, counter_col = st.columns(2)
    support_col.markdown("**Strongest support**")
    support_col.write(str(strongest["rule"]))
    support_col.code("\n".join(support_ids), language=None)
    counter_col.markdown("**Strongest counter-evidence**")
    counter_col.write(str(weakest["rule"]))
    counter_col.code("\n".join(counter_ids), language=None)

    st.subheader("Portfolio intelligence memo")
    presentation = memo_state_presentation(memo)
    getattr(st, _status_method(presentation.tone))(f"{presentation.label}. {presentation.message}")
    st.caption(
        f"Provider `{memo.provider}` · deployment `{memo.deployment_id}` · reasoning "
        f"`{memo.reasoning_effort}` · output limit `{memo.max_output_tokens}` tokens"
    )
    if memo.status is MemoStatus.GENERATED and memo.narrative is not None:
        _render_claim(memo.narrative.executive_summary)
        for section in MEMO_SECTION_NAMES:
            st.markdown(f"#### {section.replace('_', ' ').title()}")
            for claim in memo.narrative.sections[section]:
                _render_claim(claim)
        if memo.usage is not None:
            st.caption(
                "Token usage · input "
                f"{memo.usage['input_tokens']} · output {memo.usage['output_tokens']} · "
                f"total {memo.usage['total_tokens']}"
            )

    st.subheader("What would change the view")
    for trigger in decision.change_triggers:
        st.markdown(f"- {trigger}")
    st.subheader("Missing information")
    for item in decision.missing_data_flags:
        st.markdown(f"- {item}")

    evidence_index = {
        item.evidence_id: item for item in data.evidence_by_company[decision.company_id]
    }
    with st.expander("Citation details"):
        cited_ids = (
            sorted(
                {evidence_id for claim in _memo_claims(memo) for evidence_id in claim.evidence_ids}
            )
            if memo.narrative is not None
            else sorted(decision.evidence_ids)
        )
        for evidence_id in cited_ids:
            evidence = evidence_index[evidence_id]
            conflict = ", ".join(evidence.conflicting_evidence_ids) or "None recorded"
            st.markdown(
                f"**`{evidence.evidence_id}`** · {evidence.evidence_classification} · "
                f"available {format_date(evidence.available_date)}"
            )
            st.caption(
                f"{evidence.source_title} · {evidence.source_type} · "
                f"{evidence.source_locator} · conflicts: {conflict}"
            )
    st.caption(
        f"Price {format_inr(decision.current_price)} as of {format_date(decision.price_date)} · "
        "position bear-risk contribution "
        f"{format_percentage(str(raw_company['position_bear_portfolio_at_risk']))}"
    )


def _assumptions_and_audit(data: DashboardData) -> None:
    st.header("Assumptions & Audit")
    st.caption("What is fixed, what is provisional, and how every explanation is constrained.")
    cols = st.columns(3)
    cols[0].metric("Decision date", format_date(str(data.portfolio["decision_date"])))
    cols[1].metric("Evidence cutoff", "08 Sep 2026")
    cols[2].metric("Decision engine", str(data.portfolio["engine_version"]))
    st.subheader("Traceability")
    st.markdown("**Evidence manifest hash**")
    st.code(str(data.portfolio["evidence_manifest_sha256"]), language=None)
    st.markdown("**Decision snapshot hash**")
    st.code(str(data.portfolio["snapshot_sha256"]), language=None)
    st.write(f"Configuration version: `{data.portfolio['configuration_version']}`")

    st.subheader("Memo runtime")
    st.dataframe(
        [
            {
                "Company": memo.decision.company_name,
                "Status": memo.status.value,
                "Provider": memo.provider,
                "Deployment": memo.deployment_id,
                "Reasoning": memo.reasoning_effort,
                "Output limit": memo.max_output_tokens,
            }
            for memo in data.memos
        ],
        hide_index=True,
        width="stretch",
    )
    st.write("Memo contract: `company-memo-v1` · Prompt: `company-memo-prompt-v1`")

    st.subheader("Authority boundary")
    st.markdown(
        '<div class="flow"><span>Protected input + public evidence</span><b>→</b>'
        "<span>Deterministic ingestion + analytics</span><b>→</b>"
        "<span>Decision snapshot</span><b>→</b><span>Bounded evidence context</span><b>→</b>"
        "<span>Azure portfolio-intelligence memo</span><b>→</b>"
        "<span>Validated display</span></div>",
        unsafe_allow_html=True,
    )
    st.info(
        "The LLM explains a frozen result. It does not determine scores, valuation scenarios, "
        "weights, stances, or portfolio actions. Invalid narratives are never shown as trusted."
    )

    st.subheader("Declared limitations")
    st.markdown(f"- {data.portfolio['provisional_holdings_warning']}")
    for limitation in data.decisions[0].valuation_limitations:
        st.markdown(f"- {limitation}")
    st.markdown(
        f"- Primary benchmark `{data.portfolio['primary_benchmark_id']}` is "
        f"**{data.portfolio['primary_benchmark_status']}**."
    )
    st.markdown(
        f"- `{data.portfolio['secondary_benchmark_id']}` is "
        f"**{data.portfolio['secondary_benchmark_status']}** and remains historical context only."
    )


def _render_claim(claim: MemoClaim) -> None:
    st.markdown(claim.text)
    st.caption("Evidence · " + " · ".join(f"`{item}`" for item in claim.evidence_ids))


def _memo_claims(memo: object) -> tuple[MemoClaim, ...]:
    from enam_assessment.portfolio_ui import LoadedMemoArtifact

    if not isinstance(memo, LoadedMemoArtifact) or memo.narrative is None:
        return ()
    return (memo.narrative.executive_summary,) + tuple(
        claim for section in MEMO_SECTION_NAMES for claim in memo.narrative.sections[section]
    )


def _status_method(tone: str) -> str:
    return {"positive": "success", "neutral": "info", "warning": "warning", "risk": "error"}[tone]


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise UIArtifactError(f"{label} must be an object.")
    return cast(dict[str, object], value)


def _records(value: dict[str, object], key: str) -> list[dict[str, object]]:
    records = value.get(key)
    if not isinstance(records, list):
        raise UIArtifactError(f"Historical field {key!r} must be an array.")
    return [_mapping(item, key) for item in records]


def _styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --paper: #f5f1e8;
          --ink: #14213d;
          --teal: #0f766e;
          --amber: #b7791f;
          --risk: #a33d3d;
          --line: #d8d1c4;
        }
        .stApp { background: var(--paper); color: var(--ink); }
        [data-testid="stSidebar"] { background: #ebe5da; border-right: 1px solid var(--line); }
        .brand-mark {
          color: var(--ink); font-size: .85rem; font-weight: 800; letter-spacing: .14em;
        }
        h1 { color: var(--ink); font-family: Georgia, serif; letter-spacing: -.035em; }
        h2, h3, h4 { color: var(--ink); letter-spacing: -.015em; }
        .eyebrow { color: var(--teal); font-size: .76rem; font-weight: 800; letter-spacing: .16em; }
        [data-testid="stMetric"] { border-top: 2px solid var(--ink); padding-top: .7rem; }
        [data-testid="stMetricValue"] { color: var(--ink); font-family: Georgia, serif; }
        .flow { display:flex; flex-wrap:wrap; gap:.55rem; align-items:center; margin:1rem 0; }
        .flow span { border-bottom:2px solid var(--teal); padding:.45rem .1rem; font-weight:600; }
        code { color: #244b47 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
