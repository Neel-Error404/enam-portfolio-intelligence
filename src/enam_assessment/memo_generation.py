"""Orchestration and sanitized persistence for bounded company memos."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from .errors import MemoProviderError, MemoValidationError
from .memo import (
    MEMO_CONTRACT_VERSION,
    PROMPT_VERSION,
    DecisionMemoInput,
    GeneratedMemoNarrative,
    MemoContext,
    memo_response_json_schema,
    parse_and_validate_memo_response,
)
from .memo_provider import MemoProvider, ProviderUsage


class MemoStatus(StrEnum):
    """Explicit state of an optional generated memo."""

    GENERATED = "generated"
    NOT_CONFIGURED = "not_configured"
    GENERATION_FAILED = "generation_failed"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True, slots=True)
class CompanyMemoArtifact:
    """Sanitized output combining immutable decision identity and optional narrative."""

    memo_generation_status: MemoStatus
    decision: DecisionMemoInput
    provider: str
    deployment_id: str
    reasoning_effort: str
    max_output_tokens: int
    memo_contract_version: str
    prompt_version: str
    narrative: GeneratedMemoNarrative | None
    response_id: str | None
    usage: ProviderUsage | None
    error: str | None

    def stable_payload(self) -> dict[str, object]:
        return {
            "memo_generation_status": self.memo_generation_status.value,
            "decision": self.decision.stable_payload(),
            "provider": self.provider,
            "deployment_id": self.deployment_id,
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
            "memo_contract_version": self.memo_contract_version,
            "prompt_version": self.prompt_version,
            "narrative": (self.narrative.stable_payload() if self.narrative is not None else None),
            "response_id": self.response_id,
            "usage": (
                cast(dict[str, object], asdict(self.usage)) if self.usage is not None else None
            ),
            "error": self.error,
        }


def generate_company_memo(
    context: MemoContext,
    provider: MemoProvider,
    *,
    system_prompt: str,
) -> CompanyMemoArtifact:
    """Make one controlled call and return an explicit status; never synthesize fallback text."""
    try:
        result = provider.generate(
            system_prompt=system_prompt,
            context=context.stable_payload(),
            response_schema=memo_response_json_schema(context.decision),
        )
    except MemoProviderError as exc:
        return failed_memo_artifact(
            context.decision,
            status=MemoStatus.GENERATION_FAILED,
            provider=provider.provider_name,
            deployment_id=provider.deployment_id,
            reasoning_effort=provider.reasoning_effort,
            max_output_tokens=provider.max_output_tokens,
            error=str(exc),
        )
    try:
        narrative = parse_and_validate_memo_response(result.output_text, context)
    except MemoValidationError as exc:
        return failed_memo_artifact(
            context.decision,
            status=MemoStatus.VALIDATION_FAILED,
            provider=provider.provider_name,
            deployment_id=provider.deployment_id,
            reasoning_effort=provider.reasoning_effort,
            max_output_tokens=provider.max_output_tokens,
            error=str(exc),
            response_id=result.response_id,
            usage=result.usage,
        )
    return CompanyMemoArtifact(
        memo_generation_status=MemoStatus.GENERATED,
        decision=context.decision,
        provider=provider.provider_name,
        deployment_id=provider.deployment_id,
        reasoning_effort=provider.reasoning_effort,
        max_output_tokens=provider.max_output_tokens,
        memo_contract_version=MEMO_CONTRACT_VERSION,
        prompt_version=PROMPT_VERSION,
        narrative=narrative,
        response_id=result.response_id,
        usage=result.usage,
        error=None,
    )


def failed_memo_artifact(
    decision: DecisionMemoInput,
    *,
    status: MemoStatus,
    provider: str,
    deployment_id: str,
    reasoning_effort: str,
    max_output_tokens: int,
    error: str,
    response_id: str | None = None,
    usage: ProviderUsage | None = None,
) -> CompanyMemoArtifact:
    """Represent an unavailable memo without altering its deterministic decision."""
    if status is MemoStatus.GENERATED:
        raise ValueError("failed_memo_artifact cannot use generated status")
    return CompanyMemoArtifact(
        memo_generation_status=status,
        decision=decision,
        provider=provider,
        deployment_id=deployment_id,
        reasoning_effort=reasoning_effort,
        max_output_tokens=max_output_tokens,
        memo_contract_version=MEMO_CONTRACT_VERSION,
        prompt_version=PROMPT_VERSION,
        narrative=None,
        response_id=response_id,
        usage=usage,
        error=error,
    )


def write_memo_artifacts(artifacts: tuple[CompanyMemoArtifact, ...], path: Path) -> None:
    """Write only sanitized decisions, generated claims, citations, and provider metadata."""
    payload = {
        "memo_contract_version": MEMO_CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "companies": [item.stable_payload() for item in artifacts],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def render_company_memos(artifacts: tuple[CompanyMemoArtifact, ...]) -> str:
    """Render a concise report while keeping deterministic facts visibly authoritative."""
    lines = [
        "# Company Memos",
        "",
        "These memos explain the frozen deterministic Phase 5 decisions. The model does not "
        "calculate or alter scores, valuations, weights, stances, or actions.",
        "",
    ]
    for artifact in artifacts:
        decision = artifact.decision
        lines.extend(
            [
                f"## {decision.company_name}",
                "",
                f"Memo status: **{artifact.memo_generation_status.value}**  ",
                f"Deterministic stance/action: **{decision.underlying_stance.upper()} / "
                f"{decision.final_portfolio_action.upper()}**  ",
                f"Decision date: **{decision.decision_date.isoformat()}**  ",
                f"Decision snapshot: `{decision.decision_snapshot_sha256}`  ",
                f"Working current/target weight: {decision.working_current_weight} / "
                f"{decision.target_weight}",
                "",
            ]
        )
        if artifact.narrative is None:
            lines.extend(
                [
                    f"No validated model narrative was published: {artifact.error}",
                    "",
                    decision.provisional_holdings_warning,
                    "",
                ]
            )
            continue
        narrative = artifact.narrative
        lines.extend(_render_claim("Executive summary", narrative.executive_summary))
        for name, claims in narrative.sections.items():
            heading = name.replace("_", " ").title()
            lines.extend([f"### {heading}", ""])
            for claim in claims:
                citations = ", ".join(f"`{item}`" for item in claim.evidence_ids)
                lines.append(f"- {claim.text} [{citations}]")
            lines.append("")
        lines.extend(
            [
                f"Provider/deployment: `{artifact.provider}` / `{artifact.deployment_id}`  ",
                f"Reasoning/output limit: `{artifact.reasoning_effort}` / "
                f"`{artifact.max_output_tokens}` tokens  ",
                f"Contract/prompt: `{artifact.memo_contract_version}` / "
                f"`{artifact.prompt_version}`",
                "",
            ]
        )
    return "\n".join(lines)


def _render_claim(heading: str, claim: object) -> list[str]:
    from .memo import MemoClaim

    if not isinstance(claim, MemoClaim):
        raise TypeError("Expected a validated MemoClaim")
    citations = ", ".join(f"`{item}`" for item in claim.evidence_ids)
    return [f"### {heading}", "", f"{claim.text} [{citations}]", ""]
