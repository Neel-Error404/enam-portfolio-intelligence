"""Bounded, citation-grounded portfolio-intelligence questions and answers."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from .errors import MemoProviderError, QuestionContextError, QuestionValidationError
from .memo import DecisionMemoInput, MemoClaim, MemoEvidenceItem
from .memo_provider import (
    AzureOpenAIResponsesProvider,
    AzureOpenAISettings,
    MemoProvider,
    ProviderUsage,
)
from .portfolio_session import HoldingsOverlay, ScenarioDelta, calculate_holdings_overlay
from .portfolio_ui import DashboardData

ANSWER_CONTRACT_VERSION = "portfolio-answer-v1"
ANSWER_PROMPT_VERSION = "portfolio-intelligence-prompt-v1"
CHARS_PER_TOKEN = 4
DEFAULT_QUESTION_INPUT_TOKENS = 4000
DEFAULT_BRIEF_INPUT_TOKENS = 3500
MAX_ANSWER_WORDS = 450
HISTORY_EXCERPT_CHARACTERS = 420
REQUEST_OVERHEAD_TOKENS = 1600
INTERACTIVE_REQUEST_OVERHEAD_TOKENS = 1460
INTERACTIVE_DEPLOYMENT = "gpt-5.6-terra"
INTERACTIVE_REASONING_EFFORT = "low"
INTERACTIVE_MAX_OUTPUT_TOKENS = 2200
DBL_CONSOLIDATED_NET_DEBT_EVIDENCE_ID = "fundamental-dbl-consolidated-net-debt-fy26"
DBL_FY26_EBITDA_EVIDENCE_ID = "fundamental-c02d7f1564a6c6e4"


class QuestionScope(StrEnum):
    """Explicit routes supported by the bounded context selector."""

    COMPANY_BRIEF = "company_brief"
    COMPANY = "company"
    PORTFOLIO = "portfolio"
    COMPARISON = "comparison"
    BEHAVIOUR = "behaviour"
    SCENARIO_DELTA = "scenario_delta"


class AnswerStatus(StrEnum):
    """Observable state of one optional generated explanation."""

    GENERATED = "generated"
    NOT_CONFIGURED = "not_configured"
    GENERATION_FAILED = "generation_failed"
    VALIDATION_FAILED = "validation_failed"
    REQUEST_TOO_BROAD = "request_too_broad"


ANSWER_SECTION_NAMES = (
    "supporting_points",
    "counterpoints",
    "relevant_unknowns",
    "change_conditions",
)


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    """Minimum evidence sent to the model; display provenance stays local."""

    evidence_id: str
    company_or_instrument_id: str
    evidence_kind: str
    category: str
    available_date: str
    reporting_period_or_date: str
    unit: str
    content: str

    def stable_payload(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SelectedArtifact:
    """One structured UI artifact explicitly attached to a conversation."""

    artifact_id: str
    label: str
    origin_page: str
    company_ids: tuple[str, ...]
    payload: dict[str, object]
    evidence_ids: tuple[str, ...] = ()
    required_evidence_ids: tuple[str, ...] = ()

    def stable_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "label": self.label,
            "origin_page": self.origin_page,
            "company_ids": list(self.company_ids),
            "payload": self.payload,
            "evidence_ids": list(self.evidence_ids),
            "required_evidence_ids": list(self.required_evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class ConversationHistoryItem:
    """Bounded prior turn used only for conversational continuity, never as evidence."""

    question: str
    direct_answer: str
    scope: QuestionScope
    company_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    context_hash: str

    def stable_payload(self) -> dict[str, object]:
        return {
            "question": self.question,
            "direct_answer": self.direct_answer,
            "scope": self.scope.value,
            "company_ids": list(self.company_ids),
            "supporting_evidence_ids": list(self.evidence_ids),
            "context_hash": self.context_hash,
        }

    def model_payload(self) -> dict[str, object]:
        """Return a bounded, explicitly marked excerpt for conversational continuity."""
        truncated = len(self.direct_answer) > HISTORY_EXCERPT_CHARACTERS
        excerpt = self.direct_answer
        if truncated:
            excerpt = self.direct_answer[: HISTORY_EXCERPT_CHARACTERS - 3].rstrip() + "..."
        return {
            "question": self.question,
            "direct_answer_excerpt": excerpt,
            "answer_excerpt_truncated": truncated,
            "scope": self.scope.value,
            "company_ids": list(self.company_ids),
            "supporting_evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class QuestionContext:
    """Deterministic, budgeted context for one explicit user question."""

    scope: QuestionScope
    normalized_question: str
    company_ids: tuple[str, ...]
    decision_snapshot_sha256: str
    context_hash: str
    decision_facts: tuple[dict[str, object], ...]
    evidence: tuple[ContextEvidence, ...]
    included_evidence_ids: tuple[str, ...]
    excluded_evidence_ids: tuple[str, ...]
    analysis_context: dict[str, object]
    scenario_delta: dict[str, object] | None
    active_portfolio: dict[str, object]
    selected_artifacts: tuple[SelectedArtifact, ...]
    conversation_history: tuple[ConversationHistoryItem, ...]
    serialized_characters: int
    input_token_budget: int

    def stable_payload(self) -> dict[str, object]:
        return {
            "scope": self.scope.value,
            "question": self.normalized_question,
            "company_ids": list(self.company_ids),
            "decision_snapshot_sha256": self.decision_snapshot_sha256,
            "context_hash": self.context_hash,
            "decision_facts": list(self.decision_facts),
            "evidence": [item.stable_payload() for item in self.evidence],
            "included_evidence_ids": list(self.included_evidence_ids),
            "excluded_evidence_ids": list(self.excluded_evidence_ids),
            "analysis_context": self.analysis_context,
            "scenario_delta": self.scenario_delta,
            "active_portfolio": self.active_portfolio,
            "selected_artifacts": [item.stable_payload() for item in self.selected_artifacts],
            "conversation_history": [item.model_payload() for item in self.conversation_history],
            "serialized_characters": self.serialized_characters,
            "input_token_budget": self.input_token_budget,
        }

    def model_payload(self) -> dict[str, object]:
        """Return only fields the model needs; audit-only budget metadata stays local."""
        return {
            "scope": self.scope.value,
            "question": self.normalized_question,
            "company_ids": list(self.company_ids),
            "decision_snapshot_sha256": self.decision_snapshot_sha256,
            "context_hash": self.context_hash,
            "decision_facts": list(self.decision_facts),
            "evidence": [item.stable_payload() for item in self.evidence],
            "analysis_context": self.analysis_context,
            "scenario_delta": self.scenario_delta,
            "selected_artifacts": [_artifact_metadata(item) for item in self.selected_artifacts],
            "conversation_history": [item.model_payload() for item in self.conversation_history],
        }


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Validated narrative whose deterministic identity is fixed by the request."""

    scope: QuestionScope
    company_ids: tuple[str, ...]
    decision_snapshot_sha256: str
    context_hash: str
    answer_contract_version: str
    prompt_version: str
    direct_answer: MemoClaim
    sections: dict[str, tuple[MemoClaim, ...]]

    def stable_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "scope": self.scope.value,
            "company_ids": list(self.company_ids),
            "decision_snapshot_sha256": self.decision_snapshot_sha256,
            "context_hash": self.context_hash,
            "answer_contract_version": self.answer_contract_version,
            "prompt_version": self.prompt_version,
            "direct_answer": _claim_payload(self.direct_answer),
        }
        payload.update(
            {
                name: [_claim_payload(claim) for claim in self.sections[name]]
                for name in ANSWER_SECTION_NAMES
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class AnswerArtifact:
    """One generated or explicitly unavailable portfolio-intelligence answer."""

    status: AnswerStatus
    context: QuestionContext
    provider: str
    deployment_id: str
    reasoning_effort: str
    max_output_tokens: int
    answer: GroundedAnswer | None
    response_id: str | None
    usage: ProviderUsage | None
    error: str | None

    def stable_payload(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "context": self.context.stable_payload(),
            "provider": self.provider,
            "deployment_id": self.deployment_id,
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
            "answer": self.answer.stable_payload() if self.answer else None,
            "response_id": self.response_id,
            "usage": asdict(self.usage) if self.usage else None,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class CitationCard:
    """Local provenance resolved after generation; it is not repeated in model context."""

    evidence_id: str
    display_label: str
    provenance_class: str
    company_or_instrument_id: str
    category: str
    available_date: str
    reporting_period_or_date: str
    unit: str
    source_title: str
    source_type: str
    source_locator: str
    summary: str
    content: str
    conflicting_evidence_ids: tuple[str, ...]


def normalize_question(question: str) -> str:
    """Normalize whitespace for deterministic routing and session caching."""
    normalized = " ".join(question.strip().split())
    if not normalized:
        raise QuestionContextError("Enter a question before requesting portfolio intelligence.")
    if len(normalized) > 500:
        raise QuestionContextError("Question is too broad: use at most 500 characters.")
    return normalized


def build_interactive_provider(environment: Mapping[str, str]) -> MemoProvider:
    """Create the bounded Azure provider only after an explicit user request."""
    configured = dict(environment)
    configured.setdefault("AZURE_OPENAI_DEPLOYMENT", INTERACTIVE_DEPLOYMENT)
    configured["AZURE_OPENAI_REASONING_EFFORT"] = environment.get(
        "ENAM_INTELLIGENCE_REASONING_EFFORT", INTERACTIVE_REASONING_EFFORT
    )
    configured["AZURE_OPENAI_MAX_OUTPUT_TOKENS"] = environment.get(
        "ENAM_INTELLIGENCE_MAX_OUTPUT_TOKENS", str(INTERACTIVE_MAX_OUTPUT_TOKENS)
    )
    settings = AzureOpenAISettings.from_environment(configured)
    if settings.deployment != INTERACTIVE_DEPLOYMENT:
        raise QuestionContextError(
            f"Interactive portfolio intelligence requires deployment {INTERACTIVE_DEPLOYMENT!r}; "
            f"received {settings.deployment!r}."
        )
    return AzureOpenAIResponsesProvider(settings)


def build_hard_gates_artifact(data: DashboardData, company_id: str) -> SelectedArtifact:
    """Build the displayed hard-gate attachment, preserving required calculation sources."""
    decision = data.decision(company_id)
    non_passing = tuple(gate for gate in decision.hard_gates if gate["status"] != "pass")
    gate_payloads: list[dict[str, object]] = []
    required_evidence_ids: tuple[str, ...] = ()
    for gate in non_passing:
        payload: dict[str, object] = {
            "code": gate["code"],
            "status": gate["status"],
            "consequence": gate["consequence"],
        }
        if gate["status"] == "fail":
            payload["calculation"] = gate["explanation"]
        if company_id == "dbl" and gate["code"] == "balance_sheet_liquidity_and_funding":
            required_evidence_ids = (
                DBL_CONSOLIDATED_NET_DEBT_EVIDENCE_ID,
                DBL_FY26_EBITDA_EVIDENCE_ID,
            )
            gate_evidence_ids = cast(list[str], gate["evidence_ids"])
            missing = sorted(set(required_evidence_ids) - set(gate_evidence_ids))
            if missing:
                raise QuestionContextError(
                    "DBL balance-sheet gate is missing required calculation evidence IDs: "
                    f"{missing}."
                )
            net_debt = _required_metric_value(
                data,
                company_id="dbl",
                evidence_id=DBL_CONSOLIDATED_NET_DEBT_EVIDENCE_ID,
                metric_name="consolidated_net_debt",
            )
            ebitda = _required_metric_value(
                data,
                company_id="dbl",
                evidence_id=DBL_FY26_EBITDA_EVIDENCE_ID,
                metric_name="consolidated_ebitda",
            )
            threshold_match = re.search(
                r"prototype ([0-9]+(?:\.[0-9]+)?)-times sell threshold",
                str(gate["explanation"]),
            )
            if threshold_match is None:
                raise QuestionContextError(
                    "DBL balance-sheet gate explanation does not contain its sell threshold."
                )
            threshold = Decimal(threshold_match.group(1))
            ratio = net_debt / ebitda
            payload["calculation"] = {
                "numerator": {
                    "value": f"₹{net_debt:,.0f} crore",
                    "evidence_id": DBL_CONSOLIDATED_NET_DEBT_EVIDENCE_ID,
                },
                "denominator": {
                    "value": f"₹{ebitda:,.0f} crore",
                    "evidence_id": DBL_FY26_EBITDA_EVIDENCE_ID,
                },
                "result": f"approximately {ratio:.2f}x",
                "sell_threshold": f"{threshold:.1f}x",
                "comparison": "above_sell_threshold",
                "summary": (
                    f"₹{net_debt:,.0f} crore ÷ ₹{ebitda:,.0f} crore is approximately "
                    f"{ratio:.2f}× against the configured {threshold:.1f}× sell threshold."
                ),
            }
        gate_payloads.append(payload)

    evidence_ids = tuple(
        dict.fromkeys(
            evidence_id
            for gate in non_passing
            for evidence_id in cast(list[str], gate["evidence_ids"])
        )
    )
    return SelectedArtifact(
        artifact_id=f"{company_id}-hard-gates",
        label=f"{decision.company_name} hard gates",
        origin_page="Company Intelligence",
        company_ids=(company_id,),
        payload={
            "frozen_decision": {
                "underlying_stance": decision.underlying_stance,
                "final_action": decision.final_portfolio_action,
                "target_weight": decision.target_weight,
                "weighted_principle_score": decision.weighted_principle_score,
                "human_review_required": decision.human_review_required,
                "human_review_reasons": list(decision.human_review_reasons),
            },
            "hard_gates": gate_payloads,
            "missing_information": list(decision.missing_data_flags),
        },
        evidence_ids=evidence_ids,
        required_evidence_ids=required_evidence_ids,
    )


def build_question_context(
    data: DashboardData,
    *,
    scope: QuestionScope,
    question: str,
    company_ids: tuple[str, ...] = (),
    scenario_delta: ScenarioDelta | None = None,
    active_overlay: HoldingsOverlay | None = None,
    selected_artifacts: tuple[SelectedArtifact, ...] = (),
    conversation_history: tuple[ConversationHistoryItem, ...] = (),
    input_token_budget: int = DEFAULT_QUESTION_INPUT_TOKENS,
    system_prompt: str | None = None,
) -> QuestionContext:
    """Budget the complete request; default prompt loading requires the application root."""
    normalized = normalize_question(question)
    overhead_tokens = (
        REQUEST_OVERHEAD_TOKENS
        if scope is QuestionScope.COMPANY_BRIEF
        else INTERACTIVE_REQUEST_OVERHEAD_TOKENS
    )
    if input_token_budget <= overhead_tokens:
        raise QuestionContextError(
            f"Input-token budget must exceed the {overhead_tokens}-token request overhead reserve."
        )
    if system_prompt is None:
        prompt_path = Path("prompts") / "portfolio_intelligence_prompt_v1.txt"
        try:
            system_prompt = prompt_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise QuestionContextError(
                f"Cannot load the interactive prompt at {prompt_path.resolve()}. "
                "Run from the application root or supply system_prompt explicitly."
            ) from exc
    selected_ids = _validated_scope(data, scope, company_ids, scenario_delta)
    overlay = active_overlay or calculate_holdings_overlay(data.decisions)
    _validate_overlay(data, overlay)
    artifacts = _validated_artifacts(data, selected_artifacts)
    history = list(conversation_history[-3:])
    identity_ids = (
        () if scope in {QuestionScope.PORTFOLIO, QuestionScope.BEHAVIOUR} else selected_ids
    )
    decisions = tuple(data.decision(company_id) for company_id in selected_ids)
    topic = _topic(normalized, scope)
    artifact_carries_frozen_decision = any(
        "frozen_decision" in artifact.payload for artifact in artifacts
    )
    decision_facts = (
        ()
        if topic == "behaviour" or artifact_carries_frozen_decision
        else tuple(
            _compact_decision(item, topic, overlay.company_weights[item.company_id])
            for item in decisions
        )
    )
    candidates = _candidate_evidence_ids(decisions, topic)
    candidates.update(
        evidence_id for artifact in artifacts for evidence_id in artifact.evidence_ids
    )
    candidates.update(evidence_id for turn in history for evidence_id in turn.evidence_ids)
    evidence_index = {
        item.evidence_id: item
        for company_id in selected_ids
        for item in data.evidence_by_company[company_id]
    }
    allowed_owners = {
        *selected_ids,
        str(data.portfolio["primary_benchmark_id"]),
        str(data.portfolio["secondary_benchmark_id"]),
        "portfolio",
    }
    unknown = candidates - set(evidence_index)
    if unknown:
        raise QuestionContextError(
            f"Question context references unknown evidence: {sorted(unknown)}."
        )
    mismatched = sorted(
        evidence_id
        for evidence_id in candidates
        if evidence_index[evidence_id].company_or_instrument_id not in allowed_owners
    )
    if mismatched:
        raise QuestionContextError(
            f"Question context includes evidence for the wrong company: {mismatched}."
        )
    source_evidence = tuple(
        _compact_evidence(evidence_index[evidence_id]) for evidence_id in sorted(candidates)
    )
    analysis_context = _analysis_context(data, scope, selected_ids)
    scenario_payload = _compact_scenario_delta(scenario_delta) if scenario_delta else None
    active_portfolio = _compact_active_portfolio(overlay)
    derived_evidence = _derived_evidence(
        data,
        scope=scope,
        decisions=decisions,
        analysis_context=analysis_context,
        scenario_delta=scenario_delta,
        active_overlay=overlay,
        selected_artifacts=artifacts,
    )
    evidence = tuple(sorted(source_evidence + derived_evidence, key=lambda item: item.evidence_id))
    if any(
        date.fromisoformat(item.available_date) > decisions[0].decision_date for item in evidence
    ):
        raise QuestionContextError("Question context contains evidence after the decision date.")
    base: dict[str, object] = {
        "scope": scope.value,
        "question": normalized,
        "company_ids": list(identity_ids),
        "decision_snapshot_sha256": str(data.portfolio["snapshot_sha256"]),
        "decision_facts": list(decision_facts),
        "analysis_context": analysis_context,
        "scenario_delta": scenario_payload,
        "selected_artifacts": [_artifact_metadata(item) for item in artifacts],
        "conversation_history": [item.model_payload() for item in history],
        "answer_contract_version": ANSWER_CONTRACT_VERSION,
        "prompt_version": ANSWER_PROMPT_VERSION,
    }
    included: list[ContextEvidence] = list(evidence)
    excluded: list[str] = []
    protected_ids = {
        item.evidence_id
        for item in derived_evidence
        if (
            not artifacts
            or not item.evidence_id.startswith("decision:")
            or item.evidence_id == "decision:portfolio-summary"
        )
    }
    protected_ids.update(
        evidence_id for artifact in artifacts for evidence_id in artifact.required_evidence_ids
    )

    def selected_context() -> QuestionContext:
        payload_for_hash = {
            **base,
            "evidence": [item.stable_payload() for item in included],
            "included_evidence_ids": [item.evidence_id for item in included],
            "excluded_evidence_ids": sorted(excluded),
        }
        context_hash = sha256(_canonical_json(payload_for_hash).encode("utf-8")).hexdigest()
        return QuestionContext(
            scope=scope,
            normalized_question=normalized,
            company_ids=identity_ids,
            decision_snapshot_sha256=str(data.portfolio["snapshot_sha256"]),
            context_hash=context_hash,
            decision_facts=decision_facts,
            evidence=tuple(included),
            included_evidence_ids=tuple(item.evidence_id for item in included),
            excluded_evidence_ids=tuple(sorted(excluded)),
            analysis_context=analysis_context,
            scenario_delta=scenario_payload,
            active_portfolio=active_portfolio,
            selected_artifacts=artifacts,
            conversation_history=tuple(history),
            serialized_characters=_serialized_size(base, included),
            input_token_budget=input_token_budget,
        )

    context_character_budget = (input_token_budget - overhead_tokens) * CHARS_PER_TOKEN
    while included:
        context = selected_context()
        estimate = estimated_request_tokens(
            context,
            system_prompt=system_prompt,
            response_schema=answer_response_json_schema(context),
        )
        if (
            context.serialized_characters <= context_character_budget
            and estimate <= input_token_budget
        ):
            return context
        removable_index = next(
            (
                index
                for index in range(len(included) - 1, -1, -1)
                if included[index].evidence_id not in protected_ids
            ),
            None,
        )
        if removable_index is not None:
            excluded.append(included.pop(removable_index).evidence_id)
            continue
        if history:
            history.pop(0)
            base["conversation_history"] = [item.model_payload() for item in history]
            continue
        raise QuestionContextError(
            f"Request too broad for the {input_token_budget}-token input budget. Narrow the scope "
            "or question."
        )
    raise QuestionContextError(
        "Request budget leaves no citable evidence. Narrow the question or increase the "
        "explicit input-token budget."
    )


def estimated_request_tokens(
    context: QuestionContext, *, system_prompt: str, response_schema: dict[str, object]
) -> int:
    """Conservatively estimate request size where exact Azure tokenization is unavailable."""
    characters = (
        len(system_prompt)
        + len(_canonical_json(context.model_payload()))
        + len(_canonical_json(response_schema))
    )
    return (characters + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def answer_cache_key(context: QuestionContext) -> str:
    """Return a stable key so Streamlit reruns do not duplicate a live request."""
    return sha256(
        f"{context.scope.value}\n{context.normalized_question.lower()}\n{context.context_hash}".encode()
    ).hexdigest()


def history_item_from_artifact(artifact: AnswerArtifact) -> ConversationHistoryItem:
    """Freeze one accepted turn for bounded follow-ups without treating prose as evidence."""
    if artifact.status.value != AnswerStatus.GENERATED.value or artifact.answer is None:
        raise QuestionContextError(
            "Only validated generated answers can enter conversation history."
        )
    claims = (artifact.answer.direct_answer,) + tuple(
        claim for values in artifact.answer.sections.values() for claim in values
    )
    evidence_ids = tuple(
        dict.fromkeys(
            evidence_id
            for claim in claims
            for evidence_id in claim.evidence_ids
            if not evidence_id.startswith(
                ("decision:", "session:", "scenario:", "analysis:", "artifact:")
            )
        )
    )
    return ConversationHistoryItem(
        question=artifact.context.normalized_question,
        direct_answer=artifact.answer.direct_answer.text,
        scope=artifact.context.scope,
        company_ids=artifact.context.company_ids,
        evidence_ids=evidence_ids,
        context_hash=artifact.context.context_hash,
    )


def get_or_generate_answer(
    cache: dict[str, AnswerArtifact],
    context: QuestionContext,
    provider: MemoProvider,
    *,
    system_prompt: str,
) -> tuple[AnswerArtifact, bool]:
    """Return the session-cached answer or make exactly one provider call."""
    key = answer_cache_key(context)
    cached = cache.get(key)
    if cached is not None:
        return cached, True
    artifact = generate_grounded_answer(context, provider, system_prompt=system_prompt)
    cache[key] = artifact
    return artifact, False


def citation_cards(
    data: DashboardData,
    context: QuestionContext,
    evidence_ids: tuple[str, ...],
) -> tuple[CitationCard, ...]:
    """Resolve allow-listed citations into locally held display provenance."""
    unknown = set(evidence_ids) - set(context.included_evidence_ids)
    if unknown:
        raise QuestionValidationError(
            f"Cannot resolve citations outside the request allow-list: {sorted(unknown)}."
        )
    source_index = {
        item.evidence_id: item for items in data.evidence_by_company.values() for item in items
    }
    compact_index = {item.evidence_id: item for item in context.evidence}
    cards: list[CitationCard] = []
    for evidence_id in dict.fromkeys(evidence_ids):
        compact = compact_index[evidence_id]
        source = source_index.get(evidence_id)
        if source is None:
            source_title, source_type, source_locator = _derived_source_metadata(evidence_id)
            conflicts: tuple[str, ...] = ()
        else:
            source_title = source.source_title
            source_type = source.source_type
            source_locator = source.source_locator
            conflicts = source.conflicting_evidence_ids
        cards.append(
            CitationCard(
                evidence_id=evidence_id,
                display_label=_citation_display_label(evidence_id, compact),
                provenance_class=_citation_provenance_class(evidence_id, compact),
                company_or_instrument_id=compact.company_or_instrument_id,
                category=compact.category,
                available_date=compact.available_date,
                reporting_period_or_date=compact.reporting_period_or_date,
                unit=compact.unit,
                source_title=source_title,
                source_type=source_type,
                source_locator=source_locator,
                summary=_citation_summary(evidence_id, compact),
                content=compact.content,
                conflicting_evidence_ids=conflicts,
            )
        )
    return tuple(cards)


def _citation_display_label(evidence_id: str, evidence: ContextEvidence) -> str:
    if evidence_id.startswith("decision:"):
        return f"Frozen {_readable_company_id(evidence.company_or_instrument_id)} decision"
    if evidence_id == "session:active-portfolio":
        return "Current session portfolio calculation"
    if evidence_id == "analysis:historical-behaviour":
        return "Historical investor-behaviour analysis"
    if evidence_id.startswith("scenario:"):
        return "Session scenario calculation"
    if evidence_id.startswith("artifact:"):
        if evidence_id == "artifact:dbl-hard-gates":
            return "Attached DBL hard-gate analysis"
        name = evidence_id.removeprefix("artifact:").replace("-", " ")
        return f"Attached {name.title()} analysis"

    head = evidence.content.split(";", maxsplit=1)[0].strip()
    if ":" in head:
        metric, value = (part.strip() for part in head.split(":", maxsplit=1))
        readable_metric = _readable_metric_name(metric)
        readable_value = _readable_evidence_value(value)
        period = _short_period(evidence.reporting_period_or_date)
        prefix = f"{period} " if period != "not separately stated" else ""
        return f"{prefix}{readable_metric} — {readable_value}"
    excerpt = head if len(head) <= 72 else head[:69].rstrip() + "..."
    return excerpt or evidence_id


def _readable_company_id(company_id: str) -> str:
    return {
        "amber": "Amber",
        "dbl": "DBL",
        "welspun": "Welspun",
        "zee": "Zee",
    }.get(company_id, company_id.upper())


def _readable_metric_name(metric: str) -> str:
    acronyms = {"ebitda": "EBITDA", "pat": "PAT", "roe": "ROE", "roce": "ROCE"}
    return " ".join(acronyms.get(word, word) for word in metric.replace("_", " ").split())


def _citation_provenance_class(evidence_id: str, evidence: ContextEvidence) -> str:
    if evidence_id.startswith("decision:"):
        return "Frozen decision record"
    if evidence_id == "session:active-portfolio":
        return "Active-session calculation"
    if evidence_id.startswith("scenario:") or evidence_id.startswith("analysis:"):
        return "Deterministic calculation"
    if evidence_id.startswith("artifact:"):
        return "Attached application artifact"
    if evidence.evidence_kind in {"fundamental_fact", "research_evidence", "price_observation"}:
        return "Supplied source evidence"
    return "Source evidence"


def _citation_summary(evidence_id: str, evidence: ContextEvidence) -> str:
    if evidence_id == "artifact:dbl-hard-gates":
        value = json.loads(evidence.content)
        payload = _object(value, "DBL hard-gate citation")
        gates = _array(payload.get("hard_gates"), "DBL hard-gate citation.hard_gates")
        failed = next(
            (
                _object(item, "DBL hard-gate citation.hard_gates[]")
                for item in gates
                if isinstance(item, dict)
                and item.get("code") == "balance_sheet_liquidity_and_funding"
            ),
            None,
        )
        frozen = _object(payload.get("frozen_decision"), "DBL hard-gate citation.frozen_decision")
        if failed is None:
            raise QuestionValidationError(
                "DBL hard-gate citation is missing balance_sheet_liquidity_and_funding."
            )
        calculation = _object(
            failed.get("calculation"),
            "DBL hard-gate citation.balance_sheet_liquidity_and_funding.calculation",
        )
        return (
            f"{calculation['summary']} Frozen decision: "
            f"{str(frozen['underlying_stance']).upper()} stance, "
            f"{str(frozen['final_action']).upper()} action, "
            f"{Decimal(str(frozen['target_weight'])) * Decimal('100'):.1f}% target, "
            f"{frozen['weighted_principle_score']} principle score."
        )
    if evidence_id == "session:active-portfolio":
        return evidence.content
    return evidence.content


def _readable_evidence_value(value: str) -> str:
    crore_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?) INR crore", value)
    if crore_match:
        number = Decimal(crore_match.group(1))
        return f"₹{number:,.2f}".rstrip("0").rstrip(".") + " crore"
    percent_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?) percent(?: of .+)?", value)
    if percent_match:
        return f"{percent_match.group(1)}%"
    return value


def _short_period(value: str) -> str:
    match = re.fullmatch(r"FY(20)([0-9]{2})", value)
    return f"FY{match.group(2)}" if match else value


def answer_response_json_schema(context: QuestionContext) -> dict[str, object]:
    """Pin response identity and citations to this exact question context."""
    company_item_schema: dict[str, object] = {"type": "string"}
    if context.company_ids:
        company_item_schema["enum"] = list(context.company_ids)
    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "evidence_ids", "category"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "evidence_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(context.included_evidence_ids)},
            },
            "category": {"type": "string", "minLength": 1},
        },
    }
    properties: dict[str, object] = {
        "scope": {"type": "string", "enum": [context.scope.value]},
        "company_ids": {
            "type": "array",
            "items": company_item_schema,
            "minItems": len(context.company_ids),
            "maxItems": len(context.company_ids),
        },
        "decision_snapshot_sha256": {
            "type": "string",
            "enum": [context.decision_snapshot_sha256],
        },
        "context_hash": {"type": "string", "enum": [context.context_hash]},
        "answer_contract_version": {"type": "string", "enum": [ANSWER_CONTRACT_VERSION]},
        "prompt_version": {"type": "string", "enum": [ANSWER_PROMPT_VERSION]},
        "direct_answer": claim,
        "supporting_points": {"type": "array", "minItems": 1, "maxItems": 3, "items": claim},
        "counterpoints": {"type": "array", "maxItems": 2, "items": claim},
        "relevant_unknowns": {"type": "array", "maxItems": 3, "items": claim},
        "change_conditions": {"type": "array", "maxItems": 3, "items": claim},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def generate_grounded_answer(
    context: QuestionContext,
    provider: MemoProvider,
    *,
    system_prompt: str,
) -> AnswerArtifact:
    """Run one bounded provider call and fail closed on generation or validation errors."""
    schema = answer_response_json_schema(context)
    estimate = estimated_request_tokens(
        context, system_prompt=system_prompt, response_schema=schema
    )
    if estimate > context.input_token_budget:
        return _failed_answer(
            context,
            provider,
            AnswerStatus.REQUEST_TOO_BROAD,
            f"Estimated request size {estimate} exceeds budget "
            f"{context.input_token_budget} tokens.",
        )
    try:
        result = provider.generate(
            system_prompt=system_prompt,
            context=context.model_payload(),
            response_schema=schema,
        )
    except MemoProviderError as exc:
        return _failed_answer(context, provider, AnswerStatus.GENERATION_FAILED, str(exc))
    try:
        answer = parse_and_validate_answer(result.output_text, context)
    except QuestionValidationError as exc:
        return AnswerArtifact(
            AnswerStatus.VALIDATION_FAILED,
            context,
            provider.provider_name,
            provider.deployment_id,
            provider.reasoning_effort,
            provider.max_output_tokens,
            None,
            result.response_id,
            result.usage,
            str(exc),
        )
    return AnswerArtifact(
        AnswerStatus.GENERATED,
        context,
        provider.provider_name,
        provider.deployment_id,
        provider.reasoning_effort,
        provider.max_output_tokens,
        answer,
        result.response_id,
        result.usage,
        None,
    )


def parse_and_validate_answer(response_text: str, context: QuestionContext) -> GroundedAnswer:
    """Validate response identity, bounded length, and the exact evidence allow-list."""
    try:
        value: Any = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise QuestionValidationError(
            f"Portfolio-intelligence response is not JSON: {exc}"
        ) from exc
    raw = _object(value, "answer")
    required = {
        "scope",
        "company_ids",
        "decision_snapshot_sha256",
        "context_hash",
        "answer_contract_version",
        "prompt_version",
        "direct_answer",
        *ANSWER_SECTION_NAMES,
    }
    if set(raw) != required:
        raise QuestionValidationError("Answer fields do not match portfolio-answer-v1.")
    expected = {
        "scope": context.scope.value,
        "company_ids": list(context.company_ids),
        "decision_snapshot_sha256": context.decision_snapshot_sha256,
        "context_hash": context.context_hash,
        "answer_contract_version": ANSWER_CONTRACT_VERSION,
        "prompt_version": ANSWER_PROMPT_VERSION,
    }
    for field, expected_value in expected.items():
        if raw.get(field) != expected_value:
            raise QuestionValidationError(
                f"Answer changed immutable field {field!r}: expected {expected_value!r}, "
                f"received {raw.get(field)!r}."
            )
    allow_list = set(context.included_evidence_ids)
    direct = _parse_claim(raw["direct_answer"], "direct_answer", allow_list)
    sections = {
        name: tuple(
            _parse_claim(item, f"{name}[{index}]", allow_list)
            for index, item in enumerate(_array(raw[name], name))
        )
        for name in ANSWER_SECTION_NAMES
    }
    if not 1 <= len(sections["supporting_points"]) <= 3:
        raise QuestionValidationError("supporting_points must contain one to three claims.")
    if len(sections["counterpoints"]) > 2:
        raise QuestionValidationError("counterpoints may contain at most two claims.")
    claims = (direct,) + tuple(claim for name in ANSWER_SECTION_NAMES for claim in sections[name])
    word_count = sum(len(claim.text.split()) for claim in claims)
    if word_count > MAX_ANSWER_WORDS:
        raise QuestionValidationError(
            f"Answer contains {word_count} words; maximum is {MAX_ANSWER_WORDS}."
        )
    return GroundedAnswer(
        scope=context.scope,
        company_ids=context.company_ids,
        decision_snapshot_sha256=context.decision_snapshot_sha256,
        context_hash=context.context_hash,
        answer_contract_version=ANSWER_CONTRACT_VERSION,
        prompt_version=ANSWER_PROMPT_VERSION,
        direct_answer=direct,
        sections=sections,
    )


def _validated_scope(
    data: DashboardData,
    scope: QuestionScope,
    company_ids: tuple[str, ...],
    scenario_delta: ScenarioDelta | None,
) -> tuple[str, ...]:
    known = {item.company_id for item in data.decisions}
    unique = tuple(dict.fromkeys(company_ids))
    expected = {
        QuestionScope.COMPANY_BRIEF: 1,
        QuestionScope.COMPANY: 1,
        QuestionScope.PORTFOLIO: 4,
        QuestionScope.COMPARISON: 2,
        QuestionScope.BEHAVIOUR: 4,
        QuestionScope.SCENARIO_DELTA: 1,
    }[scope]
    if scope in {QuestionScope.PORTFOLIO, QuestionScope.BEHAVIOUR} and not unique:
        unique = tuple(sorted(known))
    if len(unique) != expected or not set(unique) <= known:
        raise QuestionContextError(
            f"Scope {scope.value!r} requires {expected} valid unique company ID(s)."
        )
    if scope is QuestionScope.SCENARIO_DELTA:
        if scenario_delta is None or scenario_delta.company_id != unique[0]:
            raise QuestionContextError("Scenario-delta scope requires a matching recalculation.")
    elif scenario_delta is not None:
        raise QuestionContextError("Scenario delta is only valid for scenario_delta scope.")
    return unique


def _compact_decision(
    decision: DecisionMemoInput, topic: str, active_weight: object
) -> dict[str, object]:
    identity: dict[str, object] = {
        "company_id": decision.company_id,
        "company_name": decision.company_name,
        "underlying_stance": decision.underlying_stance,
        "final_action": decision.final_portfolio_action,
    }
    if topic == "portfolio":
        # Portfolio actions, targets, gates, and active weights are carried by the
        # citable derived records. Repeating them here can exhaust the compact
        # interactive budget before any external evidence is considered.
        return identity
    if topic == "behaviour":
        payload = identity
    elif topic == "scenario":
        payload = {
            **identity,
            "current_price": decision.current_price,
            "frozen_working_weight": _compact_ratio(decision.working_current_weight),
            "active_session_weight": _compact_ratio(active_weight),
            "target_weight": _compact_ratio(decision.target_weight),
        }
    else:
        payload = {
            **identity,
            "frozen_working_weight": _compact_ratio(decision.working_current_weight),
            "active_session_weight": _compact_ratio(active_weight),
            "target_weight": _compact_ratio(decision.target_weight),
            "human_review_required": decision.human_review_required,
            "human_review_reasons": list(decision.human_review_reasons[:2]),
        }
    if topic not in {"portfolio", "behaviour", "scenario"}:
        limit = 2 if topic == "comparison" else 3
        payload.update(
            {
                "weighted_principle_score": decision.weighted_principle_score,
                "confidence": decision.confidence,
                "missing_information": list(decision.missing_data_flags[:limit]),
                "change_triggers": list(decision.change_triggers[:limit]),
            }
        )
        if topic != "comparison":
            payload["provisional_holdings"] = decision.provisional_holdings
    elif topic == "portfolio":
        payload["common_drivers"] = list(decision.common_drivers[:2])
    if topic in {"risk", "general", "portfolio", "brief"}:
        payload["material_gates"] = [
            {
                "code": item["code"],
                "status": item["status"],
                "consequence": item["consequence"],
            }
            for item in decision.hard_gates
            if item["status"] != "pass" or topic == "brief"
        ]
    if topic in {"quality", "general", "comparison", "brief"}:
        payload["principles"] = [
            {
                "dimension": item["dimension"],
                "score": item["score"],
                **(
                    {"data_quality": item["data_quality"]}
                    if topic not in {"comparison", "general"}
                    else {}
                ),
                **({"rule": item["rule"]} if topic in {"quality", "brief"} else {}),
            }
            for item in decision.principle_scores
        ]
    if topic in {"valuation", "general", "comparison", "brief"}:
        payload["scenarios"] = [
            {
                "name": _scenario_name(item),
                "target_price": item["target_price"],
                "price_cagr": item["price_cagr"],
            }
            for item in decision.scenarios
            if topic != "comparison" or _scenario_name(item) == "base"
        ]
    return payload


def _candidate_evidence_ids(decisions: tuple[DecisionMemoInput, ...], topic: str) -> set[str]:
    candidates: set[str] = set()
    for decision in decisions:
        if topic in {"risk", "general", "portfolio", "brief"}:
            for gate in decision.hard_gates:
                if gate["status"] != "pass" or topic == "brief":
                    candidates.update(cast(list[str], gate["evidence_ids"]))
        if topic in {"quality", "general", "comparison", "brief"}:
            for score in decision.principle_scores:
                candidates.update(cast(list[str], score["evidence_ids"]))
                candidates.update(cast(list[str], score["counter_evidence_ids"]))
        if topic in {"valuation", "general", "comparison", "scenario", "brief"}:
            for scenario in decision.scenarios:
                if _scenario_name(scenario) == "base" or topic == "comparison":
                    candidates.update(_scenario_evidence(scenario))
        if topic in {"change", "missing"}:
            candidates.update(decision.evidence_ids[:6])
        if topic == "behaviour":
            candidates.update(decision.evidence_ids[:3])
    return candidates


def _compact_evidence(item: MemoEvidenceItem) -> ContextEvidence:
    return ContextEvidence(
        evidence_id=item.evidence_id,
        company_or_instrument_id=item.company_or_instrument_id,
        evidence_kind=item.evidence_kind,
        category=item.evidence_classification,
        available_date=item.available_date.isoformat(),
        reporting_period_or_date=_evidence_period(item),
        unit=_evidence_unit(item),
        content=item.content,
    )


def _derived_evidence(
    data: DashboardData,
    *,
    scope: QuestionScope,
    decisions: tuple[DecisionMemoInput, ...],
    analysis_context: dict[str, object],
    scenario_delta: ScenarioDelta | None,
    active_overlay: HoldingsOverlay,
    selected_artifacts: tuple[SelectedArtifact, ...],
) -> tuple[ContextEvidence, ...]:
    """Create citable deterministic facts without pretending they are external sources."""
    decision_date = decisions[0].decision_date.isoformat()
    records: list[ContextEvidence] = []
    if scope in {QuestionScope.PORTFOLIO, QuestionScope.BEHAVIOUR}:
        summary = "; ".join(
            f"{decision.company_id}: {decision.underlying_stance}/"
            f"{decision.final_portfolio_action}"
            + (
                f", target {_compact_ratio(decision.target_weight)}, non-pass gates "
                + (
                    ",".join(
                        f"{gate['code']}={gate['status']}/{gate['consequence']}"
                        for gate in decision.hard_gates
                        if gate["status"] != "pass"
                    )
                    or "none"
                )
                if scope is QuestionScope.PORTFOLIO
                else ""
            )
            for decision in decisions
        )
        records.append(
            ContextEvidence(
                evidence_id="decision:portfolio-summary",
                company_or_instrument_id="portfolio",
                evidence_kind="deterministic_decision",
                category="deterministic_decision",
                available_date=decision_date,
                reporting_period_or_date=decision_date,
                unit="mixed",
                content=summary,
            )
        )
    else:
        for decision in decisions:
            records.append(
                ContextEvidence(
                    evidence_id=f"decision:{decision.company_id}",
                    company_or_instrument_id=decision.company_id,
                    evidence_kind="deterministic_decision",
                    category="deterministic_decision",
                    available_date=decision_date,
                    reporting_period_or_date=decision_date,
                    unit="mixed",
                    content=(
                        f"{decision.company_name}: stance {decision.underlying_stance}; final "
                        f"action {decision.final_portfolio_action}; target weight "
                        f"{decision.target_weight}; "
                        f"principle score {decision.weighted_principle_score}; human review "
                        f"required={decision.human_review_required}."
                    ),
                )
            )
    selected_behaviour_artifact = any(
        artifact.origin_page == "Investor Behaviour" for artifact in selected_artifacts
    )
    if scope is QuestionScope.BEHAVIOUR and not selected_behaviour_artifact:
        findings = cast(list[dict[str, object]], data.historical["findings"])
        behaviour_summary = {
            "coverage": data.historical["coverage"],
            "findings": [
                {
                    "title": item["title"],
                    "observed": item["observed"],
                    "counter_evidence": item["counter_evidence"],
                    "confidence": item["confidence"],
                }
                for item in findings
            ],
        }
        records.append(
            ContextEvidence(
                evidence_id="analysis:historical-behaviour",
                company_or_instrument_id="portfolio",
                evidence_kind="historical_analysis",
                category="deterministic_calculation",
                available_date=str(data.historical["analysis_cutoff"]),
                reporting_period_or_date=str(data.historical["analysis_cutoff"]),
                unit="mixed",
                content=_canonical_json(behaviour_summary),
            )
        )
    if scope is QuestionScope.SCENARIO_DELTA and scenario_delta is not None:
        records.append(
            ContextEvidence(
                evidence_id=f"scenario:{scenario_delta.company_id}:{scenario_delta.scenario_name}",
                company_or_instrument_id=scenario_delta.company_id,
                evidence_kind="scenario_calculation",
                category="deterministic_sandbox_calculation",
                available_date=decision_date,
                reporting_period_or_date=decision_date,
                unit="mixed",
                content=_canonical_json(_compact_scenario_delta(scenario_delta)),
            )
        )
    records.append(_active_portfolio_evidence(active_overlay, decision_date))
    records.extend(_artifact_evidence(artifact, decision_date) for artifact in selected_artifacts)
    return tuple(sorted(records, key=lambda item: item.evidence_id))


def _compact_active_portfolio(overlay: HoldingsOverlay) -> dict[str, object]:
    return {
        "basis": (
            "supplied_workbook_with_session_overrides"
            if overlay.uses_session_values
            else "supplied_workbook_defaults"
        ),
        "denominator": "represented_four_holdings_plus_entered_cash",
        "available_cash": str(overlay.available_cash),
        "cash_source": overlay.cash_source,
        "cash_weight": _compact_ratio(overlay.cash_weight),
        "total_represented_value": str(overlay.total_value.quantize(Decimal("0.01"))),
        "holdings": [
            {
                "company_id": item.company_id,
                "shares": str(item.shares),
                "weight": _compact_ratio(overlay.company_weights[item.company_id]),
                "source": item.source,
            }
            for item in overlay.holdings
        ],
        "concentration": {
            "top_two_weight": _compact_ratio(overlay.concentration.top_two_weight),
            "top_three_weight": _compact_ratio(overlay.concentration.top_three_weight),
            "hhi": _compact_ratio(overlay.concentration.hhi),
            "effective_positions": str(
                overlay.concentration.effective_positions.quantize(Decimal("0.001"))
            ),
            "requires_review": overlay.concentration.requires_review,
            "review_reasons": list(overlay.concentration.review_reasons),
        },
    }


def _active_portfolio_evidence(overlay: HoldingsOverlay, decision_date: str) -> ContextEvidence:
    holdings = "; ".join(
        f"{item.company_id} shares {item.shares}, weight "
        f"{_compact_ratio(overlay.company_weights[item.company_id])}"
        for item in overlay.holdings
    )
    entered = [item.company_id for item in overlay.holdings if item.source == "user_entered"]
    share_source = (
        f"session-entered share overrides are active only for {entered}"
        if entered
        else "no session-entered share overrides are active"
    )
    return ContextEvidence(
        evidence_id="session:active-portfolio",
        company_or_instrument_id="portfolio",
        evidence_kind="session_calculation",
        category="user_input_and_deterministic_calculation",
        available_date=decision_date,
        reporting_period_or_date="current session",
        unit="mixed",
        content=(
            f"{holdings}; cash {overlay.available_cash}, cash source {overlay.cash_source}, "
            f"cash weight {_compact_ratio(overlay.cash_weight)}; HHI "
            f"{_compact_ratio(overlay.concentration.hhi)}, top-two "
            f"{_compact_ratio(overlay.concentration.top_two_weight)}, top-three "
            f"{_compact_ratio(overlay.concentration.top_three_weight)}; denominator is represented "
            f"four holdings plus entered cash; {share_source}."
        ),
    )


def _artifact_evidence(artifact: SelectedArtifact, decision_date: str) -> ContextEvidence:
    return ContextEvidence(
        evidence_id=f"artifact:{artifact.artifact_id}",
        company_or_instrument_id=(
            artifact.company_ids[0] if len(artifact.company_ids) == 1 else "portfolio"
        ),
        evidence_kind="application_artifact",
        category="deterministic_application_artifact",
        available_date=decision_date,
        reporting_period_or_date=decision_date,
        unit="mixed",
        content=json.dumps(
            artifact.payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    )


def _artifact_metadata(artifact: SelectedArtifact) -> dict[str, object]:
    return {
        "artifact_id": artifact.artifact_id,
        "label": artifact.label,
        "origin_page": artifact.origin_page,
        "company_ids": list(artifact.company_ids),
    }


def _validate_overlay(data: DashboardData, overlay: HoldingsOverlay) -> None:
    expected = {item.company_id for item in data.decisions}
    actual = {item.company_id for item in overlay.holdings}
    if actual != expected or set(overlay.company_weights) != expected:
        raise QuestionContextError(
            "Active portfolio overlay must contain exactly the four decision companies."
        )


def _validated_artifacts(
    data: DashboardData, artifacts: tuple[SelectedArtifact, ...]
) -> tuple[SelectedArtifact, ...]:
    known = {item.company_id for item in data.decisions}
    unique: dict[str, SelectedArtifact] = {}
    for artifact in artifacts:
        if not artifact.artifact_id.strip() or not artifact.label.strip():
            raise QuestionContextError("Selected artifacts require a stable ID and label.")
        if not set(artifact.company_ids) <= known:
            raise QuestionContextError(
                f"Artifact {artifact.artifact_id!r} references an unknown company."
            )
        missing_required = sorted(set(artifact.required_evidence_ids) - set(artifact.evidence_ids))
        if missing_required:
            raise QuestionContextError(
                f"Artifact {artifact.artifact_id!r} has required evidence IDs that are not "
                f"declared as evidence: {missing_required}."
            )
        unique[artifact.artifact_id] = artifact
    return tuple(unique[key] for key in sorted(unique))


def _required_metric_value(
    data: DashboardData,
    *,
    company_id: str,
    evidence_id: str,
    metric_name: str,
) -> Decimal:
    evidence = next(
        (item for item in data.evidence_by_company[company_id] if item.evidence_id == evidence_id),
        None,
    )
    if evidence is None:
        raise QuestionContextError(
            f"Required evidence {evidence_id!r} is unavailable for {company_id!r}."
        )
    match = re.fullmatch(
        rf"{re.escape(metric_name)}: ([0-9]+(?:\.[0-9]+)?) INR crore;.*",
        evidence.content,
    )
    if match is None:
        raise QuestionContextError(
            f"Required evidence {evidence_id!r} does not contain {metric_name!r} in INR crore."
        )
    return Decimal(match.group(1))


def _evidence_period(item: MemoEvidenceItem) -> str:
    match = re.search(r"(?:reporting|relevant) period ([^.;]+)", item.content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if item.evidence_kind == "price_observation":
        return item.available_date.isoformat()
    return "not separately stated"


def _evidence_unit(item: MemoEvidenceItem) -> str:
    lowered = item.content.lower()
    units: list[str] = []
    if "inr crore" in lowered:
        units.append("INR crore")
    elif "inr " in lowered:
        units.append("INR")
    units.extend(
        label
        for token, label in (
            ("percent", "percent"),
            ("bps", "basis points"),
            ("days", "days"),
        )
        if token in lowered
    )
    if item.evidence_kind == "price_observation":
        return "INR per share"
    return ", ".join(dict.fromkeys(units)) or "not separately stated"


def _compact_ratio(value: object) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.000001")), "f")


def _analysis_context(
    data: DashboardData, scope: QuestionScope, company_ids: tuple[str, ...]
) -> dict[str, object]:
    if scope is not QuestionScope.BEHAVIOUR:
        return {}
    return {
        "source": "evidence/historical_analysis_summary.json",
        "analysis_cutoff": data.historical["analysis_cutoff"],
        "company_ids": list(company_ids),
    }


def _topic(question: str, scope: QuestionScope) -> str:
    if scope is QuestionScope.COMPANY_BRIEF:
        return "brief"
    if scope is QuestionScope.PORTFOLIO:
        return "portfolio"
    if scope is QuestionScope.COMPARISON:
        return "comparison"
    if scope is QuestionScope.BEHAVIOUR:
        return "behaviour"
    if scope is QuestionScope.SCENARIO_DELTA:
        return "scenario"
    lowered = question.lower()
    topics = (
        ("valuation", ("valuation", "cagr", "target", "scenario", "price")),
        ("risk", ("risk", "gate", "debt", "governance", "review")),
        ("missing", ("missing", "unknown", "uncertain")),
        ("change", ("change", "trigger")),
        ("quality", ("quality", "support", "evidence", "growth", "management")),
        ("behaviour", ("behaviour", "historical", "holding", "trading")),
    )
    for topic, words in topics:
        if any(word in lowered for word in words):
            return topic
    return "general"


def _serialized_size(base: Mapping[str, object], included: list[ContextEvidence]) -> int:
    return len(
        _canonical_json(
            {
                **base,
                "evidence": [item.stable_payload() for item in included],
            }
        )
    )


def _failed_answer(
    context: QuestionContext,
    provider: MemoProvider,
    status: AnswerStatus,
    error: str,
) -> AnswerArtifact:
    return AnswerArtifact(
        status,
        context,
        provider.provider_name,
        provider.deployment_id,
        provider.reasoning_effort,
        provider.max_output_tokens,
        None,
        None,
        None,
        error,
    )


def _parse_claim(value: object, label: str, allow_list: set[str]) -> MemoClaim:
    raw = _object(value, label)
    if set(raw) != {"text", "evidence_ids", "category"}:
        raise QuestionValidationError(f"{label} has unexpected fields.")
    text = raw.get("text")
    category = raw.get("category")
    ids = raw.get("evidence_ids")
    if not isinstance(text, str) or not text.strip():
        raise QuestionValidationError(f"{label}.text must be non-empty.")
    if not isinstance(category, str) or not category.strip():
        raise QuestionValidationError(f"{label}.category must be non-empty.")
    if not isinstance(ids, list) or not ids or not all(isinstance(item, str) for item in ids):
        raise QuestionValidationError(f"{label} requires one or more evidence IDs.")
    unknown = set(ids) - allow_list
    if unknown:
        raise QuestionValidationError(
            f"{label} cites evidence outside the allow-list: {sorted(unknown)}."
        )
    return MemoClaim(text.strip(), tuple(dict.fromkeys(ids)), category.strip())


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise QuestionValidationError(f"{label} must be an array.")
    return value


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise QuestionValidationError(f"{label} must be an object.")
    return cast(dict[str, object], value)


def _scenario_name(item: dict[str, object]) -> str:
    return str(cast(dict[str, object], item["input"])["name"])


def _scenario_evidence(item: dict[str, object]) -> tuple[str, ...]:
    raw = cast(dict[str, object], item["input"])["evidence_ids"]
    return tuple(str(value) for value in cast(list[object], raw))


def _claim_payload(claim: MemoClaim) -> dict[str, object]:
    return {
        "text": claim.text,
        "evidence_ids": list(claim.evidence_ids),
        "category": claim.category,
    }


def _derived_source_metadata(evidence_id: str) -> tuple[str, str, str]:
    if evidence_id == "analysis:historical-behaviour":
        return (
            "Frozen historical-analysis summary",
            "deterministic_calculation",
            "evidence/historical_analysis_summary.json",
        )
    if evidence_id == "decision:portfolio-concentration":
        return (
            "Frozen portfolio decision snapshot",
            "deterministic_calculation",
            "decision/decision_snapshot.json:current_concentration",
        )
    if evidence_id.startswith("decision:"):
        return (
            "Frozen company decision snapshot",
            "deterministic_decision",
            f"decision/decision_snapshot.json:{evidence_id.removeprefix('decision:')}",
        )
    if evidence_id.startswith("scenario:"):
        return (
            "Session Scenario Lab result",
            "deterministic_sandbox_calculation",
            "session-local scenario recalculation",
        )
    if evidence_id == "session:active-portfolio":
        return (
            "Active session portfolio",
            "user_input_and_deterministic_calculation",
            "session-local holdings overlay",
        )
    if evidence_id.startswith("artifact:"):
        return (
            "Selected application artifact",
            "deterministic_application_artifact",
            "session-local selected context",
        )
    raise QuestionValidationError(f"No local provenance is available for {evidence_id!r}.")


def _compact_scenario_delta(delta: ScenarioDelta) -> dict[str, object]:
    return {
        "company_id": delta.company_id,
        "scenario_name": delta.scenario_name,
        "baseline": {
            "target_price": str(delta.baseline.target_price),
            "price_cagr": str(delta.baseline.price_cagr),
        },
        "overrides": delta.overrides,
        "recalculated": {
            "target_price": str(delta.recalculated.target_price),
            "price_cagr": str(delta.recalculated.price_cagr),
        },
        "target_price_delta": str(delta.target_price_delta),
        "price_cagr_delta": str(delta.price_cagr_delta),
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
