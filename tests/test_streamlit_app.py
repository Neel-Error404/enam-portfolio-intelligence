import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from enam_assessment.intelligence import (
    ANSWER_CONTRACT_VERSION,
    ANSWER_PROMPT_VERSION,
    AnswerArtifact,
    AnswerStatus,
    GroundedAnswer,
    QuestionScope,
    build_question_context,
)
from enam_assessment.memo import MemoClaim
from enam_assessment.portfolio_ui import load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]


def _app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()


def _navigate(app: AppTest, view: str) -> AppTest:
    return next(item for item in app.radio if item.label == "Workspace").set_value(view).run()


def test_first_viewport_is_portfolio_cockpit_with_verification_state() -> None:
    app = _app()

    assert not app.exception
    assert app.title[0].value == "Portfolio Cockpit"
    assert any(item.label == "Ask AI about this page" for item in app.button)
    assert any(item.label == "Ask Portfolio Intelligence" for item in app.button)
    labels = {item.label for item in app.metric}
    assert {
        "Represented capital",
        "Available cash",
        "Top two",
        "HHI",
        "Residual target cash",
        "Target bear-risk exposure",
        "Risky-sleeve top two",
        "Risky-sleeve top three",
        "Risky-sleeve HHI",
        "Effective risky positions",
    } <= labels
    assert any("provisional" in item.value.lower() for item in app.warning)
    assert any(item.label == "Review or adjust portfolio values" for item in app.expander)
    assert any("Cash was not supplied" in item.value for item in app.info)


def test_cockpit_preserves_stance_action_and_target_separately() -> None:
    app = _app()

    assert not app.exception
    table = app.dataframe[0].value
    assert "SELL" in table["Stance"].tolist()
    assert "REVIEW_REQUIRED" in table["Portfolio action"].tolist()
    assert "HOLD" in table["Portfolio action"].tolist()
    assert "Frozen target" in table.columns


def test_all_four_views_load_and_benchmarks_remain_audit_context() -> None:
    for view in (
        "Portfolio Cockpit",
        "Company Intelligence",
        "Investor Behaviour",
        "Assumptions & Audit",
    ):
        app = _navigate(_app(), view)
        assert not app.exception
        assert any(item.value == view for item in app.title)
        assert any(item.label == "Ask AI about this page" for item in app.button)
        assert any(item.label == "Ask Portfolio Intelligence" for item in app.button)

    app = _navigate(_app(), "Assumptions & Audit")
    text = " ".join(item.value for item in (*app.markdown, *app.info))
    assert "bse-500-tri" in text
    assert "nifty-500-tri" in text
    assert "historical context only" in text


def test_all_companies_are_selectable_and_show_connected_decision_workspace() -> None:
    app = _app()
    app = _navigate(app, "Company Intelligence")
    company_actions = {
        "Amber Enterprises India Limited": "REVIEW_REQUIRED",
        "Dilip Buildcon Limited": "REVIEW_REQUIRED",
        "Welspun Living Limited": "HOLD",
        "Zee Entertainment Enterprises Limited": "HOLD",
    }

    for company_name, expected_action in company_actions.items():
        app.selectbox[0].set_value(company_name).run()
        assert not app.exception
        metric_labels = {item.label for item in app.metric}
        assert {
            "Underlying stance",
            "Final portfolio action",
            "Active represented weight",
            "Frozen target",
        } <= metric_labels
        actions = {item.label: item.value for item in app.metric}
        assert actions["Final portfolio action"] == expected_action
        subheaders = {item.value for item in app.subheader}
        assert {
            "Investment principles",
            "Hard gates",
            "Three-year valuation scenarios",
            "Historical benchmark context",
            "Scenario Lab",
            "Owner disposition",
        } <= subheaders
        assert any(item.label == "Ask AI about this page" for item in app.button)
        scenario_text = str(app.dataframe[2].value)
        assert (
            scenario_text.index("Bear") < scenario_text.index("Base") < scenario_text.index("Bull")
        )
        benchmark_text = " ".join(item.value for item in app.info)
        assert "S&P BSE 500 TRI remains unavailable" in benchmark_text
        assert "NIFTY 500 TRI is a secondary historical cross-check only" in benchmark_text


def test_investor_behaviour_shows_required_historical_analysis_sections() -> None:
    app = _navigate(_app(), "Investor Behaviour")

    assert not app.exception
    subheaders = {item.value for item in app.subheader}
    assert {
        "Realized contribution",
        "Historical stock and benchmark context",
        "Holding-period outcomes",
        "Purchase sizing and provisional open-cost concentration",
        "Inferred trading patterns",
        "Evidence-backed patterns",
        "Coverage and remaining limitations",
    } <= subheaders
    captions = " ".join(item.value for item in app.caption)
    assert "do not establish a formal disposition effect" in captions
    assert "not verified current portfolio weights" in captions
    assert "not original broker orders" in captions
    assert "S&P BSE 500 TRI is the intended primary benchmark but remains unavailable" in captions


def test_company_comparison_displays_deterministic_side_by_side_values() -> None:
    app = _app()

    assert not app.exception
    comparison = app.dataframe[-1].value
    assert {
        "Company",
        "Active weight",
        "Frozen target",
        "Stance",
        "Portfolio action",
        "Principle score",
        "Base CAGR",
        "Failed or unknown gates",
    } <= set(comparison.columns)
    assert len(comparison) == 2


def test_missing_live_configuration_is_explicit_and_deterministic_view_survives(
    monkeypatch: object,
) -> None:
    from _pytest.monkeypatch import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    for name in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    app = _app()
    app = _navigate(app, "Company Intelligence")
    next(item for item in app.button if item.label == "Ask AI about this page").click().run()
    next(item for item in app.text_area if item.label == "Ask a grounded question").set_value(
        "Why is Amber review required?"
    )
    ask_button = [item for item in app.button if item.label == "Ask Portfolio Intelligence"][-1]
    ask_button.click().run()

    assert not app.exception
    assert any("portfolio intelligence is unavailable" in item.value.lower() for item in app.info)
    assert any(item.label == "Final portfolio action" for item in app.metric)


def test_validated_answer_and_citation_card_render_from_session_artifact() -> None:
    data = load_dashboard_data(ROOT)
    context = build_question_context(
        data,
        scope=QuestionScope.COMPANY,
        question="Why is Amber review required?",
        company_ids=("amber",),
    )
    claim = MemoClaim(
        "The frozen action requires review because the working holding is provisional.",
        ("decision:amber",),
        "deterministic_explanation",
    )
    answer = GroundedAnswer(
        scope=context.scope,
        company_ids=context.company_ids,
        decision_snapshot_sha256=context.decision_snapshot_sha256,
        context_hash=context.context_hash,
        answer_contract_version=ANSWER_CONTRACT_VERSION,
        prompt_version=ANSWER_PROMPT_VERSION,
        direct_answer=claim,
        sections={
            "supporting_points": (claim,),
            "counterpoints": (),
            "relevant_unknowns": (),
            "change_conditions": (),
        },
    )
    artifact = AnswerArtifact(
        status=AnswerStatus.GENERATED,
        context=context,
        provider="fake",
        deployment_id="fake-test",
        reasoning_effort="low",
        max_output_tokens=2200,
        answer=answer,
        response_id="fake-response",
        usage=None,
        error=None,
    )
    app = _app()
    app.session_state["conversation_turns"] = [artifact]
    app.session_state["ai_dialog_open"] = True
    app = _navigate(app, "Company Intelligence")

    assert not app.exception
    assert any("working holding is provisional" in item.value for item in app.markdown)
    assert any(item.label == "Open cited evidence" for item in app.expander)
    claim_source_controls = [
        item for item in app.expander if item.label.startswith("Sources for this claim")
    ]
    assert {item.label for item in claim_source_controls} == {
        "Sources for this claim · Current view",
        "Sources for this claim · Principal support 1",
    }
    rendered = " ".join(item.value for item in app.markdown)
    assert "Source 1 · Frozen Amber decision" in rendered
    assert "working holding is provisional" in rendered
    captions = " ".join(item.value for item in app.caption)
    assert "Frozen decision record" in captions
    assert "Frozen company decision snapshot" in captions
    assert "decision/decision_snapshot.json:amber" in captions
    assert "Audit evidence ID · `decision:amber`" in captions
    assert "Original-source URL" not in rendered
    assert "fake-test" not in " ".join(item.value for item in app.markdown)


def test_missing_optional_citation_metadata_is_disclosed_without_a_broken_link() -> None:
    import app as streamlit_app

    assert streamlit_app._citation_metadata_value("") == "Not supplied in sanitized evidence"
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Open original source" not in source


def test_failed_answer_states_do_not_render_untrusted_narrative() -> None:
    data = load_dashboard_data(ROOT)
    context = build_question_context(
        data,
        scope=QuestionScope.COMPANY,
        question="Why is Amber review required?",
        company_ids=("amber",),
    )
    for status in (AnswerStatus.GENERATION_FAILED, AnswerStatus.VALIDATION_FAILED):
        app = _app()
        app.session_state["conversation_turns"] = [
            AnswerArtifact(
                status=status,
                context=context,
                provider="fake",
                deployment_id="fake-test",
                reasoning_effort="low",
                max_output_tokens=2200,
                answer=None,
                response_id=None,
                usage=None,
                error="Synthetic failure.",
            )
        ]
        app.session_state["ai_dialog_open"] = True
        app = _navigate(app, "Company Intelligence")

        assert not app.exception
        notices = [item.value for item in (*app.warning, *app.error)]
        assert any(status.value.replace("_", " ") in item for item in notices)
        assert not any("working holding is provisional" in item.value for item in app.markdown)


def test_audit_view_discloses_authority_runtime_and_session_download() -> None:
    app = _app()
    app = _navigate(app, "Assumptions & Audit")

    assert not app.exception
    text = " ".join(item.value for item in (*app.markdown, *app.info))
    assert "The LLM explains supplied facts" in text
    assert "portfolio-answer-v1" in text
    assert "portfolio-intelligence-prompt-v1" in text
    assert "gpt-5.6-terra" in text
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.download_button(\n        "Download sanitized session audit"' in source


def test_app_has_no_automatic_provider_call_at_module_load() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "responses.create" not in source
    assert "build_company_memos" not in source
    assert "if not submitted:" in source
    assert "get_or_generate_answer" in source


def test_shared_context_persists_across_navigation_without_calling_provider() -> None:
    app = _app()
    discuss_page = next(item for item in app.button if item.label == "Ask AI about this page")
    app = discuss_page.click().run()

    assert "page-portfolio-cockpit" in app.session_state["selected_artifacts"]
    assert len(app.get("dialog")) == 1
    assert any(item.label == "Ask a grounded question" for item in app.text_area)
    assert not app.session_state["conversation_turns"]
    app = _navigate(app, "Investor Behaviour")
    captions = " ".join(item.value for item in app.caption)
    assert "Portfolio Cockpit page" in captions
    assert "Portfolio Cockpit" in captions
    assert not app.session_state["conversation_turns"]


def test_shared_dialog_opens_from_compact_launcher_without_provider_call() -> None:
    app = _app()
    launcher = next(item for item in app.button if item.label == "Ask Portfolio Intelligence")
    app = launcher.click().run()

    assert not app.exception
    assert len(app.get("dialog")) == 1
    assert any(item.label == "Ask a grounded question" for item in app.text_area)
    assert not app.session_state["conversation_turns"]
    assert not app.session_state["selected_artifacts"]


def test_explicit_portfolio_and_behaviour_artifacts_control_follow_up_scope() -> None:
    import app as streamlit_app

    data = load_dashboard_data(ROOT)
    portfolio_artifact = streamlit_app.SelectedArtifact(
        artifact_id="portfolio-summary-concentration",
        label="Portfolio summary and concentration",
        origin_page="Portfolio Cockpit",
        company_ids=(),
        payload={"focus": "concentration"},
    )
    behaviour_artifact = streamlit_app.SelectedArtifact(
        artifact_id="historical-behaviour-findings",
        label="Evidence-backed behaviour patterns",
        origin_page="Investor Behaviour",
        company_ids=(),
        payload={"focus": "behaviour"},
    )

    portfolio_scope, portfolio_ids, _ = streamlit_app._conversation_route(
        data,
        "Portfolio Cockpit",
        "How did my change to Amber shares alter the active portfolio?",
        (portfolio_artifact,),
        [],
    )
    behaviour_scope, behaviour_ids, _ = streamlit_app._conversation_route(
        data,
        "Company Intelligence",
        "How should this affect Zee?",
        (behaviour_artifact,),
        [],
    )

    assert (portfolio_scope, portfolio_ids) == (QuestionScope.PORTFOLIO, ())
    assert (behaviour_scope, behaviour_ids) == (QuestionScope.BEHAVIOUR, ())


def test_section_context_actions_cover_required_analytical_artifacts() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    required_artifacts = {
        "portfolio-summary-concentration",
        "portfolio-allocation",
        "portfolio-priority-decisions",
        "historical-performance-summary",
        "historical-realized-contribution",
        "historical-benchmark-context",
        "historical-holding-periods",
        "historical-sizing-concentration",
        "historical-trading-patterns",
        "historical-behaviour-findings",
        "audit-authority-boundary",
        "audit-active-session",
        "audit-runtime-model-state",
        "audit-declared-limitations",
    }
    required_dynamic_suffixes = {
        "-decision-summary",
        "-investment-principles",
        "-valuation-scenarios",
        "-evidence-balance",
        "-change-conditions",
        "-historical-benchmark",
        "-scenario-delta",
    }

    for artifact_id in required_artifacts:
        assert f'artifact_id="{artifact_id}"' in source
    for suffix in required_dynamic_suffixes:
        assert f'company_id}}{suffix}"' in source
    assert "build_hard_gates_artifact(data, company_id)" in source
    assert 'artifact_id="comparison-"' in source
    assert '"Discuss this"' not in source
    assert '"Ask AI about this"' in source


def test_page_hierarchy_places_hard_gates_before_principles_and_hashes_after_authority() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    company_start = source.index("def _company_intelligence")
    company_end = source.index("def _scenario_lab")
    company_source = source[company_start:company_end]
    assert company_source.index('st.subheader("Hard gates")') < company_source.index(
        'st.subheader("Investment principles")'
    )

    audit_start = source.index("def _assumptions_and_audit")
    audit_end = source.index("def _active_overlay")
    audit_source = source[audit_start:audit_end]
    assert audit_source.index(
        'st.subheader("Deterministic versus LLM authority")'
    ) < audit_source.index('st.subheader("Immutable identity and versions")')


def test_responsive_styles_wrap_long_statuses_and_compact_the_mobile_header() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "overflow-wrap:anywhere" in source
    assert "white-space:normal !important" in source
    assert "@media (max-width:700px)" in source
    assert ".status-strip" in source


def test_manual_claim_support_review_payload_is_validated_and_auditable() -> None:
    import app as streamlit_app

    data = load_dashboard_data(ROOT)
    context = build_question_context(
        data,
        scope=QuestionScope.COMPANY,
        question="Why is Amber review required?",
        company_ids=("amber",),
    )
    claim = MemoClaim("Grounded explanation.", ("decision:amber",), "explanation")
    answer = GroundedAnswer(
        scope=context.scope,
        company_ids=context.company_ids,
        decision_snapshot_sha256=context.decision_snapshot_sha256,
        context_hash=context.context_hash,
        answer_contract_version=ANSWER_CONTRACT_VERSION,
        prompt_version=ANSWER_PROMPT_VERSION,
        direct_answer=claim,
        sections={
            "supporting_points": (),
            "counterpoints": (),
            "relevant_unknowns": (),
            "change_conditions": (),
        },
    )
    artifact = AnswerArtifact(
        status=AnswerStatus.GENERATED,
        context=context,
        provider="fake",
        deployment_id="fake-test",
        reasoning_effort="low",
        max_output_tokens=2200,
        answer=answer,
        response_id="resp-review",
        usage=None,
        error=None,
    )
    recorded_at = datetime(2026, 9, 10, 9, 30, tzinfo=UTC)

    payload = streamlit_app._manual_claim_review_payload(
        artifact,
        verdict="passed",
        note=" Citations support the material claims. ",
        recorded_at=recorded_at,
    )

    assert payload == {
        "status": "manual_claim_support_review",
        "response_id": "resp-review",
        "context_hash": context.context_hash,
        "verdict": "passed",
        "note": "Citations support the material claims.",
        "recorded_at": "2026-09-10T09:30:00+00:00",
    }
    with pytest.raises(Exception, match="verdict must be passed or failed"):
        streamlit_app._manual_claim_review_payload(
            artifact,
            verdict="maybe",
            note="",
            recorded_at=recorded_at,
        )


def test_manual_claim_support_review_has_no_optimistic_default() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert (
        '"Evidence verdict",\n                ("passed", "failed"),\n                index=None,'
        in source
    )
    assert "Select passed or failed before saving the evidence review." in source


def test_answer_status_comparison_survives_streamlit_module_reload() -> None:
    import app as streamlit_app

    data = load_dashboard_data(ROOT)
    context = build_question_context(
        data,
        scope=QuestionScope.COMPANY,
        question="Why is Amber review required?",
        company_ids=("amber",),
    )
    artifact = AnswerArtifact(
        status=AnswerStatus.GENERATED,
        context=context,
        provider="fake",
        deployment_id="fake-test",
        reasoning_effort="low",
        max_output_tokens=2200,
        answer=None,
        response_id=None,
        usage=None,
        error=None,
    )

    assert streamlit_app._answer_has_status(artifact, AnswerStatus.GENERATED)
    assert not streamlit_app._answer_has_status(artifact, AnswerStatus.GENERATION_FAILED)


def test_supplied_defaults_are_active_without_confirmation_and_reset_is_non_destructive() -> None:
    app = _app()
    assert "share_overrides" not in app.session_state
    assert "available_cash" not in app.session_state
    values = {item.label: item.value for item in app.metric}
    assert values["Represented capital"] != "₹0"
    assert values["Available cash"] == "₹0.00"
    assert any(item.label == "Apply session values" for item in app.button)


def test_sanitized_answer_audit_survives_session_end(tmp_path: Path, monkeypatch: object) -> None:
    from _pytest.monkeypatch import MonkeyPatch

    import app as streamlit_app

    assert isinstance(monkeypatch, MonkeyPatch)
    audit_path = tmp_path / "live_answer_audit.jsonl"
    monkeypatch.setattr(streamlit_app, "LOCAL_ANSWER_AUDIT", audit_path)
    payload = {
        "status": "validation_failed",
        "response_id": "resp-test",
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        "validation_error": "Synthetic citation failure.",
    }

    streamlit_app._persist_answer_audit(payload)

    persisted = json.loads(audit_path.read_text(encoding="utf-8"))
    assert persisted == payload
