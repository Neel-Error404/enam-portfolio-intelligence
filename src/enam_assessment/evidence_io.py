"""Deterministic JSON persistence for an offline evidence snapshot."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .errors import EvidenceValidationError
from .evidence import (
    CorporateActionStatus,
    DataState,
    EvidenceSnapshot,
    EvidenceType,
    ExtractionConfidence,
    FundamentalFact,
    PriceObservation,
    ResearchEvidence,
    SourceManifestEntry,
    TemporalExclusion,
)


def write_snapshot(snapshot: EvidenceSnapshot, path: Path) -> None:
    """Write a canonical UTF-8 JSON snapshot suitable for offline reuse."""
    payload = {
        "analysis_as_of": snapshot.analysis_as_of.isoformat(),
        "manifest_sha256": snapshot.manifest_sha256,
        "fundamentals": [_fundamental_dict(item) for item in snapshot.fundamentals],
        "research": [_research_dict(item) for item in snapshot.research],
        "prices": [_price_dict(item) for item in snapshot.prices],
        "sources": [item.stable_payload() for item in snapshot.sources],
        "temporal_exclusions": [
            {
                "evidence_id": item.evidence_id,
                "reason": item.reason,
                "available_date": item.available_date.isoformat(),
                "analysis_as_of": item.analysis_as_of.isoformat(),
            }
            for item in snapshot.temporal_exclusions
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_snapshot(path: Path) -> EvidenceSnapshot:
    """Load a previously normalized snapshot without accessing live sources."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("root is not an object")
        fundamentals = tuple(_fundamental_from_dict(item) for item in raw["fundamentals"])
        research = tuple(_research_from_dict(item) for item in raw["research"])
        prices = tuple(_price_from_dict(item) for item in raw["prices"])
        sources = tuple(_source_from_dict(item) for item in raw["sources"])
        exclusions = tuple(
            TemporalExclusion(
                evidence_id=str(item["evidence_id"]),
                reason=str(item["reason"]),
                available_date=date.fromisoformat(str(item["available_date"])),
                analysis_as_of=date.fromisoformat(str(item["analysis_as_of"])),
            )
            for item in raw["temporal_exclusions"]
        )
        snapshot = EvidenceSnapshot(
            analysis_as_of=date.fromisoformat(str(raw["analysis_as_of"])),
            fundamentals=fundamentals,
            research=research,
            prices=prices,
            sources=sources,
            temporal_exclusions=exclusions,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError(f"Invalid evidence snapshot {path}: {exc}") from exc
    expected_hash = raw.get("manifest_sha256")
    if expected_hash != snapshot.manifest_sha256:
        raise EvidenceValidationError(f"Evidence manifest hash mismatch in snapshot {path}.")
    return snapshot


def _fundamental_dict(item: FundamentalFact) -> dict[str, object]:
    payload = asdict(item)
    payload["value"] = str(item.value)
    payload["value_kind"] = "decimal" if isinstance(item.value, Decimal) else "text"
    payload["period_end"] = item.period_end.isoformat()
    payload["publication_date"] = item.publication_date.isoformat()
    payload["evidence_type"] = item.evidence_type.value
    payload["retrieval_timestamp"] = item.retrieval_timestamp.isoformat()
    payload["extraction_confidence"] = item.extraction_confidence.value
    return payload


def _research_dict(item: ResearchEvidence) -> dict[str, object]:
    payload = asdict(item)
    payload["evidence_type"] = item.evidence_type.value
    payload["publication_date"] = item.publication_date.isoformat()
    payload["extraction_confidence"] = item.extraction_confidence.value
    payload["retrieval_timestamp"] = item.retrieval_timestamp.isoformat()
    return payload


def _price_dict(item: PriceObservation) -> dict[str, object]:
    payload = asdict(item)
    for key in ("open", "high", "low", "close", "adjusted_close", "volume"):
        value = payload[key]
        payload[key] = None if value is None else str(value)
    payload["trading_date"] = item.trading_date.isoformat()
    payload["corporate_action_status"] = item.corporate_action_status.value
    payload["retrieval_timestamp"] = item.retrieval_timestamp.isoformat()
    payload["validation_status"] = item.validation_status.value
    return payload


def _fundamental_from_dict(item: dict[str, object]) -> FundamentalFact:
    value = str(item["value"])
    normalized_value: Decimal | str = (
        Decimal(value) if item.get("value_kind") == "decimal" else value
    )
    return FundamentalFact(
        evidence_id=str(item["evidence_id"]),
        company_id=str(item["company_id"]),
        metric_name=str(item["metric_name"]),
        value=normalized_value,
        unit=str(item["unit"]),
        reporting_period=str(item["reporting_period"]),
        period_end=date.fromisoformat(str(item["period_end"])),
        publication_date=date.fromisoformat(str(item["publication_date"])),
        source_id=str(item["source_id"]),
        source_locator=str(item["source_locator"]),
        evidence_type=EvidenceType(str(item["evidence_type"])),
        retrieval_timestamp=datetime.fromisoformat(str(item["retrieval_timestamp"])),
        extraction_confidence=ExtractionConfidence(str(item["extraction_confidence"])),
        conflicting_evidence_ids=_string_values(item.get("conflicting_evidence_ids", [])),
    )


def _research_from_dict(item: dict[str, object]) -> ResearchEvidence:
    return ResearchEvidence(
        evidence_id=str(item["evidence_id"]),
        company_id=str(item["company_id"]),
        claim=str(item["claim"]),
        evidence_type=EvidenceType(str(item["evidence_type"])),
        publication_date=date.fromisoformat(str(item["publication_date"])),
        source_id=str(item["source_id"]),
        source_locator=str(item["source_locator"]),
        relevant_period=str(item["relevant_period"]),
        extraction_confidence=ExtractionConfidence(str(item["extraction_confidence"])),
        conflicting_evidence_ids=_string_values(item.get("conflicting_evidence_ids", [])),
        retrieval_timestamp=datetime.fromisoformat(str(item["retrieval_timestamp"])),
    )


def _price_from_dict(item: dict[str, object]) -> PriceObservation:
    return PriceObservation(
        evidence_id=str(item["evidence_id"]),
        instrument_id=str(item["instrument_id"]),
        trading_date=date.fromisoformat(str(item["trading_date"])),
        open=_optional_decimal(item.get("open")),
        high=_optional_decimal(item.get("high")),
        low=_optional_decimal(item.get("low")),
        close=Decimal(str(item["close"])),
        adjusted_close=_optional_decimal(item.get("adjusted_close")),
        volume=_optional_decimal(item.get("volume")),
        corporate_action_status=CorporateActionStatus(str(item["corporate_action_status"])),
        source_id=str(item["source_id"]),
        retrieval_timestamp=datetime.fromisoformat(str(item["retrieval_timestamp"])),
        validation_status=DataState(str(item["validation_status"])),
    )


def _source_from_dict(item: dict[str, object]) -> SourceManifestEntry:
    publication = item.get("publication_date")
    return SourceManifestEntry(
        source_id=str(item["source_id"]),
        title=str(item["title"]),
        source_type=str(item["source_type"]),
        location=str(item["location"]),
        publication_date=(
            date.fromisoformat(str(publication)) if publication is not None else None
        ),
        retrieval_timestamp=datetime.fromisoformat(str(item["retrieval_timestamp"])),
        coverage=str(item["coverage"]),
        content_sha256=(
            str(item["content_sha256"]) if item.get("content_sha256") is not None else None
        ),
        validation_status=str(item["validation_status"]),
        is_secondary=bool(item["is_secondary"]),
        notes=str(item.get("notes", "")),
    )


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvidenceValidationError("conflicting_evidence_ids must be a list of strings")
    return tuple(value)
