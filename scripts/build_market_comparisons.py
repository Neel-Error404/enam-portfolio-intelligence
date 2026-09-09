"""Build exact-date market comparisons from the protected workbook and public snapshot."""

from __future__ import annotations

import argparse
import getpass
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from enam_assessment.evidence import EVIDENCE_ANALYSIS_AS_OF
from enam_assessment.evidence_io import read_snapshot
from enam_assessment.ingestion import ingest_workbook
from enam_assessment.market_analysis import MarketComparison, compare_realized_lots

COMPANY_INSTRUMENTS = {
    "Amber Enterprises": "amber",
    "Dilip Buildcon": "dbl",
    "Zee Entertainment Enterprises": "zee",
    "Welspun Living": "welspun",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--analysis-as-of", type=date.fromisoformat, default=EVIDENCE_ANALYSIS_AS_OF
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = getpass.getpass("Workbook password (not stored): ")
    ingestion = ingest_workbook(args.workbook, password=password)
    snapshot = read_snapshot(args.snapshot)
    comparisons = compare_realized_lots(
        ingestion,
        prices=snapshot.prices,
        company_instruments=COMPANY_INSTRUMENTS,
        primary_benchmark_id="bse-500-tri",
        secondary_benchmark_id="nifty-500-tri",
        analysis_as_of=args.analysis_as_of,
    )
    payload = {
        "analysis_as_of": args.analysis_as_of.isoformat(),
        "method": (
            "Exact purchase and sale trading dates; adjusted closes for companies; "
            "official total-return levels for benchmarks; no date shifting or filling."
        ),
        "primary_benchmark": {
            "instrument_id": "bse-500-tri",
            "status": "unavailable_authentication_required",
        },
        "secondary_benchmark": {
            "instrument_id": "nifty-500-tri",
            "status": "available",
        },
        "summary": _summaries(comparisons),
        "comparisons": [_comparison_dict(item) for item in comparisons],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _summaries(comparisons: tuple[MarketComparison, ...]) -> list[dict[str, object]]:
    grouped: dict[str, list[MarketComparison]] = defaultdict(list)
    for comparison in comparisons:
        grouped[comparison.company].append(comparison)
    grouped["Overall"] = list(comparisons)
    summaries: list[dict[str, object]] = []
    for company in sorted(grouped, key=lambda value: (value != "Overall", value)):
        rows = grouped[company]
        stock = [row for row in rows if row.stock_return is not None]
        primary = [row for row in rows if row.primary_benchmark_return is not None]
        secondary = [
            row
            for row in rows
            if row.stock_return is not None and row.secondary_benchmark_return is not None
        ]
        summaries.append(
            {
                "company": company,
                "eligible_lots": len(rows),
                "stock_matched_lots": len(stock),
                "primary_benchmark_matched_lots": len(primary),
                "secondary_benchmark_matched_lots": len(secondary),
                "stock_matched_purchase_cost": str(
                    sum((row.purchase_cost for row in stock), start=Decimal("0"))
                ),
                "cost_weighted_stock_return": _weighted_return(stock, "stock_return"),
                "cost_weighted_secondary_return": _weighted_return(
                    secondary, "secondary_benchmark_return"
                ),
                "cost_weighted_secondary_relative_return": _weighted_return(
                    secondary, "secondary_relative_return"
                ),
            }
        )
    return summaries


def _weighted_return(rows: list[MarketComparison], attribute: str) -> str | None:
    if not rows:
        return None
    denominator = sum((row.purchase_cost for row in rows), start=Decimal("0"))
    numerator = Decimal("0")
    for row in rows:
        value = getattr(row, attribute)
        if not isinstance(value, Decimal):
            raise ValueError(f"Comparison attribute {attribute!r} is unavailable")
        numerator += row.purchase_cost * value
    return str(numerator / denominator)


def _comparison_dict(item: MarketComparison) -> dict[str, object]:
    payload = asdict(item)
    for key in (
        "purchase_cost",
        "stock_return",
        "primary_benchmark_return",
        "primary_relative_return",
        "secondary_benchmark_return",
        "secondary_relative_return",
    ):
        value = payload[key]
        payload[key] = None if value is None else str(value)
    payload["purchase_date"] = item.purchase_date.isoformat()
    payload["sale_date"] = item.sale_date.isoformat()
    payload["validation_status"] = item.validation_status.value
    return payload


if __name__ == "__main__":
    main()
