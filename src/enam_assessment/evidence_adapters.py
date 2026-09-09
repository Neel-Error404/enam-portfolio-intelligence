"""Small adapters that normalize recorded JSON evidence into package contracts."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from .errors import EvidenceValidationError, SourceRetrievalError
from .evidence import (
    CorporateActionStatus,
    DataState,
    EvidenceType,
    ExtractionConfidence,
    FundamentalFact,
    PriceObservation,
    ResearchEvidence,
    make_evidence_id,
)


class JsonSourceAdapter:
    """Fetch from one configured JSON source without provider fallback."""

    def __init__(self, *, fetch_json: Callable[[str], object]) -> None:
        self._fetch_json = fetch_json

    def fetch(self, url: str) -> object:
        try:
            return self._fetch_json(url)
        except OSError as exc:
            raise SourceRetrievalError(
                f"Could not retrieve configured source {url!r}: {exc}"
            ) from exc


def parse_yahoo_chart(
    payload: object,
    *,
    instrument_id: str,
    expected_symbol: str,
    source_id: str,
    retrieval_timestamp: datetime,
) -> tuple[PriceObservation, ...]:
    """Normalize Yahoo chart JSON; null observations remain absent, never filled."""
    root = _mapping(payload, "Yahoo chart payload")
    chart = _mapping(root.get("chart"), "Yahoo chart payload.chart")
    if chart.get("error") not in (None, {}):
        raise EvidenceValidationError(f"Yahoo chart returned an error: {chart['error']!r}")
    results = _list(chart.get("result"), "Yahoo chart result")
    if len(results) != 1:
        raise EvidenceValidationError("Yahoo chart must contain exactly one result")
    result = _mapping(results[0], "Yahoo chart result item")
    meta = _mapping(result.get("meta"), "Yahoo chart metadata")
    if meta.get("symbol") != expected_symbol:
        raise EvidenceValidationError(
            f"Yahoo symbol mismatch: expected {expected_symbol!r}, got {meta.get('symbol')!r}"
        )
    timestamps = _list(result.get("timestamp"), "Yahoo timestamps")
    indicators = _mapping(result.get("indicators"), "Yahoo indicators")
    quote_blocks = _list(indicators.get("quote"), "Yahoo quote blocks")
    adj_blocks = _list(indicators.get("adjclose"), "Yahoo adjusted-close blocks")
    if len(quote_blocks) != 1 or len(adj_blocks) != 1:
        raise EvidenceValidationError(
            "Yahoo chart requires one quote block and one adjusted-close block"
        )
    quote = _mapping(quote_blocks[0], "Yahoo quote block")
    adjusted = _mapping(adj_blocks[0], "Yahoo adjusted-close block")
    opens = _list(quote.get("open"), "Yahoo open values")
    highs = _list(quote.get("high"), "Yahoo high values")
    lows = _list(quote.get("low"), "Yahoo low values")
    closes = _list(quote.get("close"), "Yahoo close values")
    volumes = _list(quote.get("volume"), "Yahoo volume values")
    adjusted_closes = _list(adjusted.get("adjclose"), "Yahoo adjusted-close values")
    lengths = {
        len(timestamps),
        len(opens),
        len(highs),
        len(lows),
        len(closes),
        len(volumes),
        len(adjusted_closes),
    }
    if len(lengths) != 1:
        raise EvidenceValidationError("Yahoo chart arrays have inconsistent lengths")

    observations: list[PriceObservation] = []
    for index, timestamp in enumerate(timestamps):
        if closes[index] is None or adjusted_closes[index] is None:
            continue
        trading_date = datetime.fromtimestamp(_integer(timestamp, "Yahoo timestamp"), tz=UTC).date()
        observations.append(
            PriceObservation(
                evidence_id=make_evidence_id(
                    "price", instrument_id, trading_date.isoformat(), source_id
                ),
                instrument_id=instrument_id,
                trading_date=trading_date,
                open=_optional_decimal(opens[index], "open"),
                high=_optional_decimal(highs[index], "high"),
                low=_optional_decimal(lows[index], "low"),
                close=_decimal(closes[index], "close"),
                adjusted_close=_decimal(adjusted_closes[index], "adjusted close"),
                volume=_optional_decimal(volumes[index], "volume"),
                corporate_action_status=CorporateActionStatus.ADJUSTED_BY_SOURCE,
                source_id=source_id,
                retrieval_timestamp=retrieval_timestamp,
                validation_status=DataState.AVAILABLE,
            )
        )
    return tuple(sorted(observations, key=lambda item: item.trading_date))


def parse_nifty_tri(
    payload: object,
    *,
    instrument_id: str,
    source_id: str,
    retrieval_timestamp: datetime,
) -> tuple[PriceObservation, ...]:
    """Normalize the official Nifty Indices TRI response."""
    root = _mapping(payload, "Nifty TRI payload")
    encoded_rows = root.get("d")
    if isinstance(encoded_rows, str):
        try:
            decoded = json.loads(encoded_rows)
        except json.JSONDecodeError as exc:
            raise EvidenceValidationError("Nifty TRI 'd' field is not valid JSON") from exc
    elif "data" in root:
        decoded = root["data"]
    else:
        raise EvidenceValidationError(
            "Nifty TRI payload requires either a JSON string in 'd' or a 'data' array"
        )
    rows = _list(decoded, "Nifty TRI rows")
    observations: list[PriceObservation] = []
    for raw_row in rows:
        row = _mapping(raw_row, "Nifty TRI row")
        raw_date = row.get("TRIDate", row.get("Date"))
        raw_value = row.get("Total Returns Index", row.get("TotalReturnsIndex"))
        if not isinstance(raw_date, str) or raw_value is None:
            raise EvidenceValidationError(
                "Nifty TRI row requires a date and Total Returns Index value"
            )
        trading_date = _parse_flexible_date(raw_date)
        close = _decimal(raw_value, "Total Returns Index")
        observations.append(
            PriceObservation(
                evidence_id=make_evidence_id(
                    "price", instrument_id, trading_date.isoformat(), source_id
                ),
                instrument_id=instrument_id,
                trading_date=trading_date,
                open=None,
                high=None,
                low=None,
                close=close,
                adjusted_close=close,
                volume=None,
                corporate_action_status=CorporateActionStatus.NOT_APPLICABLE,
                source_id=source_id,
                retrieval_timestamp=retrieval_timestamp,
            )
        )
    return tuple(sorted(observations, key=lambda item: item.trading_date))


def normalize_fundamental_rows(
    rows: Iterable[Mapping[str, object]], *, retrieval_timestamp: datetime
) -> tuple[FundamentalFact, ...]:
    """Normalize captured fundamental rows without altering units or definitions."""
    facts: list[FundamentalFact] = []
    for row in rows:
        company_id = _text(row, "company_id")
        metric_name = _text(row, "metric_name")
        reporting_period = _text(row, "reporting_period")
        publication_date = _iso_date(row, "publication_date")
        evidence_id = str(
            row.get("evidence_id")
            or make_evidence_id(
                "fundamental",
                company_id,
                metric_name,
                reporting_period,
                publication_date.isoformat(),
                _text(row, "source_locator"),
            )
        )
        facts.append(
            FundamentalFact(
                evidence_id=evidence_id,
                company_id=company_id,
                metric_name=metric_name,
                value=_decimal_or_text(row.get("value"), "value"),
                unit=_text(row, "unit"),
                reporting_period=reporting_period,
                period_end=_iso_date(row, "period_end"),
                publication_date=publication_date,
                source_id=_text(row, "source_id"),
                source_locator=_text(row, "source_locator"),
                evidence_type=EvidenceType(_text(row, "evidence_type")),
                retrieval_timestamp=retrieval_timestamp,
                extraction_confidence=ExtractionConfidence(_text(row, "extraction_confidence")),
                conflicting_evidence_ids=_string_tuple(row.get("conflicting_evidence_ids", [])),
            )
        )
    return tuple(sorted(facts, key=lambda item: item.evidence_id))


def normalize_research_rows(
    rows: Iterable[Mapping[str, object]], *, retrieval_timestamp: datetime
) -> tuple[ResearchEvidence, ...]:
    """Normalize supplied-research claims while preserving evidence classes."""
    claims = tuple(
        ResearchEvidence(
            evidence_id=_text(row, "evidence_id"),
            company_id=_text(row, "company_id"),
            claim=_text(row, "claim"),
            evidence_type=EvidenceType(_text(row, "evidence_type")),
            publication_date=_iso_date(row, "publication_date"),
            source_id=_text(row, "source_id"),
            source_locator=_text(row, "source_locator"),
            relevant_period=_text(row, "relevant_period"),
            extraction_confidence=ExtractionConfidence(_text(row, "extraction_confidence")),
            conflicting_evidence_ids=_string_tuple(row.get("conflicting_evidence_ids", [])),
            retrieval_timestamp=retrieval_timestamp,
        )
        for row in rows
    )
    return tuple(sorted(claims, key=lambda item: item.evidence_id))


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvidenceValidationError(f"{label} must be an object with string keys")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise EvidenceValidationError(f"{label} must be a list")
    return value


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvidenceValidationError(f"Field {key!r} must be a non-empty string")
    return value.strip()


def _iso_date(row: Mapping[str, object], key: str) -> date:
    value = _text(row, key)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise EvidenceValidationError(f"Field {key!r} must be an ISO date") from exc


def _parse_flexible_date(value: str) -> date:
    for pattern in ("%d %b %Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise EvidenceValidationError(f"Unsupported market date {value!r}")


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceValidationError(f"{label} must be numeric")
    return int(value)


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise EvidenceValidationError(f"{label} must be numeric")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise EvidenceValidationError(f"{label} must be numeric") from exc


def _optional_decimal(value: object, label: str) -> Decimal | None:
    return None if value is None else _decimal(value, label)


def _decimal_or_text(value: object, label: str) -> Decimal | str:
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            if value.strip():
                return value.strip()
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value))
    raise EvidenceValidationError(f"{label} must be numeric or non-empty text")


def _string_tuple(value: object) -> tuple[str, ...]:
    values = _list(value, "conflicting_evidence_ids")
    if not all(isinstance(item, str) and item.strip() for item in values):
        raise EvidenceValidationError("conflicting_evidence_ids must contain non-empty strings")
    return tuple(sorted(str(item).strip() for item in values))
