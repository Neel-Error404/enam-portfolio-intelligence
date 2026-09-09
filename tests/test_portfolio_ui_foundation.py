import json
import shutil
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from enam_assessment.errors import UIArtifactError
from enam_assessment.memo_generation import MemoStatus
from enam_assessment.portfolio_ui import (
    allocation_rows,
    format_date,
    format_inr,
    format_percentage,
    load_dashboard_data,
    memo_state_presentation,
    ordered_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_loads_and_cross_validates_local_artifacts() -> None:
    data = load_dashboard_data(ROOT)

    assert [item.company_id for item in data.decisions] == [
        "amber",
        "dbl",
        "welspun",
        "zee",
    ]
    statuses = {item.decision.company_id: item.status for item in data.memos}
    assert statuses == {
        "amber": MemoStatus.VALIDATION_FAILED,
        "dbl": MemoStatus.GENERATION_FAILED,
        "welspun": MemoStatus.GENERATION_FAILED,
        "zee": MemoStatus.GENERATION_FAILED,
    }
    assert data.portfolio["snapshot_sha256"] == (
        "014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89"
    )


def test_missing_and_malformed_artifacts_raise_actionable_errors(tmp_path: Path) -> None:
    with pytest.raises(UIArtifactError, match="Required application artifact is missing"):
        load_dashboard_data(tmp_path)

    copied = _copy_artifacts(tmp_path)
    (copied / "memos" / "company_memos.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(UIArtifactError, match="Cannot read memo artifact"):
        load_dashboard_data(copied)


def test_allocation_view_model_preserves_stance_action_and_frozen_weights() -> None:
    data = load_dashboard_data(ROOT)
    rows = {item.company_id: item for item in allocation_rows(data)}

    assert rows["amber"].current_weight == Decimal("0.4832845796910237618442504735")
    assert rows["amber"].target_weight == Decimal("0.1430883218084060355312658397")
    assert rows["amber"].underlying_stance == "sell"
    assert rows["amber"].final_action == "review_required"
    assert rows["zee"].underlying_stance == "sell"
    assert rows["zee"].final_action == "hold"


def test_formatters_are_consistent_and_explicit() -> None:
    assert format_percentage("0.2534") == "25.3%"
    assert format_percentage(Decimal("-0.039"), places=1) == "-3.9%"
    assert format_inr("369329877") == "₹36.93 cr"
    assert format_inr("404625.50") == "₹4.05 lakh"
    assert format_date("2026-09-08") == "08 Sep 2026"
    assert format_date(date(2025, 12, 12)) == "12 Dec 2025"


def test_scenarios_are_presented_in_bear_base_bull_order() -> None:
    decision = load_dashboard_data(ROOT).decision("amber")

    scenarios = ordered_scenarios(decision)

    assert [item["input"]["name"] for item in scenarios] == ["bear", "base", "bull"]


def test_memo_states_have_visible_text_labels() -> None:
    data = load_dashboard_data(ROOT)
    memo = data.memo("amber")
    expected = {
        MemoStatus.GENERATED: ("Validated portfolio intelligence", "positive"),
        MemoStatus.NOT_CONFIGURED: ("Commentary not configured", "neutral"),
        MemoStatus.GENERATION_FAILED: ("Commentary generation failed", "warning"),
        MemoStatus.VALIDATION_FAILED: ("Commentary validation failed", "risk"),
    }

    for status, (label, tone) in expected.items():
        state = memo_state_presentation(replace(memo, status=status))
        assert state.label == label
        assert state.tone == tone


def test_citation_metadata_is_resolved_from_the_normalized_snapshot() -> None:
    data = load_dashboard_data(ROOT)
    amber = data.decision("amber")
    evidence = data.evidence_by_company["amber"]

    assert {item.evidence_id for item in evidence} == set(amber.evidence_ids)
    assert all(item.source_title and item.source_type for item in evidence)
    assert all(item.available_date <= amber.decision_date for item in evidence)


def test_generated_memo_is_revalidated_and_fake_provider_remains_labelled(
    tmp_path: Path,
) -> None:
    copied = _copy_artifacts(tmp_path)
    memo_path = copied / "memos" / "company_memos.json"
    raw = json.loads(memo_path.read_text(encoding="utf-8"))
    amber = next(item for item in raw["companies"] if item["decision"]["company_id"] == "amber")
    amber["memo_generation_status"] = "generated"
    amber["provider"] = "fake"
    amber["deployment_id"] = "fake-structured-model"
    amber["narrative"] = json.loads(
        (ROOT / "tests" / "fixtures" / "validated_memo_amber.json").read_text(encoding="utf-8")
    )
    amber["error"] = None
    memo_path.write_text(json.dumps(raw), encoding="utf-8")

    data = load_dashboard_data(copied)

    assert data.memo("amber").status is MemoStatus.GENERATED
    assert data.memo("amber").provider == "fake"
    assert data.memo("amber").narrative is not None

    amber["narrative"]["executive_summary"]["evidence_ids"] = ["not-allowed"]
    memo_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(UIArtifactError, match="outside the allow-list"):
        load_dashboard_data(copied)


def _copy_artifacts(destination: Path) -> Path:
    for directory in ("decision", "evidence", "memos"):
        (destination / directory).mkdir(parents=True, exist_ok=True)
    for relative in (
        Path("decision/decision_snapshot.json"),
        Path("evidence/normalized_snapshot.json"),
        Path("evidence/historical_analysis_summary.json"),
        Path("memos/company_memos.json"),
    ):
        shutil.copy2(ROOT / relative, destination / relative)
    return destination
