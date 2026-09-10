from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def _app() -> AppTest:
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()


def _navigate(app: AppTest, view: str) -> AppTest:
    return next(item for item in app.radio if item.label == "Workspace").set_value(view).run()


def test_verify_investigate_scenario_and_disposition_workflow() -> None:
    app = _app()
    next(item for item in app.number_input if item.label.startswith("Amber")).set_value(0.0)
    next(item for item in app.number_input if item.label.startswith("Available cash")).set_value(
        1_000_000.0
    )
    app = next(item for item in app.button if item.label == "Apply session values").click().run()

    assert not app.exception
    assert any("Session-adjusted holdings" in item.value for item in app.markdown)
    assert app.session_state["share_overrides"]["amber"] == 0

    app = _navigate(app, "Company Intelligence")
    next(item for item in app.number_input if item.label == "Revenue growth (%)").set_value(20.0)
    app = next(item for item in app.button if item.label == "Recalculate scenario").click().run()

    assert not app.exception
    metrics = {item.label: item for item in app.metric}
    assert metrics["Frozen base target"].value != metrics["Sandbox target"].value
    assert "scenario_deltas" in app.session_state

    app = next(item for item in app.button if item.label == "Record disposition").click().run()
    assert any("engine action remains REVIEW_REQUIRED" in item.value for item in app.success)
    assert app.session_state["dispositions"]["amber"].engine_action == "review_required"
    assert len(app.session_state["audit_records"]) == 3


def test_reset_restores_calculated_provisional_holdings() -> None:
    app = _app()
    app.session_state["share_overrides"] = {"amber": 0}
    app.session_state["available_cash"] = 1_000_000
    app = app.run()
    app = (
        next(item for item in app.button if item.label == "Reset to supplied-data defaults")
        .click()
        .run()
    )

    assert not app.exception
    assert any("Supplied-data holdings" in item.value for item in app.markdown)
    assert "share_overrides" not in app.session_state
    assert "available_cash" not in app.session_state
