"""Frozen Phase 5 memo contract, bounded context selection, and validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from .errors import MemoContextError, MemoValidationError
from .evidence import (
    EvidenceSnapshot,
    FundamentalFact,
    PriceObservation,
    ResearchEvidence,
    SourceManifestEntry,
)

DECISION_CONTRACT_VERSION = "phase5-company-decision-v1"
MEMO_CONTRACT_VERSION = "company-memo-v1"
PROMPT_VERSION = "company-memo-prompt-v1"

MEMO_SECTION_NAMES = (
    "stance_and_action_explanation",
    "investment_thesis",
    "supporting_evidence",
    "counter_evidence_and_risks",
    "valuation_scenario_explanation",
    "portfolio_sizing_explanation",
    "missing_information_and_limitations",
    "what_would_change_the_decision",
    "human_review_explanation",
)

VALUATION_LIMITATIONS = (
    "Scenario values are a relative operating-value sensitivity, not an independent "
    "absolute valuation.",
    "Scenario assumptions are prototype judgments and are not probability-weighted.",
    "Verified diluted share counts and independently reconstructed enterprise values are "
    "not available consistently across all four companies.",
)


@dataclass(frozen=True, slots=True)
class DecisionMemoInput:
    """Versioned public subset of a frozen Phase 5 company decision."""

    contract_version: str
    company_id: str
    company_name: str
    decision_date: date
    evidence_manifest_sha256: str
    decision_snapshot_sha256: str
    engine_version: str
    configuration_version: str
    working_shares: str
    working_cost_basis: str
    current_price: str
    price_date: date
    working_current_weight: str
    target_weight: str
    underlying_stance: str
    final_portfolio_action: str
    human_review_required: bool
    human_review_reasons: tuple[str, ...]
    hard_gates: tuple[dict[str, object], ...]
    principle_scores: tuple[dict[str, object], ...]
    weighted_principle_score: str | None
    scenarios: tuple[dict[str, object], ...]
    confidence: str
    missing_data_flags: tuple[str, ...]
    common_drivers: tuple[str, ...]
    change_triggers: tuple[str, ...]
    historical_benchmark_context: dict[str, object]
    primary_benchmark_id: str
    primary_benchmark_status: str
    secondary_benchmark_id: str
    secondary_benchmark_status: str
    evidence_ids: tuple[str, ...]
    evidence_dates: tuple[tuple[str, date], ...]
    provisional_holdings: bool
    provisional_holdings_warning: str
    valuation_limitations: tuple[str, ...]

    def stable_payload(self) -> dict[str, object]:
        """Return a deterministic, JSON-compatible public contract payload."""
        payload = cast(dict[str, object], _json_value(asdict(self)))
        return payload


@dataclass(frozen=True, slots=True)
class MemoEvidenceItem:
    """Minimum source-linked evidence sent to the memo model."""

    evidence_id: str
    company_or_instrument_id: str
    evidence_kind: str
    available_date: date
    content: str
    source_id: str
    source_title: str
    source_type: str
    source_locator: str
    evidence_classification: str
    conflicting_evidence_ids: tuple[str, ...]

    def stable_payload(self) -> dict[str, object]:
        return cast(dict[str, object], _json_value(asdict(self)))


@dataclass(frozen=True, slots=True)
class MemoContext:
    """Bounded model input assembled only from a public decision and cited evidence."""

    decision: DecisionMemoInput
    evidence: tuple[MemoEvidenceItem, ...]

    @property
    def allowed_evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.evidence)

    def stable_payload(self) -> dict[str, object]:
        return {
            "decision": self.decision.stable_payload(),
            "evidence": [item.stable_payload() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class MemoClaim:
    """A material narrative claim with explicit evidence references."""

    text: str
    evidence_ids: tuple[str, ...]
    category: str


@dataclass(frozen=True, slots=True)
class GeneratedMemoNarrative:
    """Validated model-authored narrative; immutable decision values stay separate."""

    company_id: str
    company_name: str
    decision_date: date
    source_decision_snapshot_hash: str
    memo_contract_version: str
    prompt_version: str
    underlying_stance: str
    final_portfolio_action: str
    executive_summary: MemoClaim
    sections: dict[str, tuple[MemoClaim, ...]]

    def stable_payload(self) -> dict[str, object]:
        result: dict[str, object] = {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "decision_date": self.decision_date.isoformat(),
            "source_decision_snapshot_hash": self.source_decision_snapshot_hash,
            "memo_contract_version": self.memo_contract_version,
            "prompt_version": self.prompt_version,
            "underlying_stance": self.underlying_stance,
            "final_portfolio_action": self.final_portfolio_action,
            "executive_summary": _claim_payload(self.executive_summary),
        }
        result.update(
            {
                name: [_claim_payload(claim) for claim in self.sections[name]]
                for name in MEMO_SECTION_NAMES
            }
        )
        return result


def read_decision_memo_inputs(path: Path) -> tuple[DecisionMemoInput, ...]:
    """Read and integrity-check the versioned memo interface from the Phase 5 JSON."""
    try:
        raw_value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoContextError(f"Cannot read Phase 5 decision snapshot {path}: {exc}") from exc
    raw = _object(raw_value, "decision snapshot")
    stored_hash = _string(raw, "snapshot_sha256", "decision snapshot")
    hash_payload = {key: value for key, value in raw.items() if key != "snapshot_sha256"}
    calculated_hash = sha256(
        json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()
    if calculated_hash != stored_hash:
        raise MemoContextError(
            f"Decision snapshot hash mismatch: stored {stored_hash}, calculated "
            f"{calculated_hash}. Rebuild Phase 5 before generating memos."
        )
    companies = _list(raw, "companies", "decision snapshot")
    result = tuple(
        _company_contract(_object(item, "decision company"), raw, stored_hash) for item in companies
    )
    if len(result) != 4 or len({item.company_id for item in result}) != 4:
        raise MemoContextError("The Phase 5 memo contract requires four unique companies.")
    return tuple(sorted(result, key=lambda item: item.company_id))


def build_memo_context(
    decision: DecisionMemoInput,
    snapshot: EvidenceSnapshot,
) -> MemoContext:
    """Select exactly the cited, temporally valid evidence for one company."""
    if snapshot.manifest_sha256 != decision.evidence_manifest_sha256:
        raise MemoContextError(
            f"{decision.company_id}: evidence manifest hash does not match the decision contract."
        )
    declared_dates = dict(decision.evidence_dates)
    if len(declared_dates) != len(decision.evidence_dates) or set(declared_dates) != set(
        decision.evidence_ids
    ):
        raise MemoContextError(
            f"{decision.company_id}: decision evidence IDs and availability dates do not match."
        )
    source_index = {item.source_id: item for item in snapshot.sources}
    evidence_index: dict[str, FundamentalFact | ResearchEvidence | PriceObservation] = {}
    combined: list[FundamentalFact | ResearchEvidence | PriceObservation] = []
    combined.extend(snapshot.fundamentals)
    combined.extend(snapshot.research)
    combined.extend(snapshot.prices)
    for item in combined:
        if item.evidence_id in evidence_index:
            raise MemoContextError(f"Duplicate evidence ID in snapshot: {item.evidence_id}.")
        evidence_index[item.evidence_id] = item

    selected: list[MemoEvidenceItem] = []
    for evidence_id in sorted(set(decision.evidence_ids)):
        evidence_record = evidence_index.get(evidence_id)
        if evidence_record is None:
            raise MemoContextError(
                f"{decision.company_id}: cited evidence ID {evidence_id!r} is not in the "
                "frozen Phase 4 snapshot."
            )
        normalized = _memo_evidence_item(evidence_record, source_index)
        if normalized.available_date > decision.decision_date:
            raise MemoContextError(
                f"{decision.company_id}: evidence {evidence_id!r} became available on "
                f"{normalized.available_date.isoformat()}, after the decision date."
            )
        if declared_dates[evidence_id] != normalized.available_date:
            raise MemoContextError(
                f"{decision.company_id}: evidence {evidence_id!r} availability changed from "
                f"{declared_dates[evidence_id].isoformat()} to "
                f"{normalized.available_date.isoformat()}. Rebuild Phase 5 before generating memos."
            )
        allowed_context_ids = {
            decision.company_id,
            decision.primary_benchmark_id,
            decision.secondary_benchmark_id,
            "portfolio",
        }
        if normalized.company_or_instrument_id not in allowed_context_ids:
            raise MemoContextError(
                f"{decision.company_id}: evidence {evidence_id!r} belongs to "
                f"{normalized.company_or_instrument_id!r}, not this company or declared "
                "portfolio/benchmark context."
            )
        selected.append(normalized)
    actual_ids = tuple(item.evidence_id for item in selected)
    expected_ids = tuple(sorted(set(decision.evidence_ids)))
    if actual_ids != expected_ids:
        raise MemoContextError(f"{decision.company_id}: memo evidence selection is incomplete.")
    return MemoContext(decision=decision, evidence=tuple(selected))


def parse_and_validate_memo_response(
    response_text: str,
    context: MemoContext,
) -> GeneratedMemoNarrative:
    """Parse a structured response and enforce identity, authority, and citation rules."""
    try:
        raw_value: Any = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise MemoValidationError(f"Memo response is not valid JSON: {exc}") from exc
    raw = _object(raw_value, "memo response", error_type=MemoValidationError)
    required_keys = {
        "company_id",
        "company_name",
        "decision_date",
        "source_decision_snapshot_hash",
        "memo_contract_version",
        "prompt_version",
        "underlying_stance",
        "final_portfolio_action",
        "executive_summary",
        *MEMO_SECTION_NAMES,
    }
    unknown = set(raw) - required_keys
    missing = required_keys - set(raw)
    if missing or unknown:
        raise MemoValidationError(
            f"Memo response keys do not match the contract; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}."
        )
    decision = context.decision
    immutable_values = {
        "company_id": decision.company_id,
        "company_name": decision.company_name,
        "decision_date": decision.decision_date.isoformat(),
        "source_decision_snapshot_hash": decision.decision_snapshot_sha256,
        "memo_contract_version": MEMO_CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "underlying_stance": decision.underlying_stance,
        "final_portfolio_action": decision.final_portfolio_action,
    }
    for field, expected in immutable_values.items():
        actual = raw.get(field)
        if actual != expected:
            raise MemoValidationError(
                f"Memo response changed immutable field {field!r}: expected {expected!r}, "
                f"received {actual!r}."
            )
    allow_list = set(context.allowed_evidence_ids)
    executive = _parse_claim(raw["executive_summary"], "executive_summary", allow_list)
    sections = {
        name: tuple(
            _parse_claim(value, f"{name}[{index}]", allow_list)
            for index, value in enumerate(
                _list(raw, name, "memo response", error_type=MemoValidationError)
            )
        )
        for name in MEMO_SECTION_NAMES
    }
    return GeneratedMemoNarrative(
        company_id=decision.company_id,
        company_name=decision.company_name,
        decision_date=decision.decision_date,
        source_decision_snapshot_hash=decision.decision_snapshot_sha256,
        memo_contract_version=MEMO_CONTRACT_VERSION,
        prompt_version=PROMPT_VERSION,
        underlying_stance=decision.underlying_stance,
        final_portfolio_action=decision.final_portfolio_action,
        executive_summary=executive,
        sections=sections,
    )


def memo_response_json_schema(decision: DecisionMemoInput) -> dict[str, object]:
    """Return a strict schema that pins every immutable decision identity field."""
    claim_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "evidence_ids", "category"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "evidence_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "category": {"type": "string", "minLength": 1},
        },
    }
    properties: dict[str, object] = {
        "company_id": {"type": "string", "enum": [decision.company_id]},
        "company_name": {"type": "string", "enum": [decision.company_name]},
        "decision_date": {"type": "string", "enum": [decision.decision_date.isoformat()]},
        "source_decision_snapshot_hash": {
            "type": "string",
            "enum": [decision.decision_snapshot_sha256],
        },
        "memo_contract_version": {"type": "string", "enum": [MEMO_CONTRACT_VERSION]},
        "prompt_version": {"type": "string", "enum": [PROMPT_VERSION]},
        "underlying_stance": {"type": "string", "enum": [decision.underlying_stance]},
        "final_portfolio_action": {
            "type": "string",
            "enum": [decision.final_portfolio_action],
        },
        "executive_summary": claim_schema,
    }
    properties.update(
        {
            name: {"type": "array", "minItems": 1, "items": claim_schema}
            for name in MEMO_SECTION_NAMES
        }
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _company_contract(
    company: Mapping[str, object],
    root: Mapping[str, object],
    snapshot_hash: str,
) -> DecisionMemoInput:
    company_id = _string(company, "company_id", "decision company")
    evidence_dates_raw = _list(company, "evidence_dates", company_id)
    evidence_dates: list[tuple[str, date]] = []
    for index, item in enumerate(evidence_dates_raw):
        if not isinstance(item, list) or len(item) != 2:
            raise MemoContextError(f"{company_id}: invalid evidence_dates[{index}].")
        evidence_dates.append((str(item[0]), date.fromisoformat(str(item[1]))))
    return DecisionMemoInput(
        contract_version=DECISION_CONTRACT_VERSION,
        company_id=company_id,
        company_name=_string(company, "company_name", company_id),
        decision_date=date.fromisoformat(_string(company, "decision_date", company_id)),
        evidence_manifest_sha256=_string(company, "evidence_manifest_sha256", company_id),
        decision_snapshot_sha256=snapshot_hash,
        engine_version=_string(company, "engine_version", company_id),
        configuration_version=_string(company, "configuration_version", company_id),
        working_shares=_string(company, "working_shares", company_id),
        working_cost_basis=_string(company, "working_cost_basis", company_id),
        current_price=_string(company, "current_price", company_id),
        price_date=date.fromisoformat(_string(company, "price_date", company_id)),
        working_current_weight=_string(company, "working_current_weight", company_id),
        target_weight=_string(company, "target_weight", company_id),
        underlying_stance=_string(company, "underlying_stance", company_id),
        final_portfolio_action=_string(company, "final_action", company_id),
        human_review_required=_boolean(company, "human_review_required", company_id),
        human_review_reasons=_strings(company, "human_review_reasons", company_id),
        hard_gates=_objects(company, "gates", company_id),
        principle_scores=_objects(company, "principle_scores", company_id),
        weighted_principle_score=_optional_string(company, "weighted_principle_score", company_id),
        scenarios=_objects(company, "scenarios", company_id),
        confidence=_string(company, "confidence", company_id),
        missing_data_flags=_strings(company, "missing_data_flags", company_id),
        common_drivers=_strings(company, "common_drivers", company_id),
        change_triggers=_strings(company, "change_triggers", company_id),
        historical_benchmark_context=dict(
            _object(company.get("historical_benchmark_context"), f"{company_id} benchmark")
        ),
        primary_benchmark_id=_string(root, "primary_benchmark_id", "decision snapshot"),
        primary_benchmark_status=_string(root, "primary_benchmark_status", "decision snapshot"),
        secondary_benchmark_id=_string(root, "secondary_benchmark_id", "decision snapshot"),
        secondary_benchmark_status=_string(root, "secondary_benchmark_status", "decision snapshot"),
        evidence_ids=_strings(company, "evidence_ids", company_id),
        evidence_dates=tuple(evidence_dates),
        provisional_holdings=_boolean(company, "provisional_holdings", company_id),
        provisional_holdings_warning=_string(
            root, "provisional_holdings_warning", "decision snapshot"
        ),
        valuation_limitations=VALUATION_LIMITATIONS,
    )


def _memo_evidence_item(
    item: FundamentalFact | ResearchEvidence | PriceObservation,
    sources: Mapping[str, SourceManifestEntry],
) -> MemoEvidenceItem:
    source_value = sources.get(item.source_id)
    if source_value is None:
        raise MemoContextError(
            f"Evidence {item.evidence_id!r} references unknown source {item.source_id!r}."
        )
    source = source_value
    if isinstance(item, FundamentalFact):
        content = (
            f"{item.metric_name}: {item.value} {item.unit}; reporting period "
            f"{item.reporting_period}; period end {item.period_end.isoformat()}."
        )
        company_id = item.company_id
        available = item.publication_date
        locator = item.source_locator
        classification = item.evidence_type.value
        conflicts = item.conflicting_evidence_ids
        kind = "fundamental_fact"
    elif isinstance(item, ResearchEvidence):
        content = f"{item.claim}; relevant period {item.relevant_period}."
        company_id = item.company_id
        available = item.publication_date
        locator = item.source_locator
        classification = item.evidence_type.value
        conflicts = item.conflicting_evidence_ids
        kind = "research_evidence"
    else:
        adjusted = item.adjusted_close if item.adjusted_close is not None else item.close
        content = (
            f"Trading-date close {item.close}; adjusted close used {adjusted}; "
            f"corporate-action status {item.corporate_action_status.value}."
        )
        company_id = item.instrument_id
        available = item.trading_date
        locator = item.trading_date.isoformat()
        classification = item.validation_status.value
        conflicts = ()
        kind = "price_observation"
    return MemoEvidenceItem(
        evidence_id=item.evidence_id,
        company_or_instrument_id=company_id,
        evidence_kind=kind,
        available_date=available,
        content=content,
        source_id=item.source_id,
        source_title=str(source.title),
        source_type=str(source.source_type),
        source_locator=locator,
        evidence_classification=classification,
        conflicting_evidence_ids=tuple(sorted(conflicts)),
    )


def _parse_claim(value: object, field: str, allow_list: set[str]) -> MemoClaim:
    raw = _object(value, field, error_type=MemoValidationError)
    if set(raw) != {"text", "evidence_ids", "category"}:
        raise MemoValidationError(f"{field} must contain only text, evidence_ids, and category.")
    text = _string(raw, "text", field, error_type=MemoValidationError).strip()
    category = _string(raw, "category", field, error_type=MemoValidationError).strip()
    evidence_ids = _strings(raw, "evidence_ids", field, error_type=MemoValidationError)
    if not text or not category:
        raise MemoValidationError(f"{field} text and category must be non-empty.")
    if not evidence_ids:
        raise MemoValidationError(f"{field} is a material claim and requires a citation.")
    unknown = sorted(set(evidence_ids) - allow_list)
    if unknown:
        raise MemoValidationError(f"{field} cites evidence outside the allow-list: {unknown}.")
    return MemoClaim(text=text, evidence_ids=tuple(sorted(set(evidence_ids))), category=category)


def _claim_payload(claim: MemoClaim) -> dict[str, object]:
    return {
        "text": claim.text,
        "evidence_ids": list(claim.evidence_ids),
        "category": claim.category,
    }


def _object(
    value: object,
    label: str,
    *,
    error_type: type[MemoContextError] | type[MemoValidationError] = MemoContextError,
) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise error_type(f"{label} must be a JSON object.")
    return cast(dict[str, object], value)


def _list(
    value: Mapping[str, object],
    key: str,
    label: str,
    *,
    error_type: type[MemoContextError] | type[MemoValidationError] = MemoContextError,
) -> list[object]:
    candidate = value.get(key)
    if not isinstance(candidate, list):
        raise error_type(f"{label}.{key} must be a JSON array.")
    return cast(list[object], candidate)


def _string(
    value: Mapping[str, object],
    key: str,
    label: str,
    *,
    error_type: type[MemoContextError] | type[MemoValidationError] = MemoContextError,
) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str):
        raise error_type(f"{label}.{key} must be a string.")
    return candidate


def _optional_string(value: Mapping[str, object], key: str, label: str) -> str | None:
    candidate = value.get(key)
    if candidate is not None and not isinstance(candidate, str):
        raise MemoContextError(f"{label}.{key} must be a string or null.")
    return candidate


def _boolean(value: Mapping[str, object], key: str, label: str) -> bool:
    candidate = value.get(key)
    if not isinstance(candidate, bool):
        raise MemoContextError(f"{label}.{key} must be a boolean.")
    return candidate


def _strings(
    value: Mapping[str, object],
    key: str,
    label: str,
    *,
    error_type: type[MemoContextError] | type[MemoValidationError] = MemoContextError,
) -> tuple[str, ...]:
    candidates = _list(value, key, label, error_type=error_type)
    if not all(isinstance(item, str) for item in candidates):
        raise error_type(f"{label}.{key} must contain only strings.")
    return tuple(cast(list[str], candidates))


def _objects(value: Mapping[str, object], key: str, label: str) -> tuple[dict[str, object], ...]:
    return tuple(_object(item, f"{label}.{key}") for item in _list(value, key, label))


def _json_value(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value
