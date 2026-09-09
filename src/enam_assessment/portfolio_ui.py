"""Pure loading, validation, and presentation helpers for the Streamlit UI."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from .errors import EvidenceValidationError, MemoContextError, MemoValidationError, UIArtifactError
from .evidence_io import read_snapshot
from .memo import (
    MEMO_CONTRACT_VERSION,
    PROMPT_VERSION,
    DecisionMemoInput,
    GeneratedMemoNarrative,
    MemoContext,
    MemoEvidenceItem,
    build_memo_context,
    parse_and_validate_memo_response,
    read_decision_memo_inputs,
)
from .memo_generation import MemoStatus


@dataclass(frozen=True, slots=True)
class AllocationRow:
    """Display-ready allocation values copied from the deterministic snapshot."""

    company_id: str
    company_name: str
    current_weight: Decimal
    target_weight: Decimal
    underlying_stance: str
    final_action: str
    human_review_required: bool
    bear_portfolio_at_risk: Decimal


@dataclass(frozen=True, slots=True)
class MemoStatePresentation:
    """Accessible label and message for one explicit memo state."""

    label: str
    tone: str
    message: str


@dataclass(frozen=True, slots=True)
class LoadedMemoArtifact:
    """Validated persisted memo metadata and optional narrative."""

    status: MemoStatus
    decision: DecisionMemoInput
    provider: str
    deployment_id: str
    reasoning_effort: str
    max_output_tokens: int
    narrative: GeneratedMemoNarrative | None
    response_id: str | None
    usage: dict[str, int | None] | None
    error: str | None


@dataclass(frozen=True, slots=True)
class DashboardData:
    """All immutable local artifacts required by the four Streamlit views."""

    decisions: tuple[DecisionMemoInput, ...]
    memos: tuple[LoadedMemoArtifact, ...]
    evidence_by_company: dict[str, tuple[MemoEvidenceItem, ...]]
    historical: dict[str, object]
    portfolio: dict[str, object]

    def decision(self, company_id: str) -> DecisionMemoInput:
        for item in self.decisions:
            if item.company_id == company_id:
                return item
        raise UIArtifactError(f"No decision is available for company {company_id!r}.")

    def memo(self, company_id: str) -> LoadedMemoArtifact:
        for item in self.memos:
            if item.decision.company_id == company_id:
                return item
        raise UIArtifactError(f"No memo state is available for company {company_id!r}.")


def load_dashboard_data(root: Path) -> DashboardData:
    """Load and cross-validate only sanitized structured application artifacts."""
    decision_path = root / "decision" / "decision_snapshot.json"
    memo_path = root / "memos" / "company_memos.json"
    evidence_path = root / "evidence" / "normalized_snapshot.json"
    historical_path = root / "evidence" / "historical_analysis_summary.json"
    for path in (decision_path, memo_path, evidence_path, historical_path):
        if not path.is_file():
            raise UIArtifactError(
                f"Required application artifact is missing: {path}. Rebuild the documented "
                "offline artifacts before starting Streamlit."
            )
    try:
        decisions = read_decision_memo_inputs(decision_path)
        evidence = read_snapshot(evidence_path)
        decision_root = _read_object(decision_path, "decision snapshot")
        historical = _read_object(historical_path, "historical analysis summary")
        contexts = {item.company_id: build_memo_context(item, evidence) for item in decisions}
        memos = _read_memos(memo_path, decisions, contexts)
        portfolio = {
            key: decision_root[key]
            for key in (
                "companies",
                "cash_target_weight",
                "current_concentration",
                "target_concentration",
                "target_bear_portfolio_at_risk",
                "primary_benchmark_id",
                "primary_benchmark_status",
                "secondary_benchmark_id",
                "secondary_benchmark_status",
                "evidence_manifest_sha256",
                "snapshot_sha256",
                "engine_version",
                "configuration_version",
                "decision_date",
                "provisional_holdings_warning",
            )
        }
    except (
        EvidenceValidationError,
        KeyError,
        MemoContextError,
        MemoValidationError,
        TypeError,
        ValueError,
    ) as exc:
        raise UIArtifactError(f"Application artifacts are inconsistent: {exc}") from exc
    return DashboardData(
        decisions=decisions,
        memos=memos,
        evidence_by_company={
            company_id: context.evidence for company_id, context in contexts.items()
        },
        historical=historical,
        portfolio=portfolio,
    )


def allocation_rows(data: DashboardData) -> tuple[AllocationRow, ...]:
    """Copy current and target values without recomputing investment outputs."""
    rows: list[AllocationRow] = []
    for decision in data.decisions:
        company_payload = company_snapshot_payload(data, decision.company_id)
        rows.append(
            AllocationRow(
                company_id=decision.company_id,
                company_name=decision.company_name,
                current_weight=_decimal(decision.working_current_weight, "current weight"),
                target_weight=_decimal(decision.target_weight, "target weight"),
                underlying_stance=decision.underlying_stance,
                final_action=decision.final_portfolio_action,
                human_review_required=decision.human_review_required,
                bear_portfolio_at_risk=_decimal(
                    _string(
                        company_payload,
                        "position_bear_portfolio_at_risk",
                        decision.company_id,
                    ),
                    "bear portfolio-at-risk",
                ),
            )
        )
    return tuple(rows)


def ordered_scenarios(decision: DecisionMemoInput) -> tuple[dict[str, object], ...]:
    """Return persisted scenarios in semantic bear/base/bull order without recalculation."""
    order = {"bear": 0, "base": 1, "bull": 2}
    try:
        result = tuple(
            sorted(
                decision.scenarios,
                key=lambda item: order[_scenario_name(item)],
            )
        )
    except KeyError as exc:
        raise UIArtifactError(
            f"{decision.company_id}: scenarios must be bear, base, and bull."
        ) from exc
    if tuple(_scenario_name(item) for item in result) != ("bear", "base", "bull"):
        raise UIArtifactError(
            f"{decision.company_id}: scenarios must contain bear, base, and bull exactly once."
        )
    return result


def memo_state_presentation(memo: LoadedMemoArtifact) -> MemoStatePresentation:
    """Map memo state to text and a CSS tone; colour is never the only signal."""
    if memo.status is MemoStatus.GENERATED:
        return MemoStatePresentation(
            "Validated portfolio intelligence",
            "positive",
            "The narrative passed schema, identity, temporal, and citation allow-list checks.",
        )
    if memo.status is MemoStatus.NOT_CONFIGURED:
        return MemoStatePresentation(
            "Commentary not configured",
            "neutral",
            "The deterministic analysis remains available; Azure memo generation is not "
            "configured.",
        )
    if memo.status is MemoStatus.GENERATION_FAILED:
        return MemoStatePresentation(
            "Commentary generation failed",
            "warning",
            memo.error or "The provider did not return a usable response.",
        )
    return MemoStatePresentation(
        "Commentary validation failed",
        "risk",
        "The model response failed schema or evidence validation and is not shown as trusted "
        "content.",
    )


def format_percentage(value: Decimal | str, places: int = 1) -> str:
    """Format a stored fraction as a percentage without changing its meaning."""
    number = value if isinstance(value, Decimal) else _decimal(value, "percentage")
    return f"{number * Decimal('100'):.{places}f}%"


def format_inr(value: Decimal | str) -> str:
    """Format a rupee amount in readable Indian units."""
    number = value if isinstance(value, Decimal) else _decimal(value, "rupee amount")
    absolute = abs(number)
    if absolute >= Decimal("10000000"):
        return f"₹{number / Decimal('10000000'):,.2f} cr"
    if absolute >= Decimal("100000"):
        return f"₹{number / Decimal('100000'):,.2f} lakh"
    return f"₹{number:,.2f}"


def format_date(value: date | str) -> str:
    """Format dates consistently for the interface."""
    parsed = value if isinstance(value, date) else date.fromisoformat(value)
    return parsed.strftime("%d %b %Y")


def _read_memos(
    path: Path,
    decisions: tuple[DecisionMemoInput, ...],
    contexts: Mapping[str, MemoContext],
) -> tuple[LoadedMemoArtifact, ...]:
    root = _read_object(path, "memo artifact")
    if root.get("memo_contract_version") != MEMO_CONTRACT_VERSION:
        raise UIArtifactError("Memo artifact contract version is unsupported.")
    if root.get("prompt_version") != PROMPT_VERSION:
        raise UIArtifactError("Memo artifact prompt version is unsupported.")
    decision_index = {item.company_id: item for item in decisions}
    results: list[LoadedMemoArtifact] = []
    raw_companies = root.get("companies")
    if not isinstance(raw_companies, list):
        raise UIArtifactError("Memo artifact companies must be an array.")
    for raw_value in raw_companies:
        raw = _object(raw_value, "memo company")
        decision_raw = _object(raw.get("decision"), "memo decision")
        company_id = _string(decision_raw, "company_id", "memo decision")
        decision = decision_index.get(company_id)
        if decision is None:
            raise UIArtifactError(f"Memo artifact contains unknown company {company_id!r}.")
        if decision_raw != decision.stable_payload():
            raise UIArtifactError(
                f"{company_id}: persisted memo decision does not match the frozen snapshot."
            )
        try:
            status = MemoStatus(_string(raw, "memo_generation_status", company_id))
        except ValueError as exc:
            raise UIArtifactError(f"{company_id}: unsupported memo status.") from exc
        narrative_value = raw.get("narrative")
        narrative: GeneratedMemoNarrative | None = None
        if status is MemoStatus.GENERATED:
            if not isinstance(narrative_value, dict):
                raise UIArtifactError(f"{company_id}: generated memo has no narrative.")
            context = contexts.get(company_id)
            if context is None:
                raise UIArtifactError(f"{company_id}: memo context is unavailable.")
            narrative = parse_and_validate_memo_response(json.dumps(narrative_value), context)
        elif narrative_value is not None:
            raise UIArtifactError(
                f"{company_id}: {status.value} memo must not expose rejected narrative."
            )
        results.append(
            LoadedMemoArtifact(
                status=status,
                decision=decision,
                provider=_string(raw, "provider", company_id),
                deployment_id=_string(raw, "deployment_id", company_id),
                reasoning_effort=_string(raw, "reasoning_effort", company_id),
                max_output_tokens=_integer(raw, "max_output_tokens", company_id),
                narrative=narrative,
                response_id=_optional_string(raw.get("response_id"), "response_id"),
                usage=_usage(raw.get("usage"), company_id),
                error=_optional_string(raw.get("error"), "error"),
            )
        )
    if set(decision_index) != {item.decision.company_id for item in results}:
        raise UIArtifactError("Memo artifact must contain exactly one state for every company.")
    return tuple(sorted(results, key=lambda item: item.decision.company_id))


def company_snapshot_payload(data: DashboardData, company_id: str) -> dict[str, object]:
    """Return one validated raw company payload for display-only fields."""
    raw_companies = data.portfolio.get("companies")
    if not isinstance(raw_companies, list):
        raise UIArtifactError("Decision snapshot companies must be an array.")
    for value in raw_companies:
        company = _object(value, "decision company")
        if company.get("company_id") == company_id:
            return company
    raise UIArtifactError(f"No raw company payload for {company_id!r}.")


def _scenario_name(item: Mapping[str, object]) -> str:
    input_value = _object(item.get("input"), "scenario input")
    return _string(input_value, "name", "scenario input")


def _decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise UIArtifactError(f"Invalid decimal for {label}: {value!r}.") from exc


def _read_object(path: Path, label: str) -> dict[str, object]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UIArtifactError(f"Required {label} is missing: {path}.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise UIArtifactError(f"Cannot read {label} {path}: {exc}") from exc
    return _object(value, label)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise UIArtifactError(f"{label} must be a JSON object.")
    return cast(dict[str, object], value)


def _string(value: Mapping[str, object], key: str, label: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str):
        raise UIArtifactError(f"{label}.{key} must be a string.")
    return candidate


def _integer(value: Mapping[str, object], key: str, label: str) -> int:
    candidate = value.get(key)
    if not isinstance(candidate, int) or isinstance(candidate, bool):
        raise UIArtifactError(f"{label}.{key} must be an integer.")
    return candidate


def _optional_string(value: object, label: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise UIArtifactError(f"{label} must be a string or null.")
    return value


def _usage(value: object, company_id: str) -> dict[str, int | None] | None:
    if value is None:
        return None
    raw = _object(value, f"{company_id} usage")
    result: dict[str, int | None] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        candidate = raw.get(key)
        if candidate is not None and (
            not isinstance(candidate, int) or isinstance(candidate, bool)
        ):
            raise UIArtifactError(f"{company_id} usage.{key} must be an integer or null.")
        result[key] = candidate
    return result
