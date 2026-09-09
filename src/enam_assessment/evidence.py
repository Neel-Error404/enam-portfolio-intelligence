"""Point-in-time evidence contracts and deterministic normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256

from enam_assessment.errors import (
    EvidenceValidationError,
    MissingEvidenceError,
    UnsupportedIdentifierError,
)

EVIDENCE_ANALYSIS_AS_OF = date(2026, 9, 8)


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    """Explicit boundary for a reproducible point-in-time snapshot."""

    analysis_as_of: date = EVIDENCE_ANALYSIS_AS_OF


class EvidenceType(StrEnum):
    """Nature of a fundamental or research claim."""

    REPORTED_FACT = "reported_fact"
    ANALYST_ESTIMATE = "analyst_estimate"
    ANALYST_OPINION = "analyst_opinion"
    MANAGEMENT_GUIDANCE = "management_guidance"


class ExtractionConfidence(StrEnum):
    """Confidence in extracting a claim from its cited source."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CorporateActionStatus(StrEnum):
    """Whether a price is adjusted and how that status was established."""

    ADJUSTED_BY_SOURCE = "adjusted_by_source"
    UNADJUSTED = "unadjusted"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class DataState(StrEnum):
    """Explicit availability state for evidence used by later layers."""

    AVAILABLE = "available"
    MISSING = "missing"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class InstrumentIdentifier:
    """Verified identifiers for one company or benchmark."""

    company_id: str
    canonical_name: str
    nse_symbol: str | None
    bse_code: str | None
    isin: str | None
    aliases: tuple[str, ...] = ()
    history_note: str = ""


INSTRUMENTS: tuple[InstrumentIdentifier, ...] = (
    InstrumentIdentifier(
        "amber",
        "Amber Enterprises India Limited",
        "AMBER",
        "540902",
        "INE371P01015",
        ("AMBER ENTERPRISES", "AMBER.NS"),
    ),
    InstrumentIdentifier(
        "dbl",
        "Dilip Buildcon Limited",
        "DBL",
        "540047",
        "INE917M01012",
        ("DILIP BUILDCON", "DBL.NS"),
    ),
    InstrumentIdentifier(
        "zee",
        "Zee Entertainment Enterprises Limited",
        "ZEEL",
        "505537",
        "INE256A01028",
        ("ZEE ENTERTAINMENT", "ZEEL.NS"),
    ),
    InstrumentIdentifier(
        "welspun",
        "Welspun Living Limited",
        "WELSPUNLIV",
        "514162",
        "INE192B01031",
        ("WELSPUN", "WELSPUN INDIA", "WELSPUNIND", "WELSPUNLIV.NS"),
        "Formerly Welspun India Limited; exact exchange symbol-change date remains unverified.",
    ),
    InstrumentIdentifier(
        "bse-500-tri",
        "S&P BSE 500 Total Return Index",
        None,
        "17",
        None,
        ("BSE500T",),
        "Primary benchmark; official daily history requires authenticated access.",
    ),
    InstrumentIdentifier(
        "nifty-500-tri",
        "NIFTY 500 Total Return Index",
        "NIFTY 500",
        None,
        None,
        ("NIFTY 500 TRI",),
        "Secondary benchmark using the official Total Returns Index field.",
    ),
)


def resolve_instrument(identifier: str) -> InstrumentIdentifier:
    """Resolve a supported symbol, code, ISIN, name, or declared alias."""
    candidate = identifier.strip().upper()
    for instrument in INSTRUMENTS:
        known = {
            instrument.company_id.upper(),
            instrument.canonical_name.upper(),
            *(alias.upper() for alias in instrument.aliases),
        }
        if instrument.nse_symbol is not None:
            known.add(instrument.nse_symbol.upper())
        if instrument.bse_code is not None:
            known.add(instrument.bse_code.upper())
        if instrument.isin is not None:
            known.add(instrument.isin.upper())
        if candidate in known:
            return instrument
    raise UnsupportedIdentifierError(
        f"Unsupported instrument identifier {identifier!r}; use a verified NSE symbol, "
        "BSE code, ISIN, canonical name, or recorded alias."
    )


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    """Age and optional policy outcome for one dated source."""

    state: DataState
    age_days: int | None
    max_age_days: int | None


def assess_freshness(
    observation_date: date | None,
    *,
    as_of: date,
    max_age_days: int | None,
) -> FreshnessAssessment:
    """Describe freshness without inventing a policy threshold."""
    if max_age_days is not None and max_age_days < 0:
        raise EvidenceValidationError("max_age_days must be zero or positive")
    if observation_date is None:
        return FreshnessAssessment(DataState.MISSING, None, max_age_days)
    age_days = (as_of - observation_date).days
    if age_days < 0:
        raise EvidenceValidationError("observation date cannot be after the as-of date")
    state = (
        DataState.STALE
        if max_age_days is not None and age_days > max_age_days
        else DataState.AVAILABLE
    )
    return FreshnessAssessment(state, age_days, max_age_days)


@dataclass(frozen=True, slots=True)
class PriceObservation:
    """One dated OHLCV observation with explicit adjustment provenance."""

    evidence_id: str
    instrument_id: str
    trading_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    adjusted_close: Decimal | None
    volume: Decimal | None
    corporate_action_status: CorporateActionStatus
    source_id: str
    retrieval_timestamp: datetime
    validation_status: DataState = DataState.AVAILABLE

    def __post_init__(self) -> None:
        prices = tuple(
            value
            for value in (self.open, self.high, self.low, self.close, self.adjusted_close)
            if value is not None
        )
        if not prices or any(value <= 0 for value in prices):
            raise EvidenceValidationError("price values must be positive")
        upper_candidates = tuple(
            value for value in (self.open, self.close, self.low) if value is not None
        )
        lower_candidates = tuple(
            value for value in (self.open, self.close, self.high) if value is not None
        )
        if self.high is not None and self.high < max(upper_candidates):
            raise EvidenceValidationError("high price must be at least open, low, and close")
        if self.low is not None and self.low > min(lower_candidates):
            raise EvidenceValidationError("low price must be at most open, high, and close")
        if self.volume is not None and self.volume < 0:
            raise EvidenceValidationError("volume must be zero or positive")


@dataclass(frozen=True, slots=True)
class ResearchEvidence:
    """A dated claim extracted from supplied analyst research."""

    evidence_id: str
    company_id: str
    claim: str
    evidence_type: EvidenceType
    publication_date: date
    source_id: str
    source_locator: str
    relevant_period: str
    extraction_confidence: ExtractionConfidence
    conflicting_evidence_ids: tuple[str, ...]
    retrieval_timestamp: datetime

    def __post_init__(self) -> None:
        required = {
            "evidence_id": self.evidence_id,
            "company_id": self.company_id,
            "claim": self.claim,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "relevant_period": self.relevant_period,
        }
        missing = tuple(name for name, value in required.items() if not value.strip())
        if missing:
            raise EvidenceValidationError(
                f"Research evidence requires non-empty fields: {', '.join(missing)}"
            )


def match_price_date(
    observations: tuple[PriceObservation, ...],
    *,
    instrument_id: str,
    target: date,
) -> PriceObservation:
    """Return an exact-date observation; never shift or forward-fill."""
    matches = tuple(
        observation
        for observation in observations
        if observation.instrument_id == instrument_id and observation.trading_date == target
    )
    if not matches:
        raise MissingEvidenceError(
            f"No exact price observation for {instrument_id!r} on {target.isoformat()}; "
            "future or prior prices are not substituted."
        )
    if len(matches) > 1:
        raise EvidenceValidationError(
            f"Multiple price observations for {instrument_id!r} on {target.isoformat()}."
        )
    return matches[0]


@dataclass(frozen=True, slots=True)
class FundamentalFact:
    """A dated, source-linked company fundamental observation."""

    evidence_id: str
    company_id: str
    metric_name: str
    value: Decimal | str
    unit: str
    reporting_period: str
    period_end: date
    publication_date: date
    source_id: str
    source_locator: str
    evidence_type: EvidenceType
    retrieval_timestamp: datetime
    extraction_confidence: ExtractionConfidence
    conflicting_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = {
            "evidence_id": self.evidence_id,
            "company_id": self.company_id,
            "metric_name": self.metric_name,
            "unit": self.unit,
            "reporting_period": self.reporting_period,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
        }
        missing = tuple(name for name, value in required.items() if not value.strip())
        if missing:
            raise EvidenceValidationError(
                f"Fundamental evidence requires non-empty fields: {', '.join(missing)}"
            )


@dataclass(frozen=True, slots=True)
class SourceManifestEntry:
    """Provenance record for a local or public evidence source."""

    source_id: str
    title: str
    source_type: str
    location: str
    publication_date: date | None
    retrieval_timestamp: datetime
    coverage: str
    content_sha256: str | None
    validation_status: str
    is_secondary: bool
    notes: str = ""

    def stable_payload(self) -> dict[str, object]:
        """Return a canonical manifest payload, including retrieval provenance."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "source_type": self.source_type,
            "location": self.location,
            "publication_date": (
                self.publication_date.isoformat() if self.publication_date is not None else None
            ),
            "retrieval_timestamp": self.retrieval_timestamp.isoformat(),
            "coverage": self.coverage,
            "content_sha256": self.content_sha256,
            "validation_status": self.validation_status,
            "is_secondary": self.is_secondary,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class TemporalExclusion:
    """Evidence rejected from a snapshot because it was not yet available."""

    evidence_id: str
    reason: str
    available_date: date
    analysis_as_of: date


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    """Point-in-time evidence accepted at a declared as-of date."""

    analysis_as_of: date
    fundamentals: tuple[FundamentalFact, ...]
    research: tuple[ResearchEvidence, ...]
    prices: tuple[PriceObservation, ...]
    sources: tuple[SourceManifestEntry, ...]
    temporal_exclusions: tuple[TemporalExclusion, ...]

    @property
    def manifest_sha256(self) -> str:
        """Hash the canonical, deterministically ordered source manifest."""
        payload = [source.stable_payload() for source in self.sources]
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @classmethod
    def create(
        cls,
        *,
        analysis_as_of: date,
        fundamentals: tuple[FundamentalFact, ...] = (),
        research: tuple[ResearchEvidence, ...] = (),
        prices: tuple[PriceObservation, ...] = (),
        sources: tuple[SourceManifestEntry, ...] = (),
    ) -> EvidenceSnapshot:
        included: list[FundamentalFact] = []
        included_research: list[ResearchEvidence] = []
        included_prices: list[PriceObservation] = []
        included_sources: list[SourceManifestEntry] = []
        excluded: list[TemporalExclusion] = []
        for fact in fundamentals:
            if fact.publication_date > analysis_as_of:
                excluded.append(
                    TemporalExclusion(
                        evidence_id=fact.evidence_id,
                        reason="published_after_analysis_as_of",
                        available_date=fact.publication_date,
                        analysis_as_of=analysis_as_of,
                    )
                )
            else:
                included.append(fact)
        for item in research:
            if item.publication_date > analysis_as_of:
                excluded.append(
                    TemporalExclusion(
                        evidence_id=item.evidence_id,
                        reason="published_after_analysis_as_of",
                        available_date=item.publication_date,
                        analysis_as_of=analysis_as_of,
                    )
                )
            else:
                included_research.append(item)
        for observation in prices:
            if observation.trading_date > analysis_as_of:
                excluded.append(
                    TemporalExclusion(
                        evidence_id=observation.evidence_id,
                        reason="trading_date_after_analysis_as_of",
                        available_date=observation.trading_date,
                        analysis_as_of=analysis_as_of,
                    )
                )
            else:
                included_prices.append(observation)
        for source in sources:
            if source.publication_date is not None and source.publication_date > analysis_as_of:
                excluded.append(
                    TemporalExclusion(
                        evidence_id=source.source_id,
                        reason="source_published_after_analysis_as_of",
                        available_date=source.publication_date,
                        analysis_as_of=analysis_as_of,
                    )
                )
            else:
                included_sources.append(source)
        return cls(
            analysis_as_of=analysis_as_of,
            fundamentals=tuple(sorted(included, key=lambda item: item.evidence_id)),
            research=tuple(sorted(included_research, key=lambda item: item.evidence_id)),
            prices=tuple(
                sorted(
                    included_prices,
                    key=lambda item: (item.instrument_id, item.trading_date),
                )
            ),
            sources=tuple(sorted(included_sources, key=lambda item: item.source_id)),
            temporal_exclusions=tuple(sorted(excluded, key=lambda item: item.evidence_id)),
        )


def make_evidence_id(namespace: str, *identity_parts: str) -> str:
    """Build a stable ID from source identity fields, never retrieval time."""
    normalized = "\x1f".join(part.strip().lower() for part in identity_parts)
    digest = sha256(normalized.encode("utf-8")).hexdigest()[:16]
    prefix = "-".join(namespace.strip().lower().split())
    return f"{prefix}-{digest}"
