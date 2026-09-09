import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from enam_assessment.errors import SourceRetrievalError
from enam_assessment.evidence import (
    CorporateActionStatus,
    EvidenceSnapshot,
    EvidenceType,
    ExtractionConfidence,
    FundamentalFact,
    ResearchEvidence,
    SourceManifestEntry,
    make_evidence_id,
)
from enam_assessment.evidence_adapters import (
    JsonSourceAdapter,
    normalize_fundamental_rows,
    normalize_research_rows,
    parse_nifty_tri,
    parse_yahoo_chart,
)
from enam_assessment.evidence_io import read_snapshot, write_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
RETRIEVED_AT = datetime(2026, 9, 8, 12, tzinfo=UTC)


def read_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_market_adapters_parse_recorded_fixtures_without_forward_filling() -> None:
    stock = parse_yahoo_chart(
        read_fixture("yahoo_chart_amber.json"),
        instrument_id="amber",
        expected_symbol="AMBER.NS",
        source_id="yahoo-chart-amber",
        retrieval_timestamp=RETRIEVED_AT,
    )
    benchmark = parse_nifty_tri(
        read_fixture("nifty_tri.json"),
        instrument_id="nifty-500-tri",
        source_id="niftyindices-tri",
        retrieval_timestamp=RETRIEVED_AT,
    )

    assert [item.trading_date for item in stock] == [date(2026, 9, 7), date(2026, 9, 9)]
    assert stock[0].adjusted_close == Decimal("101.5")
    assert stock[0].corporate_action_status is CorporateActionStatus.ADJUSTED_BY_SOURCE
    assert [item.close for item in benchmark] == [Decimal("12345.67"), Decimal("12400.00")]
    assert benchmark[0].corporate_action_status is CorporateActionStatus.NOT_APPLICABLE

    direct = parse_nifty_tri(
        {"data": [{"TRIDate": "08 Sep 2026", "Total Returns Index": "12400.00"}]},
        instrument_id="nifty-500-tri",
        source_id="niftyindices-tri",
        retrieval_timestamp=RETRIEVED_AT,
    )
    assert direct[0].trading_date == date(2026, 9, 8)


def test_fundamental_and_research_normalization_preserves_conflicts() -> None:
    fundamentals = normalize_fundamental_rows(
        [
            {
                "company_id": "dbl",
                "metric_name": "net_debt",
                "value": "19",
                "unit": "INR billion",
                "reporting_period": "Q4 FY2026",
                "period_end": "2026-03-31",
                "publication_date": "2026-05-15",
                "source_id": "research-dbl-2026-05-15",
                "source_locator": "page 1",
                "evidence_type": "reported_fact",
                "extraction_confidence": "medium",
                "conflicting_evidence_ids": ["research-dbl-net-debt-p5"],
            }
        ],
        retrieval_timestamp=RETRIEVED_AT,
    )
    research = normalize_research_rows(
        [
            {
                "evidence_id": "research-dbl-net-debt-p5",
                "company_id": "dbl",
                "claim": "Standalone net debt was approximately INR 18.8bn.",
                "evidence_type": "reported_fact",
                "publication_date": "2026-05-15",
                "source_id": "research-dbl-2026-05-15",
                "source_locator": "page 5",
                "relevant_period": "Q4 FY2026",
                "extraction_confidence": "medium",
                "conflicting_evidence_ids": [],
            }
        ],
        retrieval_timestamp=RETRIEVED_AT,
    )

    assert fundamentals[0].conflicting_evidence_ids == ("research-dbl-net-debt-p5",)
    assert research[0].evidence_id == "research-dbl-net-debt-p5"


def test_adapter_network_failure_is_explicit_and_does_not_change_provider() -> None:
    def fail(_: str) -> object:
        raise OSError("connection refused")

    adapter = JsonSourceAdapter(fetch_json=fail)
    with pytest.raises(SourceRetrievalError, match="configured source"):
        adapter.fetch("https://example.invalid/data")


def test_snapshot_and_manifest_are_deterministic_for_identical_inputs(
    tmp_path: Path,
) -> None:
    fact = FundamentalFact(
        evidence_id=make_evidence_id("fundamental", "amber", "revenue", "fy2026"),
        company_id="amber",
        metric_name="revenue",
        value=Decimal("100"),
        unit="INR million",
        reporting_period="FY2026",
        period_end=date(2026, 3, 31),
        publication_date=date(2026, 5, 16),
        source_id="amber-fy2026-results",
        source_locator="page 2",
        evidence_type=EvidenceType.REPORTED_FACT,
        retrieval_timestamp=RETRIEVED_AT,
        extraction_confidence=ExtractionConfidence.HIGH,
    )
    claim = ResearchEvidence(
        evidence_id=make_evidence_id("research", "amber", "guidance", "page 1"),
        company_id="amber",
        claim="Management guided to 30-35% mobility growth.",
        evidence_type=EvidenceType.MANAGEMENT_GUIDANCE,
        publication_date=date(2026, 5, 16),
        source_id="research-amber-2026-05-16",
        source_locator="page 1",
        relevant_period="FY2027",
        extraction_confidence=ExtractionConfidence.MEDIUM,
        conflicting_evidence_ids=(),
        retrieval_timestamp=RETRIEVED_AT,
    )
    manifest = (
        SourceManifestEntry(
            source_id="amber-fy2026-results",
            title="Amber FY2026 results",
            source_type="official_company_filing",
            location="https://example.com/amber-results.pdf",
            publication_date=date(2026, 5, 15),
            retrieval_timestamp=RETRIEVED_AT,
            coverage="FY2026 results",
            content_sha256="a" * 64,
            validation_status="validated",
            is_secondary=False,
        ),
    )

    one = EvidenceSnapshot.create(
        analysis_as_of=date(2026, 9, 8), fundamentals=(fact,), research=(claim,), sources=manifest
    )
    two = EvidenceSnapshot.create(
        analysis_as_of=date(2026, 9, 8), research=(claim,), sources=manifest, fundamentals=(fact,)
    )

    assert one == two
    assert one.manifest_sha256 == two.manifest_sha256
    output = tmp_path / "snapshot.json"
    write_snapshot(one, output)
    assert read_snapshot(output) == one
