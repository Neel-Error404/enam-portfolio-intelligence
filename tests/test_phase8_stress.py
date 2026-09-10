from pathlib import Path

from enam_assessment.intelligence import (
    DEFAULT_QUESTION_INPUT_TOKENS,
    QuestionScope,
    answer_cache_key,
    answer_response_json_schema,
    build_question_context,
    estimated_request_tokens,
)
from enam_assessment.portfolio_ui import load_dashboard_data

ROOT = Path(__file__).resolve().parents[1]


def test_repeated_context_builds_remain_bounded_and_order_stable() -> None:
    data = load_dashboard_data(ROOT)
    prompt = (ROOT / "prompts" / "portfolio_intelligence_prompt_v1.txt").read_text(encoding="utf-8")
    keys: set[str] = set()
    for index in range(50):
        context = build_question_context(
            data,
            scope=QuestionScope.COMPARISON,
            question=f"Compare evidence, risk, and valuation. Review number {index}.",
            company_ids=("welspun", "zee"),
        )
        estimate = estimated_request_tokens(
            context,
            system_prompt=prompt,
            response_schema=answer_response_json_schema(context),
        )
        assert estimate <= DEFAULT_QUESTION_INPUT_TOKENS
        assert context.included_evidence_ids == tuple(sorted(context.included_evidence_ids))
        keys.add(answer_cache_key(context))

    assert len(keys) == 50
