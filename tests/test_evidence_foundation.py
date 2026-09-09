from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from enam_assessment.errors import (
    EvidenceValidationError,
    MissingEvidenceError,
    UnsupportedIdentifierError,
)
from enam_assessment.evidence import (
    CorporateActionStatus,
    DataState,
    EvidenceConfig,
    EvidenceSnapshot,
    EvidenceType,
    ExtractionConfidence,
    FundamentalFact,
    PriceObservation,
    ResearchEvidence,
    SourceManifestEntry,
    assess_freshness,
    make_evidence_id,
    match_price_date,
    resolve_instrument,
)


def fundamental(*, publication_date: date, retrieval_day: int) -> FundamentalFact:
    return FundamentalFact(
        evidence_id=make_evidence_id(
            "fundamental",
            "amber",
            "revenue",
            "fy2026",
            publication_date.isoformat(),
        ),
        company_id="amber",
        metric_name="revenue",
        value=Decimal("100"),
        unit="INR million",
        reporting_period="FY2026",
        period_end=date(2026, 3, 31),
        publication_date=publication_date,
        source_id="amber-fy2026-results",
        source_locator="page 2",
        evidence_type=EvidenceType.REPORTED_FACT,
        retrieval_timestamp=datetime(2026, 9, retrieval_day, tzinfo=UTC),
        extraction_confidence=ExtractionConfidence.HIGH,
    )


def test_snapshot_uses_publication_date_and_stable_evidence_ids() -> None:
    assert EvidenceConfig().analysis_as_of == date(2026, 9, 8)
    available = fundamental(publication_date=date(2026, 5, 16), retrieval_day=8)
    same_fact_retrieved_later = fundamental(publication_date=date(2026, 5, 16), retrieval_day=9)
    future = fundamental(publication_date=date(2026, 9, 9), retrieval_day=9)

    snapshot = EvidenceSnapshot.create(
        analysis_as_of=date(2026, 9, 8),
        fundamentals=(future, available),
    )

    assert available.period_end < available.publication_date
    assert available.evidence_id == same_fact_retrieved_later.evidence_id
    assert snapshot.fundamentals == (available,)
    assert snapshot.temporal_exclusions[0].evidence_id == future.evidence_id
    assert snapshot.temporal_exclusions[0].reason == "published_after_analysis_as_of"


def test_price_validation_corporate_action_status_and_identifiers() -> None:
    observation = PriceObservation(
        evidence_id="price-amber-2026-09-08",
        instrument_id="amber",
        trading_date=date(2026, 9, 8),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        adjusted_close=Decimal("103"),
        volume=Decimal("1000"),
        corporate_action_status=CorporateActionStatus.ADJUSTED_BY_SOURCE,
        source_id="yahoo-chart-amber",
        retrieval_timestamp=datetime(2026, 9, 8, 12, tzinfo=UTC),
    )

    assert observation.corporate_action_status is CorporateActionStatus.ADJUSTED_BY_SOURCE
    assert resolve_instrument("AMBER").company_id == "amber"
    assert resolve_instrument("540902").company_id == "amber"
    with pytest.raises(UnsupportedIdentifierError, match="Unsupported instrument identifier"):
        resolve_instrument("NOT-A-SYMBOL")
    with pytest.raises(EvidenceValidationError, match="high price"):
        replace(observation, high=Decimal("90"))


def test_freshness_states_are_explicit_and_threshold_is_optional() -> None:
    as_of = date(2026, 9, 8)

    assert assess_freshness(None, as_of=as_of, max_age_days=None).state is DataState.MISSING
    not_assessed = assess_freshness(date(2026, 1, 1), as_of=as_of, max_age_days=None)
    assert not_assessed.state is DataState.AVAILABLE
    assert not_assessed.age_days == 250
    assert (
        assess_freshness(date(2026, 1, 1), as_of=as_of, max_age_days=180).state is DataState.STALE
    )


def test_price_alignment_requires_exact_date_and_never_uses_future_data() -> None:
    prices = (
        PriceObservation(
            evidence_id="price-amber-2026-09-07",
            instrument_id="amber",
            trading_date=date(2026, 9, 7),
            open=Decimal("100"),
            high=Decimal("104"),
            low=Decimal("99"),
            close=Decimal("102"),
            adjusted_close=Decimal("102"),
            volume=Decimal("1000"),
            corporate_action_status=CorporateActionStatus.ADJUSTED_BY_SOURCE,
            source_id="recorded-market-fixture",
            retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
        ),
        PriceObservation(
            evidence_id="price-amber-2026-09-09",
            instrument_id="amber",
            trading_date=date(2026, 9, 9),
            open=Decimal("105"),
            high=Decimal("108"),
            low=Decimal("104"),
            close=Decimal("107"),
            adjusted_close=Decimal("107"),
            volume=Decimal("900"),
            corporate_action_status=CorporateActionStatus.ADJUSTED_BY_SOURCE,
            source_id="recorded-market-fixture",
            retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
        ),
    )

    assert match_price_date(prices, instrument_id="amber", target=date(2026, 9, 7)) == prices[0]
    with pytest.raises(MissingEvidenceError, match="No exact price observation"):
        match_price_date(prices, instrument_id="amber", target=date(2026, 9, 8))


def test_research_conflicts_remain_linked_and_future_claims_are_excluded() -> None:
    first_id = make_evidence_id("research", "dbl", "net debt", "page 1")
    second_id = make_evidence_id("research", "dbl", "net debt", "page 5")
    first = ResearchEvidence(
        evidence_id=first_id,
        company_id="dbl",
        claim="Net debt was approximately INR 19bn.",
        evidence_type=EvidenceType.REPORTED_FACT,
        publication_date=date(2026, 5, 15),
        source_id="research-dbl-2026-05-15",
        source_locator="page 1",
        relevant_period="Q4 FY2026",
        extraction_confidence=ExtractionConfidence.MEDIUM,
        conflicting_evidence_ids=(second_id,),
        retrieval_timestamp=datetime(2026, 9, 8, tzinfo=UTC),
    )
    second = replace(
        first,
        evidence_id=second_id,
        claim="Standalone net debt was approximately INR 18.8bn.",
        source_locator="page 5",
        conflicting_evidence_ids=(first_id,),
    )
    future = replace(
        first,
        evidence_id=make_evidence_id("research", "dbl", "future"),
        publication_date=date(2026, 9, 9),
        conflicting_evidence_ids=(),
    )

    snapshot = EvidenceSnapshot.create(
        analysis_as_of=date(2026, 9, 8), research=(future, second, first)
    )

    assert snapshot.research == tuple(sorted((first, second), key=lambda item: item.evidence_id))
    assert snapshot.temporal_exclusions[0].evidence_id == future.evidence_id


def test_source_published_after_snapshot_date_is_excluded() -> None:
    future_source = SourceManifestEntry(
        source_id="future-filing",
        title="Future filing",
        source_type="official_company_filing",
        location="https://example.com/future.pdf",
        publication_date=date(2026, 9, 9),
        retrieval_timestamp=datetime(2026, 9, 9, tzinfo=UTC),
        coverage="future",
        content_sha256=None,
        validation_status="temporally_invalid",
        is_secondary=False,
    )

    snapshot = EvidenceSnapshot.create(analysis_as_of=date(2026, 9, 8), sources=(future_source,))

    assert snapshot.sources == ()
    assert snapshot.temporal_exclusions[0].reason == ("source_published_after_analysis_as_of")
