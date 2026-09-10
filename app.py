"""Local Streamlit entry point for the Portfolio Intelligence application."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import streamlit as st

from enam_assessment.errors import (
    MemoConfigurationError,
    PortfolioIntelligenceError,
    UIArtifactError,
)
from enam_assessment.intelligence import (
    DEFAULT_BRIEF_INPUT_TOKENS,
    DEFAULT_QUESTION_INPUT_TOKENS,
    AnswerArtifact,
    AnswerStatus,
    CitationCard,
    QuestionContext,
    QuestionScope,
    SelectedArtifact,
    build_hard_gates_artifact,
    build_interactive_provider,
    build_question_context,
    citation_cards,
    get_or_generate_answer,
    history_item_from_artifact,
)
from enam_assessment.memo import DecisionMemoInput, MemoClaim
from enam_assessment.portfolio_session import (
    Disposition,
    HoldingsOverlay,
    HumanDisposition,
    ScenarioDelta,
    calculate_holdings_overlay,
    recalculate_scenario,
    record_disposition,
)
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
LOCAL_ANSWER_AUDIT = ROOT / "artifacts" / "phase8b" / "live_answer_audit.jsonl"
VIEWS = (
    "Portfolio Cockpit",
    "Company Intelligence",
    "Investor Behaviour",
    "Assumptions & Audit",
)


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
        overlay = _active_overlay(data)
    except (PortfolioIntelligenceError, UIArtifactError) as exc:
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
        basis = "Session-adjusted" if overlay.uses_session_values else "Supplied-data defaults"
        st.caption(f"Active holdings: {basis}")
        if st.button(
            "Ask Portfolio Intelligence",
            key="sidebar_ai_launcher",
            type="primary",
            width="stretch",
        ):
            st.session_state["ai_dialog_open"] = True

    _header(data, overlay)
    if view == "Portfolio Cockpit":
        _portfolio_cockpit(data, overlay)
    elif view == "Company Intelligence":
        _company_intelligence(data, overlay)
    elif view == "Investor Behaviour":
        _investor_behaviour(data)
    else:
        _assumptions_and_audit(data, overlay)
    if st.session_state.get("ai_dialog_open", False):
        _portfolio_intelligence_dialog(data, _active_overlay(data), view)


def _header(data: DashboardData, overlay: HoldingsOverlay) -> None:
    review_count = sum(item.human_review_required for item in data.decisions)
    holdings_basis = (
        "Session-adjusted holdings" if overlay.uses_session_values else "Supplied-data holdings"
    )
    st.markdown(
        '<div class="status-strip"><strong>PORTFOLIO INTELLIGENCE</strong>'
        f"<span>Decision {format_date(str(data.portfolio['decision_date']))}</span>"
        f"<span>{review_count} companies need review</span>"
        f"<span>{holdings_basis}</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def _page_heading(
    data: DashboardData,
    overlay: HoldingsOverlay,
    *,
    view: str,
    title: str,
    scope: str,
) -> None:
    title_column, action_column = st.columns((4.5, 1.4), vertical_alignment="bottom")
    with title_column:
        st.title(title)
        st.caption(scope)
    with action_column:
        if st.button(
            "Ask AI about this page",
            key=f"page_ai_{view}",
            type="primary",
            width="stretch",
        ):
            artifact = _default_page_artifact(data, overlay, view)
            _select_artifact(artifact)
            st.session_state["ai_dialog_open"] = True


def _portfolio_cockpit(data: DashboardData, overlay: HoldingsOverlay) -> None:
    _page_heading(
        data,
        overlay,
        view="Portfolio Cockpit",
        title="Portfolio Cockpit",
        scope=(
            "What is the portfolio state, what needs attention, and where should you investigate?"
        ),
    )

    metrics = st.columns(5)
    metrics[0].metric("Represented capital", format_inr(overlay.total_value))
    metrics[1].metric("Available cash", format_inr(overlay.available_cash))
    metrics[2].metric("Top two", format_percentage(overlay.concentration.top_two_weight))
    metrics[3].metric("HHI", f"{overlay.concentration.hhi:.3f}")
    metrics[4].metric("Effective positions", f"{overlay.concentration.effective_positions:.2f}")

    rows = allocation_rows(data)
    if overlay.concentration.requires_review:
        st.warning(
            "The active overlay breaches prototype concentration review conventions: "
            + ", ".join(overlay.concentration.review_reasons)
            + "."
        )
    st.caption(
        "Calculated from supplied workbook open lots and frozen prices. These represented holdings "
        "are not independently verified as the complete live portfolio."
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="portfolio-summary-concentration",
            label="Portfolio summary and concentration",
            origin_page="Portfolio Cockpit",
            company_ids=(),
            payload={
                "represented_total_value": str(overlay.total_value),
                "available_cash": str(overlay.available_cash),
                "cash_source": overlay.cash_source,
                "company_weights": {
                    item.company_id: str(overlay.company_weights[item.company_id])
                    for item in data.decisions
                },
                "cash_weight": str(overlay.cash_weight),
                "top_two_weight": str(overlay.concentration.top_two_weight),
                "top_three_weight": str(overlay.concentration.top_three_weight),
                "hhi": str(overlay.concentration.hhi),
                "effective_positions": str(overlay.concentration.effective_positions),
                "review_reasons": list(overlay.concentration.review_reasons),
            },
        ),
        key="portfolio_summary_concentration",
    )

    st.subheader("Current versus frozen target allocation")
    st.bar_chart(
        {
            "Company": [row.company_id.upper() for row in rows] + ["CASH"],
            "Current": [float(overlay.company_weights[row.company_id] * 100) for row in rows]
            + [float(overlay.cash_weight * 100)],
            "Frozen target": [float(row.target_weight * 100) for row in rows]
            + [float(Decimal(str(data.portfolio["cash_target_weight"])) * 100)],
        },
        x="Company",
        y=["Current", "Frozen target"],
        x_label="Company",
        y_label="Allocation (%)",
        horizontal=True,
        color=["#1f3a5f", "#0f766e"],
    )
    st.dataframe(
        [
            {
                "Company": row.company_name,
                "Active current": format_percentage(overlay.company_weights[row.company_id]),
                "Frozen target": format_percentage(row.target_weight),
                "Stance": row.underlying_stance.upper(),
                "Portfolio action": row.final_action.upper(),
                "Owner approval": "Required" if row.human_review_required else "Not required",
                "Frozen bear risk": format_percentage(row.bear_portfolio_at_risk),
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="portfolio-allocation",
            label="Current versus target allocation",
            origin_page="Portfolio Cockpit",
            company_ids=tuple(item.company_id for item in data.decisions),
            payload={
                "focus": "active allocation versus frozen target allocation",
                "target_weights": {
                    item.company_id: format_percentage(item.target_weight)
                    for item in data.decisions
                },
                "target_cash_weight": str(data.portfolio["cash_target_weight"]),
                "target_bear_portfolio_at_risk": str(
                    data.portfolio["target_bear_portfolio_at_risk"]
                ),
                "target_concentration": data.portfolio["target_concentration"],
            },
        ),
        key="portfolio_allocation",
    )

    target_concentration = _mapping(data.portfolio["target_concentration"], "target concentration")
    st.markdown("**Frozen target risk profile**")
    target_metrics = st.columns(3)
    target_metrics[0].metric(
        "Residual target cash", format_percentage(str(data.portfolio["cash_target_weight"]))
    )
    target_metrics[1].metric(
        "Target bear-risk exposure",
        format_percentage(str(data.portfolio["target_bear_portfolio_at_risk"])),
    )
    target_metrics[2].metric(
        "Risky-sleeve top two", format_percentage(str(target_concentration["top_two_weight"]))
    )
    target_metrics = st.columns(3)
    target_metrics[0].metric(
        "Risky-sleeve top three", format_percentage(str(target_concentration["top_three_weight"]))
    )
    target_metrics[1].metric("Risky-sleeve HHI", f"{Decimal(str(target_concentration['hhi'])):.3f}")
    target_metrics[2].metric(
        "Effective risky positions",
        f"{Decimal(str(target_concentration['effective_positions'])):.2f}",
    )
    st.caption(
        "Frozen target concentration is measured within the invested company sleeve; residual "
        "target cash is shown separately."
    )

    st.subheader("Priority decisions")
    for decision in data.decisions:
        label = f"{decision.company_name} · {decision.underlying_stance.upper()}"
        with st.expander(label):
            st.write(
                f"Final portfolio action: **{decision.final_portfolio_action.upper()}** · "
                "active weight: **"
                f"{format_percentage(overlay.company_weights[decision.company_id])}** · "
                f"frozen target: **{format_percentage(decision.target_weight)}**"
            )
            if decision.human_review_required:
                st.warning("Owner review: " + "; ".join(decision.human_review_reasons))
            st.caption("Common drivers: " + " · ".join(decision.common_drivers))
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="portfolio-priority-decisions",
            label="Priority decisions",
            origin_page="Portfolio Cockpit",
            company_ids=tuple(item.company_id for item in data.decisions),
            payload={
                "decisions": [
                    {
                        "company_id": item.company_id,
                        "stance": item.underlying_stance,
                        "final_action": item.final_portfolio_action,
                        "active_weight": str(overlay.company_weights[item.company_id]),
                        "frozen_target_weight": item.target_weight,
                        "human_review_required": item.human_review_required,
                        "human_review_reasons": list(item.human_review_reasons),
                        "common_drivers": list(item.common_drivers),
                    }
                    for item in data.decisions
                ]
            },
        ),
        key="portfolio_priority_decisions",
    )

    _holdings_verification(data, overlay)
    _comparison_surface(data, overlay)


def _holdings_verification(data: DashboardData, overlay: HoldingsOverlay) -> None:
    with st.expander("Review or adjust portfolio values", expanded=False):
        st.caption(
            "Shares are calculated from the supplied workbook and are active immediately. "
            "Optional edits remain session-local and do not promote a new investment decision."
        )
        if overlay.cash_source == "assumed_zero":
            st.info("Cash was not supplied; these calculations assume ₹0 unless you enter a value.")
        with st.form("holdings_verification_form"):
            cols = st.columns(2)
            inputs: dict[str, float] = {}
            active = {item.company_id: item for item in overlay.holdings}
            for index, decision in enumerate(data.decisions):
                inputs[decision.company_id] = cols[index % 2].number_input(
                    f"{decision.company_name} shares",
                    min_value=0.0,
                    value=float(active[decision.company_id].shares),
                    step=1.0,
                    key=f"holding_{decision.company_id}",
                )
            cash = st.number_input(
                "Available cash (₹)",
                min_value=0.0,
                value=float(overlay.available_cash),
                step=100000.0,
                key="available_cash_input",
            )
            confirmed = st.form_submit_button("Apply session values")
        reset = st.button("Reset to supplied-data defaults", key="reset_holdings")
        if confirmed:
            baseline = {item.company_id: Decimal(item.working_shares) for item in data.decisions}
            st.session_state["share_overrides"] = {
                company_id: Decimal(str(value))
                for company_id, value in inputs.items()
                if Decimal(str(value)) != baseline[company_id]
            }
            st.session_state["available_cash"] = Decimal(str(cash))
            _record_audit(
                "holdings_verified",
                {
                    "shares": {key: str(value) for key, value in inputs.items()},
                    "available_cash": str(cash),
                },
            )
            st.success("Session-entered values are active; supplied defaults remain preserved.")
            st.rerun()
        if reset:
            st.session_state.pop("share_overrides", None)
            st.session_state.pop("available_cash", None)
            _record_audit("holdings_reset", {"basis": "supplied_workbook_defaults"})
            st.rerun()


def _company_intelligence(data: DashboardData, overlay: HoldingsOverlay) -> None:
    _page_heading(
        data,
        overlay,
        view="Company Intelligence",
        title="Company Intelligence",
        scope=(
            "Start with the decision and hard gates, then examine quality, valuation, and evidence."
        ),
    )
    company_names = {item.company_name: item.company_id for item in data.decisions}
    requested_company = st.query_params.get("company", "")
    options = tuple(company_names)
    selected_index = next(
        (index for index, name in enumerate(options) if company_names[name] == requested_company),
        0,
    )
    selected_name = st.selectbox("Company", options, index=selected_index, key="company_selector")
    company_id = company_names[selected_name]
    st.session_state["current_company_id"] = company_id
    if company_id != requested_company:
        st.query_params["company"] = company_id
    decision = data.decision(company_id)
    raw_company = company_snapshot_payload(data, company_id)

    decision_row = st.columns((1, 1.45, 1))
    decision_row[0].metric("Underlying stance", decision.underlying_stance.upper())
    decision_row[1].metric("Final portfolio action", decision.final_portfolio_action.upper())
    decision_row[2].metric(
        "Human review", "REQUIRED" if decision.human_review_required else "NOT REQUIRED"
    )
    exposure_row = st.columns(3)
    exposure_row[0].metric(
        "Active represented weight", format_percentage(overlay.company_weights[company_id])
    )
    exposure_row[1].metric("Frozen target", format_percentage(decision.target_weight))
    exposure_row[2].metric("Principle score", f"{decision.weighted_principle_score} / 5")
    if decision.human_review_required:
        st.warning("Human review required · " + "; ".join(decision.human_review_reasons))
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id=f"{company_id}-decision-summary",
            label=f"{decision.company_name} decision summary",
            origin_page="Company Intelligence",
            company_ids=(company_id,),
            payload={
                "stance": decision.underlying_stance,
                "final_action": decision.final_portfolio_action,
                "human_review_required": decision.human_review_required,
                "human_review_reasons": list(decision.human_review_reasons),
                "active_weight": str(overlay.company_weights[company_id]),
                "frozen_target_weight": decision.target_weight,
                "weighted_principle_score": decision.weighted_principle_score,
            },
        ),
        key=f"decision_summary_{company_id}",
    )

    left, right = st.columns((1, 1))
    with left:
        st.subheader("Hard gates")
        st.dataframe(
            [
                {
                    "Gate": item["code"],
                    "Status": str(item["status"]).upper(),
                }
                for item in decision.hard_gates
            ],
            hide_index=True,
            width="stretch",
        )
        with st.expander("Gate consequences and explanations"):
            for gate_item in decision.hard_gates:
                st.markdown(
                    f"**{gate_item['code']}** — {str(gate_item['status']).upper()} / "
                    f"{str(gate_item['consequence']).upper()}"
                )
                st.write(str(gate_item["explanation"]))
        _discuss_artifact_button(
            build_hard_gates_artifact(data, company_id),
            key=f"hard_gates_{company_id}",
        )
    with right:
        st.subheader("Investment principles")
        st.dataframe(
            [
                {
                    "Dimension": str(item["dimension"]).replace("_", " ").title(),
                    "Score": item["score"],
                }
                for item in decision.principle_scores
            ],
            hide_index=True,
            width="stretch",
        )
        with st.expander("Principle details"):
            for principle_item in decision.principle_scores:
                dimension = str(principle_item["dimension"]).replace("_", " ").title()
                st.markdown(
                    f"**{dimension}** — score {principle_item['score']} / 5; "
                    f"quality {str(principle_item['data_quality']).upper()}"
                )
                st.write(str(principle_item["rule"]))
        _discuss_artifact_button(
            SelectedArtifact(
                artifact_id=f"{company_id}-investment-principles",
                label=f"{decision.company_name} investment principles",
                origin_page="Company Intelligence",
                company_ids=(company_id,),
                payload={
                    "weighted_score": decision.weighted_principle_score,
                    "principle_scores": list(decision.principle_scores),
                },
                evidence_ids=tuple(
                    dict.fromkeys(
                        evidence_id
                        for principle in decision.principle_scores
                        for evidence_id in cast(list[str], principle["evidence_ids"])
                        + cast(list[str], principle["counter_evidence_ids"])
                    )
                ),
            ),
            key=f"principles_{company_id}",
        )

    st.subheader("Three-year valuation scenarios")
    st.dataframe(_scenario_table(decision), hide_index=True, width="stretch")
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id=f"{company_id}-valuation-scenarios",
            label=f"{decision.company_name} valuation scenarios",
            origin_page="Company Intelligence",
            company_ids=(company_id,),
            payload={"scenarios": list(decision.scenarios)},
            evidence_ids=tuple(
                dict.fromkeys(
                    evidence_id
                    for scenario in decision.scenarios
                    for evidence_id in cast(
                        list[str], _mapping(scenario["input"], "scenario")["evidence_ids"]
                    )
                )
            ),
        ),
        key=f"valuation_{company_id}",
    )

    st.subheader("Evidence balance")
    scored = [item for item in decision.principle_scores if item["score"] is not None]
    strongest = max(scored, key=lambda item: Decimal(str(item["score"])))
    weakest = min(scored, key=lambda item: Decimal(str(item["score"])))
    support, counter = st.columns(2)
    support.markdown("**Strongest support**")
    support.write(str(strongest["rule"]))
    support.code("\n".join(cast(list[str], strongest["evidence_ids"])), language=None)
    counter.markdown("**Strongest counter-evidence**")
    counter.write(str(weakest["rule"]))
    counter.code(
        "\n".join(cast(list[str], weakest["counter_evidence_ids"] or weakest["evidence_ids"])),
        language=None,
    )
    st.markdown("**Missing information**")
    if decision.missing_data_flags:
        for item in decision.missing_data_flags:
            st.markdown(f"- {item}")
    else:
        st.caption("No missing-data flag is recorded in the frozen decision.")
    conflict_records = [
        {
            "evidence_id": item.evidence_id,
            "conflicting_evidence_ids": list(item.conflicting_evidence_ids),
        }
        for item in data.evidence_by_company[company_id]
        if item.conflicting_evidence_ids
    ]
    if conflict_records:
        with st.expander("Recorded evidence conflicts"):
            for conflict in conflict_records:
                st.markdown(
                    f"- `{conflict['evidence_id']}` conflicts with "
                    + ", ".join(
                        f"`{evidence_id}`"
                        for evidence_id in cast(list[str], conflict["conflicting_evidence_ids"])
                    )
                )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id=f"{company_id}-evidence-balance",
            label=f"{decision.company_name} evidence balance and missing information",
            origin_page="Company Intelligence",
            company_ids=(company_id,),
            payload={
                "strongest_support": strongest["rule"],
                "strongest_counter_evidence": weakest["rule"],
                "missing_information": list(decision.missing_data_flags),
                "conflicts": conflict_records,
            },
            evidence_ids=tuple(
                dict.fromkeys(
                    cast(list[str], strongest["evidence_ids"])
                    + cast(list[str], weakest["counter_evidence_ids"] or weakest["evidence_ids"])
                )
            ),
        ),
        key=f"evidence_balance_{company_id}",
    )

    benchmark = decision.historical_benchmark_context
    st.subheader("Historical benchmark context")
    matched_lots = int(str(benchmark.get("secondary_benchmark_matched_lots", 0)))
    eligible_lots = int(str(benchmark.get("eligible_lots", 0)))
    relative_return = benchmark.get("cost_weighted_secondary_relative_return")
    st.info(
        "S&P BSE 500 TRI remains unavailable as the intended primary benchmark. "
        "NIFTY 500 TRI is a secondary historical cross-check only and does not drive the score, "
        "valuation, stance, or action."
    )
    benchmark_metrics = st.columns(2)
    benchmark_metrics[0].metric(
        "NIFTY-matched realized lots", f"{matched_lots:,} / {eligible_lots:,}"
    )
    benchmark_metrics[1].metric(
        "Cost-weighted relative return",
        "Unavailable" if relative_return is None else format_percentage(str(relative_return)),
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id=f"{company_id}-historical-benchmark",
            label=f"{decision.company_name} historical benchmark context",
            origin_page="Company Intelligence",
            company_ids=(company_id,),
            payload={
                "benchmark_context": benchmark,
                "primary_benchmark": "S&P BSE 500 TRI unavailable",
                "secondary_benchmark": "NIFTY 500 TRI contextual cross-check only",
                "decision_use": "not a principle score, valuation input, or action driver",
            },
        ),
        key=f"benchmark_context_{company_id}",
    )

    st.subheader("What would change the view")
    for trigger in decision.change_triggers:
        st.markdown(f"- {trigger}")
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id=f"{company_id}-change-conditions",
            label=f"{decision.company_name} change conditions",
            origin_page="Company Intelligence",
            company_ids=(company_id,),
            payload={"change_conditions": list(decision.change_triggers)},
        ),
        key=f"change_conditions_{company_id}",
    )

    _scenario_lab(data, company_id)
    _human_disposition(data, company_id)

    with st.expander("Frozen decision details and legacy memo state"):
        memo = data.memo(company_id)
        presentation = memo_state_presentation(memo)
        getattr(st, _status_method(presentation.tone))(
            f"{presentation.label}. {presentation.message}"
        )
        st.write("**Common drivers:** " + " · ".join(decision.common_drivers))
        st.caption(
            f"Price {format_inr(decision.current_price)} as of "
            f"{format_date(decision.price_date)} · "
            "frozen position bear-risk contribution "
            f"{format_percentage(str(raw_company['position_bear_portfolio_at_risk']))}"
        )


def _scenario_lab(data: DashboardData, company_id: str) -> None:
    decision = data.decision(company_id)
    base = next(
        item for item in decision.scenarios if _mapping(item["input"], "scenario")["name"] == "base"
    )
    raw = cast(dict[str, object], base["input"])
    st.subheader("Scenario Lab")
    st.caption(
        "Change supported inputs and recalculate through the existing deterministic valuation "
        "function. The frozen base case remains unchanged."
    )
    with st.form(f"scenario_form_{company_id}"):
        cols = st.columns(4)
        growth = cols[0].number_input(
            "Revenue growth (%)",
            value=float(Decimal(str(raw["annual_revenue_growth"])) * 100),
            step=0.5,
            key=f"growth_{company_id}",
        )
        margin = cols[1].number_input(
            "Terminal margin (%)",
            value=float(Decimal(str(raw["terminal_margin"])) * 100),
            step=0.5,
            key=f"margin_{company_id}",
        )
        multiple = cols[2].number_input(
            "Exit multiple factor",
            min_value=0.01,
            value=float(Decimal(str(raw["multiple_change_factor"]))),
            step=0.05,
            key=f"multiple_{company_id}",
        )
        bridge = cols[3].number_input(
            "Equity bridge factor",
            min_value=0.01,
            value=float(Decimal(str(raw["equity_bridge_factor"]))),
            step=0.05,
            key=f"bridge_{company_id}",
        )
        run = st.form_submit_button("Recalculate scenario")
    if run:
        try:
            computed_delta = recalculate_scenario(
                decision,
                scenario_name="base",
                annual_revenue_growth=Decimal(str(growth)) / 100,
                terminal_margin=Decimal(str(margin)) / 100,
                multiple_change_factor=Decimal(str(multiple)),
                equity_bridge_factor=Decimal(str(bridge)),
            )
        except PortfolioIntelligenceError as exc:
            st.error(str(exc))
        else:
            st.session_state.setdefault("scenario_deltas", {})[company_id] = computed_delta
            _record_audit("scenario_recalculated", computed_delta.stable_payload())
    active_delta = cast(dict[str, ScenarioDelta], st.session_state.get("scenario_deltas", {})).get(
        company_id
    )
    if active_delta is not None:
        cols = st.columns(3)
        cols[0].metric("Frozen base target", format_inr(active_delta.baseline.target_price))
        cols[1].metric(
            "Sandbox target",
            format_inr(active_delta.recalculated.target_price),
            delta=format_inr(active_delta.target_price_delta),
        )
        cols[2].metric(
            "Sandbox CAGR",
            format_percentage(active_delta.recalculated.price_cagr),
            delta=format_percentage(active_delta.price_cagr_delta),
        )
        _discuss_artifact_button(
            SelectedArtifact(
                artifact_id=f"{company_id}-scenario-delta",
                label=f"{decision.company_name} scenario delta",
                origin_page="Company Intelligence",
                company_ids=(company_id,),
                payload=active_delta.stable_payload(),
            ),
            key=f"scenario_{company_id}",
        )


def _human_disposition(data: DashboardData, company_id: str) -> None:
    decision = data.decision(company_id)
    st.subheader("Owner disposition")
    st.caption("Record a supervised view. This does not place a trade or alter the engine result.")
    with st.form(f"disposition_form_{company_id}"):
        disposition = st.radio("Disposition", ("accepted", "rejected", "deferred"), horizontal=True)
        note = st.text_input("Optional note", key=f"disposition_note_{company_id}")
        submit = st.form_submit_button("Record disposition")
    if submit:
        record = record_disposition(
            decision,
            disposition=cast(Disposition, disposition),
            note=note,
            recorded_at=datetime.now(UTC),
        )
        st.session_state.setdefault("dispositions", {})[company_id] = record
        _record_audit("human_disposition", record.stable_payload())
        st.success(
            f"Recorded {record.disposition.upper()}; engine action remains "
            f"{record.engine_action.upper()}."
        )
    existing = cast(dict[str, HumanDisposition], st.session_state.get("dispositions", {})).get(
        company_id
    )
    if existing is not None:
        st.info(
            f"Session disposition: {existing.disposition.upper()} · engine action: "
            f"{existing.engine_action.upper()} · {existing.note or 'No note'}"
        )


def _comparison_surface(data: DashboardData, overlay: HoldingsOverlay) -> None:
    with st.expander("Compare two companies"):
        names = {item.company_name: item.company_id for item in data.decisions}
        options = tuple(names)
        cols = st.columns(2)
        first = cols[0].selectbox("First company", options, key="compare_first")
        second = cols[1].selectbox("Second company", options, index=1, key="compare_second")
        if first == second:
            st.warning("Choose two different companies.")
            return
        selected = (names[first], names[second])
        comparison_rows: list[dict[str, object]] = []
        for company_id in selected:
            decision = data.decision(company_id)
            base = next(
                item
                for item in decision.scenarios
                if _mapping(item["input"], "scenario")["name"] == "base"
            )
            comparison_rows.append(
                {
                    "Company": decision.company_name,
                    "Active weight": format_percentage(overlay.company_weights[company_id]),
                    "Frozen target": format_percentage(decision.target_weight),
                    "Stance": decision.underlying_stance.upper(),
                    "Portfolio action": decision.final_portfolio_action.upper(),
                    "Principle score": f"{decision.weighted_principle_score} / 5",
                    "Base CAGR": format_percentage(str(base["price_cagr"])),
                    "Failed or unknown gates": sum(
                        str(gate["status"]) != "pass" for gate in decision.hard_gates
                    ),
                }
            )
        st.dataframe(comparison_rows, hide_index=True, width="stretch")
        _discuss_artifact_button(
            SelectedArtifact(
                artifact_id="comparison-" + "-".join(sorted(selected)),
                label=f"Compare {first} with {second}",
                origin_page="Portfolio Cockpit",
                company_ids=selected,
                payload={
                    "comparison_dimensions": [
                        "business quality",
                        "valuation",
                        "balance sheet",
                        "risks",
                        "missing evidence",
                    ],
                    "deterministic_comparison": comparison_rows,
                },
            ),
            key="comparison",
        )


def _dismiss_ai_dialog() -> None:
    st.session_state["ai_dialog_open"] = False


@st.dialog(
    "Portfolio Intelligence",
    width="large",
    icon=":material/insights:",
    on_dismiss=_dismiss_ai_dialog,
)
def _portfolio_intelligence_dialog(
    data: DashboardData, overlay: HoldingsOverlay, view: str
) -> None:
    _shared_conversation(data, overlay, view)


def _shared_conversation(data: DashboardData, overlay: HoldingsOverlay, view: str) -> None:
    st.caption(
        "Ask about the selected page or analytical sections. The model explains the frozen "
        "analysis; it does not recalculate or change the decision."
    )
    default_artifact = _default_page_artifact(data, overlay, view)
    selected = cast(
        dict[str, SelectedArtifact], st.session_state.setdefault("selected_artifacts", {})
    )
    if st.button("Ask AI about this page", key=f"dialog_page_context_{view}"):
        _select_artifact(default_artifact)
    active_artifacts = tuple(selected[key] for key in sorted(selected)) or (default_artifact,)
    if selected:
        st.caption("Selected context")
        for artifact in active_artifacts:
            cols = st.columns((5, 1))
            cols[0].caption(
                f"{artifact.label} · {artifact.origin_page} · {_artifact_scope_label(artifact)}"
            )
            if cols[1].button("×", key=f"remove_context_{artifact.artifact_id}"):
                selected.pop(artifact.artifact_id, None)
                st.rerun()
        if st.button("Clear selected context", key="clear_context", width="stretch"):
            selected.clear()
            st.rerun()
    else:
        st.caption(f"Current-page context · {default_artifact.label}")

    turns = cast(list[AnswerArtifact], st.session_state.setdefault("conversation_turns", []))
    if turns:
        st.caption(f"Conversation · {len(turns)} turn(s)")
        for index, turn in enumerate(turns):
            with st.expander(
                f"{index + 1}. {turn.context.normalized_question[:62]}",
                expanded=index == len(turns) - 1,
            ):
                if _turn_predates_overlay(turn, overlay):
                    st.warning("This answer predates the active portfolio change.")
                _render_answer(data, turn, turn_key=f"turn_{index}")

    with st.form("shared_portfolio_intelligence_form"):
        question = st.text_area(
            "Ask a grounded question",
            placeholder="Why does this action differ from the attractive base-case CAGR?",
            height=90,
            key="shared_question",
        )
        submitted = st.form_submit_button("Ask Portfolio Intelligence", width="stretch")
    if not submitted:
        error = cast(str | None, st.session_state.get("conversation_error"))
        if error:
            st.info(
                "Portfolio intelligence is unavailable; deterministic analysis remains usable. "
                + error
            )
        return

    try:
        scope, company_ids, scenario_delta = _conversation_route(
            data, view, question, active_artifacts, turns
        )
        history = tuple(
            history_item_from_artifact(turn)
            for turn in turns[-3:]
            if _answer_has_status(turn, AnswerStatus.GENERATED)
        )
        context = build_question_context(
            data,
            scope=scope,
            question=question,
            company_ids=company_ids,
            scenario_delta=scenario_delta,
            active_overlay=overlay,
            selected_artifacts=active_artifacts,
            conversation_history=history,
            input_token_budget=(
                DEFAULT_BRIEF_INPUT_TOKENS
                if scope is QuestionScope.COMPANY_BRIEF
                else DEFAULT_QUESTION_INPUT_TOKENS
            ),
        )
        provider = build_interactive_provider(os.environ)
        cache = cast(dict[str, AnswerArtifact], st.session_state.setdefault("answer_cache", {}))
        with st.spinner("Building a grounded answer…"):
            generated, cached = get_or_generate_answer(
                cache,
                context,
                provider,
                system_prompt=(ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(
                    encoding="utf-8"
                ),
            )
        turns.append(generated)
        st.session_state.pop("conversation_error", None)
        payload = {**_answer_audit_payload(generated), "served_from_session_cache": cached}
        _record_audit("portfolio_intelligence_answer", payload)
        if not cached:
            _persist_answer_audit(payload)
        st.rerun()
    except (MemoConfigurationError, PortfolioIntelligenceError) as exc:
        st.session_state["conversation_error"] = str(exc)
        payload = {"status": "not_configured_or_context_error", "error": str(exc)}
        _record_audit("portfolio_intelligence_unavailable", payload)
        _persist_answer_audit(payload)
        st.rerun()


def _render_answer(data: DashboardData, artifact: AnswerArtifact, *, turn_key: str) -> None:
    if not _answer_has_status(artifact, AnswerStatus.GENERATED) or artifact.answer is None:
        method = (
            "warning" if _answer_has_status(artifact, AnswerStatus.GENERATION_FAILED) else "error"
        )
        getattr(st, method)(
            f"Portfolio intelligence: {artifact.status.value.replace('_', ' ')}. "
            f"{artifact.error or 'No validated narrative is available.'}"
        )
        return
    answer = artifact.answer
    st.markdown("#### Current view")
    _render_claim(
        data,
        artifact.context,
        answer.direct_answer,
        claim_label="Current view",
    )
    labels = {
        "supporting_points": "Principal support",
        "counterpoints": "Counter-evidence and risks",
        "relevant_unknowns": "Relevant unknowns",
        "change_conditions": "What would change the view",
    }
    for section, label in labels.items():
        claims = answer.sections[section]
        if claims:
            st.markdown(f"**{label}**")
            for index, claim in enumerate(claims, start=1):
                _render_claim(
                    data,
                    artifact.context,
                    claim,
                    claim_label=f"{label} {index}",
                    bullet=True,
                )
    all_claims = (answer.direct_answer,) + tuple(
        item for values in answer.sections.values() for item in values
    )
    all_ids = tuple(
        dict.fromkeys(evidence_id for claim in all_claims for evidence_id in claim.evidence_ids)
    )
    with st.expander("Open cited evidence"):
        st.caption(
            "Evidence appendix for this answer; claim-level sources appear beside each claim."
        )
        for index, card in enumerate(citation_cards(data, artifact.context, all_ids), start=1):
            _render_citation_card(card, source_number=index)
    if artifact.usage is not None:
        st.caption(
            f"Azure usage · input {artifact.usage.input_tokens} · output "
            f"{artifact.usage.output_tokens} · total {artifact.usage.total_tokens} · "
            f"reasoning {artifact.reasoning_effort}"
        )
    _manual_claim_support_review(artifact, turn_key=turn_key)


def _investor_behaviour(data: DashboardData) -> None:
    historical = data.historical
    realized = _records(historical, "realized_performance")
    overall = realized[0]
    coverage = _mapping(historical["coverage"], "coverage")
    sizing = _mapping(historical["purchase_sizing"], "purchase sizing")
    _page_heading(
        data,
        _active_overlay(data),
        view="Investor Behaviour",
        title="Investor Behaviour",
        scope=(
            "Accepted FIFO-matched lots through 12 December 2025; scope and limitations precede "
            "interpretation."
        ),
    )
    st.info(
        "Gross, price-only lot analysis—not complete portfolio performance. Fees, taxes, "
        "dividends, independently reconstructed corporate actions, complete NAV, and investor "
        "intent are unavailable."
    )

    metrics = st.columns(4)
    metrics[0].metric("Realized net profit", format_inr(str(overall["net_profit"])))
    metrics[1].metric(
        "Cost-weighted return", format_percentage(str(overall["cost_weighted_return"]))
    )
    metrics[2].metric("Win rate", format_percentage(str(overall["win_rate"])))
    metrics[3].metric("Accepted lots", f"{int(str(sizing['accepted_lots'])):,}")
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-performance-summary",
            label="Historical realized-performance summary",
            origin_page="Investor Behaviour",
            company_ids=(),
            payload={
                "analysis_cutoff": historical.get("analysis_cutoff"),
                "overall_realized_performance": overall,
                "purchase_sizing": sizing,
                "scope": "accepted FIFO-matched lots; gross and price-only",
            },
        ),
        key="historical_performance_summary",
    )

    company_realized = [item for item in realized if item["company_id"] != "overall"]
    st.subheader("Realized contribution")
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
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-realized-contribution",
            label="Historical realized contribution",
            origin_page="Investor Behaviour",
            company_ids=(),
            payload={"company_realized_performance": company_realized},
        ),
        key="historical_realized_contribution",
    )

    benchmark_rows: list[dict[str, object]] = []
    for decision in data.decisions:
        benchmark = decision.historical_benchmark_context
        stock_return = benchmark.get("cost_weighted_stock_return")
        nifty_return = benchmark.get("cost_weighted_secondary_return")
        relative_return = benchmark.get("cost_weighted_secondary_relative_return")
        benchmark_rows.append(
            {
                "Company": decision.company_name,
                "Eligible realized lots": benchmark.get("eligible_lots", 0),
                "NIFTY-matched lots": benchmark.get("secondary_benchmark_matched_lots", 0),
                "Stock return": (
                    "Unavailable" if stock_return is None else format_percentage(str(stock_return))
                ),
                "NIFTY 500 TRI return": (
                    "Unavailable" if nifty_return is None else format_percentage(str(nifty_return))
                ),
                "Relative return": (
                    "Unavailable"
                    if relative_return is None
                    else format_percentage(str(relative_return))
                ),
            }
        )
    st.subheader("Historical stock and benchmark context")
    st.dataframe(benchmark_rows, hide_index=True, width="stretch")
    st.caption(
        "S&P BSE 500 TRI is the intended primary benchmark but remains unavailable. NIFTY 500 TRI "
        "is a secondary matched-period cross-check, not alpha or a decision-engine input."
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-benchmark-context",
            label="Historical stock and benchmark context",
            origin_page="Investor Behaviour",
            company_ids=tuple(item.company_id for item in data.decisions),
            payload={
                "comparisons": benchmark_rows,
                "primary_benchmark": "S&P BSE 500 TRI unavailable",
                "secondary_benchmark": "NIFTY 500 TRI contextual cross-check only",
            },
        ),
        key="historical_benchmark_context",
    )

    holding_periods = _records(historical, "holding_periods")
    winner_loser = _records(historical, "winner_loser_holding")
    st.subheader("Holding-period outcomes")
    st.dataframe(
        [
            {
                "Band": item["band"],
                "Lots": item["lots"],
                "Purchase cost": format_inr(str(item["purchase_cost"])),
                "Realized profit": format_inr(str(item["realized_profit"])),
                "Cost-weighted return": format_percentage(str(item["cost_weighted_return"])),
                "Win rate": format_percentage(str(item["win_rate"])),
                "Median holding days": item["median_days"],
            }
            for item in holding_periods
        ],
        hide_index=True,
        width="stretch",
    )
    st.dataframe(
        [
            {
                "Outcome": item["outcome"],
                "Lots": item["lots"],
                "Mean holding days": item["mean_days"],
                "Median holding days": item["median_days"],
            }
            for item in winner_loser
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Winner-versus-loser holding differences describe an observed asymmetry; they do not "
        "establish a formal disposition effect."
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-holding-periods",
            label="Historical holding-period outcomes",
            origin_page="Investor Behaviour",
            company_ids=(),
            payload={"holding_periods": holding_periods, "winner_loser_holding": winner_loser},
        ),
        key="historical_holding_periods",
    )

    open_cost = _mapping(historical["open_cost"], "open cost")
    open_companies = _records(open_cost, "companies")
    st.subheader("Purchase sizing and provisional open-cost concentration")
    sizing_metrics = st.columns(4)
    sizing_metrics[0].metric(
        "Accepted purchase cost", format_inr(str(sizing["accepted_purchase_cost"]))
    )
    sizing_metrics[1].metric(
        "Median purchase lot", format_inr(str(sizing["median_purchase_lot_cost"]))
    )
    sizing_metrics[2].metric(
        "Largest purchase lot", format_inr(str(sizing["largest_purchase_lot_cost"]))
    )
    sizing_metrics[3].metric(
        "Open-cost effective positions", f"{Decimal(str(open_cost['effective_positions'])):.2f}"
    )
    st.bar_chart(
        {
            "Company": [str(item["company"]) for item in open_companies],
            "Provisional open-cost share (%)": [
                float(Decimal(str(item["share"])) * 100) for item in open_companies
            ],
        },
        x="Company",
        y="Provisional open-cost share (%)",
        horizontal=True,
        color="#b7791f",
    )
    st.caption(
        f"Open-cost HHI {Decimal(str(open_cost['hhi'])):.3f}. These are partial cost-basis "
        "weights from provisionally open lots, not verified current portfolio weights."
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-sizing-concentration",
            label="Historical purchase sizing and open-cost concentration",
            origin_page="Investor Behaviour",
            company_ids=(),
            payload={"purchase_sizing": sizing, "provisional_open_cost": open_cost},
        ),
        key="historical_sizing_concentration",
    )

    trading_patterns = _records(historical, "trading_patterns")
    st.subheader("Inferred trading patterns")
    st.dataframe(
        [
            {
                "Company": item["company"],
                "Purchase days": item["purchase_days"],
                "Scaling buys": item["scaling_buys"],
                "Higher-rate buys": item["higher_rate"],
                "Lower-rate buys": item["lower_rate"],
                "Partial sales": item["partial_sales"],
                "Complete exits": item["complete_exits"],
                "Re-entries": item["reentries"],
                "Same-day ambiguous": item["same_day_ambiguous"],
            }
            for item in trading_patterns
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Daily groups are conservative inferences from FIFO-matched fragments, not original broker "
        "orders; they cannot by themselves establish investor intent."
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-trading-patterns",
            label="Historical inferred trading patterns",
            origin_page="Investor Behaviour",
            company_ids=(),
            payload={
                "trading_patterns": trading_patterns,
                "interpretation_boundary": (
                    "Daily groups are inferred from FIFO-matched fragments and are not "
                    "broker orders."
                ),
            },
        ),
        key="historical_trading_patterns",
    )

    st.subheader("Evidence-backed patterns")
    findings = _records(historical, "findings")
    for finding in findings:
        with st.expander(f"{finding['title']} · {str(finding['confidence']).upper()} confidence"):
            st.write(str(finding["observed"]))
            st.markdown(f"**Evidence:** {finding['evidence']}")
            st.markdown(f"**Counter-evidence:** {finding['counter_evidence']}")
            st.caption(str(finding["limitation"]))
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="historical-behaviour-findings",
            label="Historical behaviour patterns and limitations",
            origin_page="Investor Behaviour",
            company_ids=(),
            payload={
                "coverage": coverage,
                "findings": [
                    {
                        "title": item["title"],
                        "observed": item["observed"],
                        "counter_evidence": item["counter_evidence"],
                        "confidence": item["confidence"],
                        "limitation": item["limitation"],
                    }
                    for item in findings
                ],
                "interpretation_boundary": (
                    "Observed FIFO-lot patterns do not prove intent, skill, alpha, or psychology."
                ),
            },
        ),
        key="historical_behaviour",
    )

    st.subheader("Coverage and remaining limitations")
    st.info(
        f"Coverage: {coverage['realized_lots']} realized, "
        f"{coverage['provisional_open_lots']} provisional open, "
        f"{coverage['quarantined']} quarantined, and {coverage['structural']} structural rows."
    )
    st.caption(
        "Results are gross and price-only. Fees, taxes, dividends, independently reconstructed "
        "corporate actions, complete NAV, and investor intent are unavailable."
    )


def _assumptions_and_audit(data: DashboardData, overlay: HoldingsOverlay) -> None:
    _page_heading(
        data,
        overlay,
        view="Assumptions & Audit",
        title="Assumptions & Audit",
        scope=(
            "Understand the authority boundary and active session before inspecting technical "
            "identifiers."
        ),
    )
    st.subheader("Deterministic versus LLM authority")
    st.markdown(
        '<div class="flow"><span>Protected input + public evidence</span><b>→</b>'
        "<span>Deterministic analytics</span><b>→</b><span>Frozen decision</span><b>→</b>"
        "<span>Bounded question context</span><b>→</b><span>Azure explanation</span><b>→</b>"
        "<span>Validated display</span></div>",
        unsafe_allow_html=True,
    )
    st.info(
        "The LLM explains supplied facts. It cannot calculate or change scores, scenarios, "
        "weights, gates, stances, actions, or the owner disposition."
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="audit-authority-boundary",
            label="Deterministic and LLM authority boundary",
            origin_page="Assumptions & Audit",
            company_ids=(),
            payload={
                "deterministic_authority": [
                    "ingestion and historical calculations",
                    "hard gates and principle scores",
                    "valuation scenarios and portfolio weights",
                    "stances, final actions, and review state",
                ],
                "llm_authority": "explanation and synthesis of the supplied bounded context only",
                "flow": [
                    "protected input and public evidence",
                    "deterministic analytics",
                    "frozen decision",
                    "bounded question context",
                    "Azure explanation",
                    "validated display",
                ],
            },
        ),
        key="audit_authority",
    )

    st.subheader("Active session state")
    holdings_basis = (
        "supplied workbook with session entries"
        if overlay.uses_session_values
        else "supplied workbook defaults"
    )
    st.write(f"Holdings basis: **{holdings_basis}**")
    st.write(f"Available cash: **{format_inr(overlay.available_cash)}**")
    st.caption(
        "Cash source: entered for this session"
        if overlay.cash_source == "user_entered"
        else "Cash was not supplied; ₹0 is an explicit calculation assumption."
    )
    st.write(
        f"Scenario recalculations: **{len(st.session_state.get('scenario_deltas', {}))}** · "
        f"human dispositions: **{len(st.session_state.get('dispositions', {}))}** · "
        f"grounded answers: **{len(st.session_state.get('answer_cache', {}))}**"
    )
    audit = cast(list[dict[str, object]], st.session_state.get("audit_records", []))
    conversation = cast(list[AnswerArtifact], st.session_state.get("conversation_turns", []))
    download_payload = {
        "session_events": audit,
        "conversation": [_answer_audit_payload(item) for item in conversation],
        "selected_artifact_ids": sorted(st.session_state.get("selected_artifacts", {})),
    }
    st.download_button(
        "Download sanitized session audit",
        data=json.dumps(download_payload, indent=2, sort_keys=True, ensure_ascii=False),
        file_name="portfolio_intelligence_session_audit.json",
        mime="application/json",
        disabled=not audit,
    )
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="audit-active-session",
            label="Active session state",
            origin_page="Assumptions & Audit",
            company_ids=(),
            payload={
                "holdings_basis": holdings_basis,
                "holdings": [
                    {
                        "company_id": item.company_id,
                        "shares": str(item.shares),
                        "source": item.source,
                        "active_weight": str(overlay.company_weights[item.company_id]),
                    }
                    for item in overlay.holdings
                ],
                "available_cash": str(overlay.available_cash),
                "cash_source": overlay.cash_source,
                "cash_weight": str(overlay.cash_weight),
                "scenario_recalculations": len(st.session_state.get("scenario_deltas", {})),
                "human_dispositions": len(st.session_state.get("dispositions", {})),
            },
        ),
        key="audit_active_session",
    )

    st.subheader("Immutable identity and versions")
    cols = st.columns(3)
    cols[0].metric("Decision date", format_date(str(data.portfolio["decision_date"])))
    cols[1].metric("Evidence cutoff", "08 Sep 2026")
    cols[2].metric("Decision engine", str(data.portfolio["engine_version"]))
    st.write(f"Configuration version: `{data.portfolio['configuration_version']}`")
    st.markdown("**Evidence manifest hash**")
    st.code(str(data.portfolio["evidence_manifest_sha256"]), language=None)
    st.markdown("**Decision snapshot hash**")
    st.code(str(data.portfolio["snapshot_sha256"]), language=None)

    st.subheader("Runtime and memo states")
    st.write(
        "Interactive contract: `portfolio-answer-v1` · prompt: "
        "`portfolio-intelligence-prompt-v1` · deployment: `gpt-5.6-terra` · default reasoning: "
        "`low` · output limit: `2200` tokens"
    )
    memo_states = [
        {
            "Company": memo.decision.company_name,
            "Legacy memo status": memo.status.value,
            "Provider": memo.provider,
            "Deployment": memo.deployment_id,
            "Input tokens": memo.usage["input_tokens"] if memo.usage else None,
            "Output tokens": memo.usage["output_tokens"] if memo.usage else None,
        }
        for memo in data.memos
    ]
    st.dataframe(memo_states, hide_index=True, width="stretch")
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="audit-runtime-model-state",
            label="Runtime and model state",
            origin_page="Assumptions & Audit",
            company_ids=(),
            payload={
                "answer_contract": "portfolio-answer-v1",
                "prompt": "portfolio-intelligence-prompt-v1",
                "deployment": "gpt-5.6-terra",
                "reasoning_effort": "low",
                "max_output_tokens": 2200,
                "legacy_memo_states": memo_states,
            },
        ),
        key="audit_runtime",
    )

    st.subheader("Declared limitations")
    limitations = [
        str(data.portfolio["provisional_holdings_warning"]),
        *data.decisions[0].valuation_limitations,
        (
            f"Primary benchmark {data.portfolio['primary_benchmark_id']} remains "
            f"{data.portfolio['primary_benchmark_status']}."
        ),
        (
            f"{data.portfolio['secondary_benchmark_id']} is "
            f"{data.portfolio['secondary_benchmark_status']} and remains historical context only."
        ),
    ]
    for limitation in limitations:
        st.markdown(f"- {limitation}")
    _discuss_artifact_button(
        SelectedArtifact(
            artifact_id="audit-declared-limitations",
            label="Declared limitations",
            origin_page="Assumptions & Audit",
            company_ids=(),
            payload={"limitations": limitations},
        ),
        key="audit_limitations",
    )


def _active_overlay(data: DashboardData) -> HoldingsOverlay:
    cash = cast(Decimal | None, st.session_state.get("available_cash"))
    return calculate_holdings_overlay(
        data.decisions,
        share_overrides=cast(dict[str, Decimal] | None, st.session_state.get("share_overrides")),
        available_cash=cash,
    )


def _portfolio_stance(data: DashboardData) -> str:
    reviews = sum(item.final_portfolio_action == "review_required" for item in data.decisions)
    return f"{reviews} need review"


def _scenario_table(decision: DecisionMemoInput) -> list[dict[str, str]]:
    return [
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
    ]


def _render_claim(
    data: DashboardData,
    context: QuestionContext,
    claim: MemoClaim,
    *,
    claim_label: str,
    bullet: bool = False,
) -> None:
    prefix = "- " if bullet else ""
    st.markdown(prefix + claim.text)
    cards = citation_cards(data, context, claim.evidence_ids)
    with st.expander(f"Sources for this claim · {claim_label}"):
        for index, card in enumerate(cards, start=1):
            _render_citation_card(card, source_number=index)


def _render_citation_card(card: CitationCard, *, source_number: int) -> None:
    with st.container(border=True):
        st.markdown(f"**Source {source_number} · {card.display_label}**")
        st.caption(
            f"{card.provenance_class} · "
            f"{_citation_metadata_value(card.company_or_instrument_id).upper()} · "
            f"{_readable_metadata_label(card.category)}"
        )
        st.markdown("**Evidence record**")
        st.write(card.summary)
        if card.summary != card.content:
            st.caption("Complete sanitized record")
            st.code(card.content, language="json", wrap_lines=True)
        st.caption(
            "Period / observation · "
            f"{_citation_metadata_value(card.reporting_period_or_date)} · Unit · "
            f"{_citation_metadata_value(card.unit)} · Available · "
            f"{_citation_date_value(card.available_date)}"
        )
        st.caption(
            "Source · "
            f"{_citation_metadata_value(card.source_title)} · "
            f"{_readable_metadata_label(card.source_type)}"
        )
        st.caption(f"Locator · {_citation_metadata_value(card.source_locator)}")
        if card.conflicting_evidence_ids:
            st.warning(
                "Recorded conflicts · " + ", ".join(card.conflicting_evidence_ids),
                icon="⚠️",
            )
        else:
            st.caption("Recorded conflicts · None")
        st.caption(f"Audit evidence ID · `{card.evidence_id}`")


def _citation_metadata_value(value: str) -> str:
    normalized = value.strip()
    return normalized or "Not supplied in sanitized evidence"


def _readable_metadata_label(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return "Not supplied in sanitized evidence"
    return normalized.replace("_", " ").replace("-", " ").title()


def _citation_date_value(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return "Not supplied in sanitized evidence"
    return format_date(normalized)


def _record_audit(event: str, payload: dict[str, object]) -> None:
    records = cast(list[dict[str, object]], st.session_state.setdefault("audit_records", []))
    records.append(
        {"event": event, "recorded_at": datetime.now(UTC).isoformat(), "payload": payload}
    )


def _manual_claim_support_review(artifact: AnswerArtifact, *, turn_key: str) -> None:
    if not _answer_has_status(artifact, AnswerStatus.GENERATED) or artifact.answer is None:
        return
    review_id = artifact.response_id or artifact.context.context_hash
    reviews = cast(
        dict[str, dict[str, object]], st.session_state.setdefault("manual_claim_reviews", {})
    )
    existing = reviews.get(review_id)
    if existing is not None:
        st.caption(
            "Manual claim-support review · "
            f"{str(existing['verdict']).upper()} · {existing.get('note') or 'No note'}"
        )
    with st.expander("Record manual claim-support review"):
        with st.form(f"manual_claim_review_{turn_key}"):
            verdict = st.radio(
                "Evidence verdict",
                ("passed", "failed"),
                index=None,
                horizontal=True,
                key=f"manual_verdict_{turn_key}",
            )
            note = st.text_input("Review note", key=f"manual_review_note_{turn_key}")
            submitted = st.form_submit_button("Save evidence review")
        if submitted:
            if verdict is None:
                st.error("Select passed or failed before saving the evidence review.")
                return
            payload = _manual_claim_review_payload(
                artifact,
                verdict=verdict,
                note=note,
                recorded_at=datetime.now(UTC),
            )
            reviews[review_id] = payload
            _record_audit("manual_claim_support_review", payload)
            _persist_answer_audit(payload)
            st.success(f"Manual claim-support verdict recorded: {verdict.upper()}.")


def _manual_claim_review_payload(
    artifact: AnswerArtifact,
    *,
    verdict: str,
    note: str,
    recorded_at: datetime,
) -> dict[str, object]:
    if not _answer_has_status(artifact, AnswerStatus.GENERATED) or artifact.answer is None:
        raise PortfolioIntelligenceError(
            "Manual claim-support review requires a generated, validated answer."
        )
    if verdict not in {"passed", "failed"}:
        raise PortfolioIntelligenceError("Manual claim-support verdict must be passed or failed.")
    return {
        "status": "manual_claim_support_review",
        "response_id": artifact.response_id,
        "context_hash": artifact.context.context_hash,
        "verdict": verdict,
        "note": note.strip(),
        "recorded_at": recorded_at.astimezone(UTC).isoformat(),
    }


def _answer_has_status(artifact: AnswerArtifact, expected: AnswerStatus) -> bool:
    """Compare serialized session status values across Streamlit code reloads."""
    return artifact.status.value == expected.value


def _select_artifact(artifact: SelectedArtifact) -> None:
    selected = cast(
        dict[str, SelectedArtifact], st.session_state.setdefault("selected_artifacts", {})
    )
    selected[artifact.artifact_id] = artifact
    _record_audit(
        "context_selected",
        {
            "artifact_id": artifact.artifact_id,
            "label": artifact.label,
            "origin_page": artifact.origin_page,
            "company_ids": list(artifact.company_ids),
        },
    )


def _artifact_scope_label(artifact: SelectedArtifact) -> str:
    if not artifact.company_ids:
        return "portfolio / cross-company scope"
    return "company scope: " + ", ".join(company_id.upper() for company_id in artifact.company_ids)


def _discuss_artifact_button(artifact: SelectedArtifact, *, key: str) -> None:
    selected = cast(dict[str, SelectedArtifact], st.session_state.get("selected_artifacts", {}))
    is_selected = artifact.artifact_id in selected
    if st.button(
        "Added to AI context" if is_selected else "Ask AI about this",
        key=f"discuss_{key}",
        icon=":material/check:" if is_selected else ":material/add_comment:",
        disabled=is_selected,
    ):
        _select_artifact(artifact)
        st.session_state["ai_dialog_open"] = True
        st.rerun()


def _default_page_artifact(
    data: DashboardData, overlay: HoldingsOverlay, view: str
) -> SelectedArtifact:
    if view == "Company Intelligence":
        company_id = cast(str, st.session_state.get("current_company_id", "amber"))
        decision = data.decision(company_id)
        return SelectedArtifact(
            artifact_id=f"page-company-{company_id}",
            label=f"{decision.company_name} workspace",
            origin_page=view,
            company_ids=(company_id,),
            payload={
                "stance": decision.underlying_stance,
                "final_action": decision.final_portfolio_action,
                "active_weight": str(overlay.company_weights[company_id]),
                "frozen_target_weight": decision.target_weight,
                "human_review_reasons": list(decision.human_review_reasons),
            },
        )
    if view == "Investor Behaviour":
        return SelectedArtifact(
            artifact_id="page-investor-behaviour",
            label="Investor Behaviour page",
            origin_page=view,
            company_ids=(),
            payload={
                "coverage": data.historical["coverage"],
                "findings": data.historical["findings"],
            },
        )
    if view == "Assumptions & Audit":
        return SelectedArtifact(
            artifact_id="page-assumptions-audit",
            label="Assumptions and Audit page",
            origin_page=view,
            company_ids=(),
            payload={
                "authority": "deterministic calculations and decisions; LLM explanation only",
                "holdings_basis": (
                    "session_adjusted" if overlay.uses_session_values else "supplied_data"
                ),
                "cash_source": overlay.cash_source,
                "runtime": {
                    "deployment": "gpt-5.6-terra",
                    "reasoning_effort": "low",
                    "prompt": "portfolio-intelligence-prompt-v1",
                    "contract": "portfolio-answer-v1",
                },
                "primary_benchmark_status": data.portfolio["primary_benchmark_status"],
                "secondary_benchmark_status": data.portfolio["secondary_benchmark_status"],
            },
        )
    return SelectedArtifact(
        artifact_id="page-portfolio-cockpit",
        label="Portfolio Cockpit page",
        origin_page="Portfolio Cockpit",
        company_ids=(),
        payload={
            "active_weights": {
                item.company_id: str(overlay.company_weights[item.company_id])
                for item in data.decisions
            },
            "cash_weight": str(overlay.cash_weight),
            "cash_source": overlay.cash_source,
        },
    )


def _conversation_route(
    data: DashboardData,
    view: str,
    question: str,
    artifacts: tuple[SelectedArtifact, ...],
    turns: list[AnswerArtifact],
) -> tuple[QuestionScope, tuple[str, ...], ScenarioDelta | None]:
    lowered = question.lower()
    aliases = {
        "amber": "amber",
        "dilip": "dbl",
        "dbl": "dbl",
        "welspun": "welspun",
        "zee": "zee",
    }
    referenced = {company_id for alias, company_id in aliases.items() if alias in lowered}
    selected_ids = {company_id for artifact in artifacts for company_id in artifact.company_ids}
    terse_follow_up = len(question.split()) <= 5 or lowered.startswith(
        ("why", "which", "what about", "compare that", "and ")
    )
    if terse_follow_up and turns and not referenced:
        selected_ids.update(turns[-1].context.company_ids)
    selected_ids.update(referenced)
    scenario_artifact = next(
        (item for item in artifacts if item.artifact_id.endswith("scenario-delta")), None
    )
    if scenario_artifact is not None:
        company_id = scenario_artifact.company_ids[0]
        delta = cast(dict[str, ScenarioDelta], st.session_state.get("scenario_deltas", {})).get(
            company_id
        )
        if delta is None:
            raise PortfolioIntelligenceError(
                "The selected scenario result is no longer active; recalculate it before asking."
            )
        return QuestionScope.SCENARIO_DELTA, (company_id,), delta
    if view == "Investor Behaviour" or any(
        item.origin_page == "Investor Behaviour" for item in artifacts
    ):
        return QuestionScope.BEHAVIOUR, (), None
    if artifacts and not any(item.company_ids for item in artifacts):
        # A deliberately portfolio-scoped attachment remains the subject even if a
        # follow-up names one constituent. The user can remove it to switch scope.
        return QuestionScope.PORTFOLIO, (), None
    ordered = tuple(item.company_id for item in data.decisions if item.company_id in selected_ids)
    if len(ordered) == 2:
        return QuestionScope.COMPARISON, ordered, None
    if len(ordered) == 1:
        return QuestionScope.COMPANY, ordered, None
    return QuestionScope.PORTFOLIO, (), None


def _turn_predates_overlay(artifact: AnswerArtifact, overlay: HoldingsOverlay) -> bool:
    prior = artifact.context.active_portfolio
    prior_holdings = {
        str(item["company_id"]): (str(item["shares"]), str(item["source"]))
        for item in cast(list[dict[str, object]], prior.get("holdings", []))
    }
    current = {item.company_id: (str(item.shares), item.source) for item in overlay.holdings}
    return (
        prior_holdings != current
        or str(prior.get("available_cash")) != str(overlay.available_cash)
        or str(prior.get("cash_source")) != overlay.cash_source
    )


def _answer_audit_payload(artifact: AnswerArtifact) -> dict[str, object]:
    context = artifact.context
    review_id = artifact.response_id or context.context_hash
    manual_reviews = cast(
        dict[str, dict[str, object]], st.session_state.get("manual_claim_reviews", {})
    )
    return {
        "status": artifact.status.value,
        "recorded_at": datetime.now(UTC).isoformat(),
        "question": context.normalized_question,
        "scope": context.scope.value,
        "company_ids": list(context.company_ids),
        "context_hash": context.context_hash,
        "decision_snapshot_sha256": context.decision_snapshot_sha256,
        "selected_artifact_ids": [item.artifact_id for item in context.selected_artifacts],
        "included_evidence_ids": list(context.included_evidence_ids),
        "excluded_evidence_ids": list(context.excluded_evidence_ids),
        "active_portfolio": context.active_portfolio,
        "scenario_delta": context.scenario_delta,
        "provider": artifact.provider,
        "deployment_id": artifact.deployment_id,
        "reasoning_effort": artifact.reasoning_effort,
        "max_output_tokens": artifact.max_output_tokens,
        "response_id": artifact.response_id,
        "usage": (
            {
                "input_tokens": artifact.usage.input_tokens,
                "output_tokens": artifact.usage.output_tokens,
                "total_tokens": artifact.usage.total_tokens,
                "reasoning_tokens": artifact.usage.reasoning_tokens,
            }
            if artifact.usage
            else None
        ),
        "validation_error": artifact.error,
        "manual_claim_support": manual_reviews.get(review_id),
        "answer": artifact.answer.stable_payload() if artifact.answer else None,
    }


def _persist_answer_audit(payload: dict[str, object]) -> None:
    try:
        LOCAL_ANSWER_AUDIT.parent.mkdir(parents=True, exist_ok=True)
        with LOCAL_ANSWER_AUDIT.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise PortfolioIntelligenceError(
            f"Could not preserve the local answer audit at {LOCAL_ANSWER_AUDIT}: {exc}"
        ) from exc


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
        :root { --paper:#f5f1e8; --ink:#14213d; --teal:#0f766e; --amber:#b7791f;
                --risk:#a33d3d; --line:#d8d1c4; }
        .stApp { background:var(--paper); color:var(--ink); }
        [data-testid="stSidebar"] { background:#ebe5da; border-right:1px solid var(--line); }
        [data-testid="stMainBlockContainer"] { padding-top:1.35rem; }
        .brand-mark { color:var(--ink); font-size:.85rem; font-weight:800; letter-spacing:.14em; }
        h1 { color:var(--ink); font-family:Georgia,serif; letter-spacing:-.035em; }
        h2,h3,h4 { color:var(--ink); letter-spacing:-.015em; }
        .eyebrow { color:var(--teal); font-size:.76rem; font-weight:800; letter-spacing:.16em; }
        .status-strip {
          align-items:center; border-bottom:1px solid var(--line); color:#526071;
          display:flex; flex-wrap:wrap; font-size:.78rem; gap:.55rem 1.2rem;
          margin:0 0 .8rem; padding:0 0 .65rem;
        }
        .status-strip strong { color:var(--ink); letter-spacing:.12em; }
        .status-strip span { border-left:1px solid var(--line); padding-left:1.2rem; }
        [data-testid="stMetric"] { border-top:2px solid var(--ink); padding-top:.7rem; }
        [data-testid="stMetricValue"] {
          color:var(--ink); font-family:Georgia,serif; font-size:1.55rem;
          max-width:100%; min-width:0; overflow:visible !important;
          overflow-wrap:anywhere; text-overflow:clip !important; white-space:normal;
        }
        [data-testid="stMetricValue"] > div {
          display:block; line-height:1.08; max-width:100%; min-width:0;
          overflow:visible !important; overflow-wrap:anywhere;
          text-overflow:clip !important; white-space:normal !important;
        }
        .flow { display:flex; flex-wrap:wrap; gap:.55rem; align-items:center; margin:1rem 0; }
        .flow span { border-bottom:2px solid var(--teal); padding:.45rem .1rem; font-weight:600; }
        code { color:#244b47 !important; }
        p, [data-testid="stAlert"] { white-space:normal; overflow-wrap:anywhere; }
        @media (max-width:700px) {
          html,body,[data-testid="stAppViewContainer"] { max-width:100vw; overflow-x:hidden; }
          [data-testid="stMain"] { min-width:0 !important; width:100vw !important;
                                  max-width:100vw !important; overflow-x:hidden !important; }
          .block-container,[data-testid="stMainBlockContainer"],
          [data-testid="stAppViewBlockContainer"] {
            box-sizing:border-box !important; min-width:0 !important;
            width:calc(100vw - 1rem) !important; max-width:calc(100vw - 1rem) !important;
            padding-left:1rem !important; padding-right:1rem !important;
          }
          [data-testid="stHorizontalBlock"] { gap:.5rem; flex-wrap:wrap; }
          [data-testid="column"] { min-width:100% !important; width:100% !important;
                                   flex:1 1 100% !important; }
          [data-testid="stAlert"], [data-testid="stForm"],
          [data-testid="stMarkdownContainer"] { min-width:0; max-width:100%; }
          [data-testid="stMetricValue"] { font-size:1.25rem; }
          .status-strip { gap:.35rem .75rem; margin-bottom:.55rem; }
          .status-strip strong { flex:0 0 100%; }
          .status-strip span { border-left:0; padding-left:0; }
          .flow { display:block; }
          .flow span,.flow b { display:block; margin:.4rem 0; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
