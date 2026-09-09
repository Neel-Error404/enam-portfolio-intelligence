from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def _app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()


def test_first_viewport_and_investor_behaviour_load() -> None:
    app = _app()

    assert not app.exception
    assert app.title[0].value == "Portfolio Intelligence"
    assert any("Decision date" in item.label for item in app.metric)
    assert any("provisional" in item.value.lower() for item in app.warning)
    assert any(item.value == "Investor Behaviour" for item in app.header)
    assert any("Realized net profit" == item.label for item in app.metric)


def test_current_portfolio_view_preserves_stance_and_action() -> None:
    app = _app()
    app.radio[0].set_value("Current Portfolio").run()

    assert not app.exception
    assert any(item.value == "Current Portfolio" for item in app.header)
    table = app.dataframe[0].value
    assert "SELL" in table["Stance"].tolist()
    assert "REVIEW_REQUIRED" in table["Portfolio action"].tolist()
    assert "HOLD" in table["Portfolio action"].tolist()


def test_all_companies_are_selectable_and_show_decision_sections() -> None:
    app = _app()
    app.radio[0].set_value("Company Intelligence").run()
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
        assert {"Stance", "Portfolio action", "Current weight", "Target weight"} <= metric_labels
        decision_labels = " ".join(item.value for item in app.markdown)
        assert f"final portfolio action `{expected_action}`" in decision_labels
        subheaders = {item.value for item in app.subheader}
        assert "Six investment principles" in subheaders
        assert "Hard gates" in subheaders
        assert "Three-year valuation scenarios" in subheaders
        assert "Portfolio intelligence memo" in subheaders
        scenario_text = str(app.dataframe[2].value)
        assert (
            scenario_text.index("Bear") < scenario_text.index("Base") < scenario_text.index("Bull")
        )


def test_memo_failure_and_citations_are_visible_without_fake_live_content() -> None:
    app = _app()
    app.radio[0].set_value("Company Intelligence").run()

    assert any("Commentary validation failed" in item.value for item in app.error)
    assert any(item.label == "Citation details" for item in app.expander)
    visible = " ".join(item.value for item in app.markdown)
    assert "fake-structured-model" not in visible


def test_assumptions_and_audit_view_discloses_authority_and_benchmarks() -> None:
    app = _app()
    app.radio[0].set_value("Assumptions & Audit").run()

    assert not app.exception
    text = " ".join(item.value for item in (*app.markdown, *app.info))
    assert "The LLM explains a frozen result" in text
    assert "bse-500-tri" in text
    assert "nifty-500-tri" in text
    assert "company-memo-v1" in text
    assert "company-memo-prompt-v1" in text


def test_app_source_has_no_model_call_path() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "AzureOpenAIResponsesProvider" not in source
    assert "responses.create" not in source
    assert "build_company_memos" not in source
