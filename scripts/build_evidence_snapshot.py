"""Build the offline Phase 4 snapshot from captured public and supplied sources."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from enam_assessment.evidence import (
    EVIDENCE_ANALYSIS_AS_OF,
    EvidenceSnapshot,
    SourceManifestEntry,
)
from enam_assessment.evidence_adapters import (
    normalize_fundamental_rows,
    normalize_research_rows,
    parse_nifty_tri,
    parse_yahoo_chart,
)
from enam_assessment.evidence_io import write_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--amber", type=Path, required=True)
    parser.add_argument("--dbl", type=Path, required=True)
    parser.add_argument("--zee", type=Path, required=True)
    parser.add_argument("--welspun", type=Path, required=True)
    parser.add_argument("--nifty", type=Path, required=True)
    parser.add_argument("--retrieval-timestamp", type=datetime.fromisoformat, required=True)
    parser.add_argument(
        "--analysis-as-of", type=date.fromisoformat, default=EVIDENCE_ANALYSIS_AS_OF
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    curated: Any = json.loads(args.curated.read_text(encoding="utf-8"))
    if not isinstance(curated, dict):
        raise ValueError("Curated evidence root must be a JSON object")
    retrieval_timestamp: datetime = args.retrieval_timestamp
    prices = []
    market_files = (
        ("amber", "AMBER.NS", "yahoo-chart-amber", args.amber),
        ("dbl", "DBL.NS", "yahoo-chart-dbl", args.dbl),
        ("zee", "ZEEL.NS", "yahoo-chart-zee", args.zee),
        ("welspun", "WELSPUNLIV.NS", "yahoo-chart-welspun", args.welspun),
    )
    for instrument_id, symbol, source_id, path in market_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        prices.extend(
            parse_yahoo_chart(
                payload,
                instrument_id=instrument_id,
                expected_symbol=symbol,
                source_id=source_id,
                retrieval_timestamp=retrieval_timestamp,
            )
        )
    prices.extend(
        parse_nifty_tri(
            json.loads(args.nifty.read_text(encoding="utf-8")),
            instrument_id="nifty-500-tri",
            source_id="official-nifty-500-tri",
            retrieval_timestamp=retrieval_timestamp,
        )
    )

    sources = tuple(
        SourceManifestEntry(
            source_id=str(item["source_id"]),
            title=str(item["title"]),
            source_type=str(item["source_type"]),
            location=str(item["location"]),
            publication_date=(
                date.fromisoformat(str(item["publication_date"]))
                if item.get("publication_date") is not None
                else None
            ),
            retrieval_timestamp=retrieval_timestamp,
            coverage=str(item["coverage"]),
            content_sha256=(
                str(item["content_sha256"]) if item.get("content_sha256") is not None else None
            ),
            validation_status=str(item["validation_status"]),
            is_secondary=bool(item["is_secondary"]),
            notes=str(item.get("notes", "")),
        )
        for item in curated["sources"]
    )
    snapshot = EvidenceSnapshot.create(
        analysis_as_of=args.analysis_as_of,
        fundamentals=normalize_fundamental_rows(
            curated["fundamentals"], retrieval_timestamp=retrieval_timestamp
        ),
        research=normalize_research_rows(
            curated["research"], retrieval_timestamp=retrieval_timestamp
        ),
        prices=tuple(prices),
        sources=sources,
    )
    write_snapshot(snapshot, args.output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(
            {
                "analysis_as_of": args.analysis_as_of.isoformat(),
                "manifest_sha256": snapshot.manifest_sha256,
                "sources": [source.stable_payload() for source in snapshot.sources],
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
