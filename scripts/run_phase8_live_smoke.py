"""Run the bounded three-rung Azure Responses smoke ladder for Phase 8A."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import APIError, OpenAI

from enam_assessment.intelligence import (
    AnswerStatus,
    QuestionScope,
    build_interactive_provider,
    build_question_context,
    generate_grounded_answer,
)
from enam_assessment.memo_provider import (
    AzureOpenAISettings,
    sanitize_provider_error,
)
from enam_assessment.portfolio_ui import load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT = "gpt-5.6-terra"
EXPECTED_SNAPSHOT = "014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89"
OUTPUT_PATH = ROOT / "artifacts" / "phase8_live_smoke.json"


def _usage(response: Any) -> dict[str, int | None] | None:
    if response.usage is None:
        return None
    details = getattr(response.usage, "output_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", None)
    return {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "reasoning_tokens": reasoning if isinstance(reasoning, int) else None,
        "total_tokens": response.usage.total_tokens,
    }


def _write(record: dict[str, object]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _failure(
    record: dict[str, object],
    *,
    rung: str,
    exc: Exception,
    settings: AzureOpenAISettings,
) -> None:
    error = sanitize_provider_error(exc, settings) if isinstance(exc, APIError) else None
    record["status"] = "failed"
    record["failed_rung"] = rung
    record["inference_began"] = False
    record["usage_confirmed"] = False
    record["error"] = (
        error.stable_payload()
        if error is not None
        else {
            "status": None,
            "request_id": None,
            "code": None,
            "parameter": None,
            "type": type(exc).__name__,
            "message": str(exc)[:800],
        }
    )
    _write(record)
    raise SystemExit(1)


def _audit_schema(node: object, path: str = "$") -> None:
    if not isinstance(node, dict):
        raise ValueError(f"{path} must be a schema object.")
    enum = node.get("enum")
    if enum is not None and (not isinstance(enum, list) or not enum):
        raise ValueError(f"{path}.enum must be a non-empty array.")
    if node.get("type") == "object":
        properties = node.get("properties")
        required = node.get("required")
        if node.get("additionalProperties") is not False:
            raise ValueError(f"{path} must set additionalProperties=false.")
        if not isinstance(properties, dict) or set(required or []) != set(properties):
            raise ValueError(f"{path}.required must contain every property exactly once.")
        for name, child in properties.items():
            _audit_schema(child, f"{path}.properties.{name}")
    if node.get("type") == "array":
        if "items" not in node:
            raise ValueError(f"{path} must define items.")
        _audit_schema(node["items"], f"{path}.items")


def main() -> None:
    configured = dict(os.environ)
    configured["AZURE_OPENAI_DEPLOYMENT"] = DEPLOYMENT
    configured["AZURE_OPENAI_REASONING_EFFORT"] = "low"
    configured["AZURE_OPENAI_MAX_OUTPUT_TOKENS"] = "2200"
    settings = AzureOpenAISettings.from_environment(configured)
    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    retry_amber_only = "--amber-only-retry" in sys.argv[1:]
    if retry_amber_only:
        if not OUTPUT_PATH.exists():
            raise RuntimeError("Amber-only retry requires the prior ladder artifact.")
        loaded = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or loaded.get("calls_made") != 3:
            raise RuntimeError("Amber-only retry requires exactly three recorded prior calls.")
        record = loaded
        rungs = record.get("rungs")
        if not isinstance(rungs, list) or [item.get("status") for item in rungs] != [
            "passed",
            "passed",
        ]:
            raise RuntimeError("Amber-only retry requires both earlier rungs to have passed.")
        prior_amber = record.get("amber")
        if prior_amber is not None:
            record["prior_failed_amber_attempt"] = prior_amber
        record["status"] = "running"
        record["corrective_retry"] = "removed non-scalar enum from company_ids array schema"
    else:
        record = {
            "started_at": datetime.now(UTC).isoformat(),
            "status": "running",
            "provider": "azure_openai_responses",
            "deployment": DEPLOYMENT,
            "reasoning_effort": "low",
            "calls_made": 0,
            "rungs": [],
        }

        try:
            plain = client.responses.create(
                model=DEPLOYMENT,
                input="Reply only with OK",
                reasoning={"effort": "low"},
                max_output_tokens=256,
            )
        except Exception as exc:
            record["calls_made"] = 1
            _failure(record, rung="connectivity", exc=exc, settings=settings)
        record["calls_made"] = 1
        rungs = record["rungs"]
        assert isinstance(rungs, list)
        rungs.append(
            {
                "rung": "connectivity",
                "status": "passed",
                "response_id": plain.id,
                "output_text": plain.output_text,
                "usage": _usage(plain),
            }
        )
        _write(record)

        minimal_schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["ok"]}},
            "required": ["status"],
            "additionalProperties": False,
        }
        try:
            structured = client.responses.create(
                model=DEPLOYMENT,
                input='Return the required JSON object with status "ok".',
                reasoning={"effort": "low"},
                max_output_tokens=256,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "phase8_minimal_smoke",
                        "strict": True,
                        "schema": minimal_schema,
                    }
                },
            )
        except Exception as exc:
            record["calls_made"] = 2
            _failure(record, rung="minimal_structured_output", exc=exc, settings=settings)
        record["calls_made"] = 2
        try:
            minimal_output = json.loads(structured.output_text)
        except json.JSONDecodeError as exc:
            _failure(record, rung="minimal_structured_output", exc=exc, settings=settings)
        if minimal_output != {"status": "ok"}:
            _failure(
                record,
                rung="minimal_structured_output",
                exc=ValueError("Minimal structured response did not equal the required object."),
                settings=settings,
            )
        rungs.append(
            {
                "rung": "minimal_structured_output",
                "status": "passed",
                "response_id": structured.id,
                "output": minimal_output,
                "usage": _usage(structured),
            }
        )
        _write(record)

    data = load_dashboard_data(ROOT)
    context = build_question_context(
        data,
        scope=QuestionScope.COMPANY,
        question=(
            "Why can Amber's portfolio action require review despite an attractive base-case "
            "three-year CAGR?"
        ),
        company_ids=("amber",),
    )
    if context.decision_snapshot_sha256 != EXPECTED_SNAPSHOT:
        raise RuntimeError("Decision snapshot hash changed before the Amber smoke request.")
    from enam_assessment.intelligence import answer_response_json_schema

    response_schema = answer_response_json_schema(context)
    _audit_schema(response_schema)
    properties = response_schema["properties"]
    assert isinstance(properties, dict)
    company_schema = properties["company_ids"]
    assert isinstance(company_schema, dict)
    items_schema = company_schema.get("items")
    if (
        not isinstance(items_schema, dict)
        or items_schema.get("enum") != ["amber"]
        or company_schema.get("minItems") != 1
        or company_schema.get("maxItems") != 1
    ):
        raise RuntimeError("Amber company_ids is not constrained to the exact requested value.")
    expected_evidence = set(context.included_evidence_ids)
    if len(expected_evidence) != 6:
        raise RuntimeError("Amber smoke context must contain exactly six evidence IDs.")
    record["schema_audit"] = {
        "status": "passed",
        "root_object": response_schema.get("type") == "object",
        "strict_objects": True,
        "all_properties_required": True,
        "all_arrays_define_items": True,
        "amber_company_ids_exact": True,
        "allowed_evidence_ids": sorted(expected_evidence),
    }
    provider = build_interactive_provider(configured)
    artifact = generate_grounded_answer(
        context,
        provider,
        system_prompt=(ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(
            encoding="utf-8"
        ),
    )
    record["calls_made"] = 4 if retry_amber_only else 3
    record["amber"] = artifact.stable_payload()
    record["status"] = "passed" if artifact.status is AnswerStatus.GENERATED else "failed"
    record["failed_rung"] = (
        None if artifact.status is AnswerStatus.GENERATED else "amber_portfolio_answer"
    )
    record["completed_at"] = datetime.now(UTC).isoformat()
    _write(record)
    usage = artifact.usage
    print(f"status={artifact.status.value}")
    print(f"provider={artifact.provider}")
    print(f"deployment={artifact.deployment_id}")
    print(f"reasoning={artifact.reasoning_effort}")
    print(f"context_hash={artifact.context.context_hash}")
    print(f"included_evidence={len(artifact.context.included_evidence_ids)}")
    print(f"excluded_evidence={len(artifact.context.excluded_evidence_ids)}")
    print(f"serialized_context_characters={artifact.context.serialized_characters}")
    if usage is not None:
        print(f"input_tokens={usage.input_tokens}")
        print(f"output_tokens={usage.output_tokens}")
        print(f"total_tokens={usage.total_tokens}")
    if artifact.error:
        print(f"error={artifact.error}")
    print(f"artifact={OUTPUT_PATH}")
    if artifact.status is not AnswerStatus.GENERATED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
