"""Build sanitized company memo artifacts from frozen Phase 4/5 inputs."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from enam_assessment.errors import MemoConfigurationError
from enam_assessment.evidence_io import read_snapshot
from enam_assessment.memo import build_memo_context, read_decision_memo_inputs
from enam_assessment.memo_generation import (
    MemoStatus,
    failed_memo_artifact,
    generate_company_memo,
    render_company_memos,
    write_memo_artifacts,
)
from enam_assessment.memo_provider import AzureOpenAIResponsesProvider, AzureOpenAISettings

ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = ROOT / "decision" / "decision_snapshot.json"
EVIDENCE_PATH = ROOT / "evidence" / "normalized_snapshot.json"
PROMPT_PATH = ROOT / "prompts" / "company_memo_prompt_v1.txt"
OUTPUT_PATH = ROOT / "memos" / "company_memos.json"
REPORT_PATH = ROOT / "docs" / "COMPANY_MEMOS.md"


def main() -> None:
    """Assemble all contexts offline, then make controlled calls only when configured."""
    decisions = read_decision_memo_inputs(DECISION_PATH)
    evidence = read_snapshot(EVIDENCE_PATH)
    contexts = tuple(build_memo_context(item, evidence) for item in decisions)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    try:
        settings = AzureOpenAISettings.from_environment(os.environ)
    except MemoConfigurationError as exc:
        artifacts = tuple(
            failed_memo_artifact(
                context.decision,
                status=MemoStatus.NOT_CONFIGURED,
                provider="azure_openai_responses",
                deployment_id="not_configured",
                reasoning_effort=os.environ.get("AZURE_OPENAI_REASONING_EFFORT", "medium"),
                max_output_tokens=_configured_output_limit(os.environ),
                error=str(exc),
            )
            for context in contexts
        )
    else:
        provider = AzureOpenAIResponsesProvider(settings)
        smoke = generate_company_memo(contexts[0], provider, system_prompt=prompt)
        if smoke.memo_generation_status is MemoStatus.GENERATED:
            artifacts = (smoke,) + tuple(
                generate_company_memo(context, provider, system_prompt=prompt)
                for context in contexts[1:]
            )
        else:
            artifacts = (smoke,) + tuple(
                failed_memo_artifact(
                    context.decision,
                    status=MemoStatus.GENERATION_FAILED,
                    provider=provider.provider_name,
                    deployment_id=provider.deployment_id,
                    reasoning_effort=provider.reasoning_effort,
                    max_output_tokens=provider.max_output_tokens,
                    error=(
                        "Not attempted because the single-company live smoke test did not "
                        "produce a validated memo."
                    ),
                )
                for context in contexts[1:]
            )
    write_memo_artifacts(artifacts, OUTPUT_PATH)
    REPORT_PATH.write_text(render_company_memos(artifacts), encoding="utf-8")
    for artifact in artifacts:
        print(f"{artifact.decision.company_id}={artifact.memo_generation_status.value}")
    print(f"wrote={OUTPUT_PATH.relative_to(ROOT)}")
    print(f"wrote={REPORT_PATH.relative_to(ROOT)}")


def _configured_output_limit(environment: Mapping[str, str]) -> int:
    value = environment.get("AZURE_OPENAI_MAX_OUTPUT_TOKENS", "6000")
    try:
        parsed = int(value)
    except ValueError:
        return 6000
    return parsed if parsed > 0 else 6000


if __name__ == "__main__":
    main()
