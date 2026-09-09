# LLM Memo Architecture

## Purpose and authority boundary

The memo layer is the portfolio-intelligence explanation surface for the frozen Phase 5 decisions.
It helps a portfolio owner understand the current view, evidence, risks, scenario drivers, sizing,
uncertainties, review requirements, and change triggers. It does not calculate or alter a gate,
score, scenario, weight, stance, or action.

The bounded flow is:

`Phase 5 company decision + only its cited Phase 4 evidence -> memo context -> Azure OpenAI
Responses API -> structured response -> local identity/schema/citation validation -> sanitized memo`

There is no vector search, retrieval agent, tool-using model, hidden repair loop, or fallback memo.
The deterministic decision remains available when the provider is unavailable or a response fails
validation.

## Versioned contracts

- Decision contract: `phase5-company-decision-v1`
- Memo contract: `company-memo-v1`
- Prompt: `company-memo-prompt-v1`

The decision contract exposes only these fields:

- company ID/name, decision date, evidence-manifest hash, decision-snapshot hash, and engine/config
  versions;
- working shares/cost basis, dated current price, working current weight, target weight, and the
  provisional-holdings warning;
- immutable underlying stance, final action, human-review status/reasons, hard gates, six principle
  scores, weighted total, and bear/base/bull scenario results;
- confidence, missing-data flags, common drivers, change triggers, historical benchmark context,
  benchmark availability, cited evidence IDs and their availability dates;
- the explicit limitations of the relative operating-value scenarios.

The model receives that contract plus a stable, deduplicated list containing exactly the evidence
IDs cited by the company decision. Each evidence item contains a concise normalized fact or claim,
company/instrument ID, evidence type, availability date, source ID/title/type, source locator, and
conflict IDs. Evidence is rejected if its ID is unknown, it became available after the decision
date, or it belongs to another company outside declared portfolio/benchmark context.

The model never receives workbook rows, passwords, credentials, protected PDFs, complete source
documents, arbitrary repository files, raw download caches, or uncited evidence. Evidence text is
explicitly treated as untrusted data rather than instructions.

## Response and citation validation

The Responses request uses strict JSON Schema. Narrative is returned as claim objects containing
`text`, one or more `evidence_ids`, and `category`. Local validation requires:

- exact company identity, decision date, decision-snapshot hash, contract version, prompt version,
  stance, and final action;
- every required memo section and no unknown response fields;
- at least one allow-listed citation on every material claim;
- evidence already validated as no later than the decision date and within company/context scope.

Citation presence proves only that a claim points to evidence included in the context. This
prototype does not claim semantic entailment or truth verification. Invalid responses receive
`validation_failed` and are not published as valid memos. Provider failures receive
`generation_failed`; absent runtime configuration receives `not_configured`.

## Azure OpenAI operation

The adapter uses the official `openai` Python SDK against Azure's v1 Responses endpoint. Required
runtime variables are:

- `AZURE_OPENAI_API_KEY`;
- `AZURE_OPENAI_DEPLOYMENT`;
- either `AZURE_OPENAI_BASE_URL` or `AZURE_OPENAI_ENDPOINT`.

The controlled Phase 7 run additionally sets:

- `AZURE_OPENAI_REASONING_EFFORT=medium`;
- `AZURE_OPENAI_MAX_OUTPUT_TOKENS=6000`.

The adapter sends these as `reasoning={"effort": "medium"}` and `max_output_tokens=6000` on the
Responses request. The effective non-secret settings are retained in sanitized memo metadata.

Optional `ENAM_MEMO_PROMPT_VERSION` and `ENAM_MEMO_CONTRACT_VERSION` values must match the supported
versions above. Values are never printed or persisted. After offline verification, run:

```powershell
py scripts/build_company_memos.py
```

When configured, the script makes one company call first and validates it. It calls the remaining
companies only after that smoke test succeeds. Returned token counts are retained when available;
cost is not inferred because Azure deployment pricing and account credits are not part of the
repository evidence.

As of 2026-09-10, the configured endpoint was found to already end in `/openai`. Earlier code
blindly appended `/openai/v1/`, producing the invalid `/openai/openai/v1/` route and the observed
`NotFoundError`. Endpoint normalization now accepts the Azure resource root, `/openai`, or the
complete `/openai/v1/` path and produces the documented SDK base URL exactly once.

The next controlled Amber request reached deployment `gpt-5.6-terra` and Azure accepted the
Responses request, reasoning parameter, output limit, and strict structured-output schema. Local
validation rejected the returned narrative because it supplied decision-contract version
`phase5-company-decision-v1` in the `memo_contract_version` field instead of `company-memo-v1`.
Amber is recorded as `validation_failed`; the remaining companies are `generation_failed` because
they were deliberately not attempted after the failed smoke gate. Azure reported 6,104 input,
3,222 output, and 9,326 total tokens. No charge is confirmed. Immutable response fields are now
constrained to their exact values in the request schema and checked again locally. The sanitized
Amber fixture at
`tests/fixtures/validated_memo_amber.json` is the representative memo validated through the fake
provider during offline Component tests.

Implementation references:

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
  documents strict JSON Schema under the Responses API `text.format` field.
- [Microsoft Azure OpenAI Responses API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
  documents the Azure v1 base URL, deployment name in `model`, and official OpenAI SDK client.

## Phase 5 consistency checkpoint

The configured working shares and cost bases exactly reconcile to the Phase 3 provisional open-lot
table for all four companies. DBL's gate now calculates `7244 / 1766 =
4.101925254813137033975084938...x` using `Decimal`, from
`fundamental-dbl-consolidated-net-debt-fy26` and `fundamental-c02d7f1564a6c6e4`. This exceeds the
configurable strict `4.0x` prototype threshold, so the gate remains `FAIL` with a `SELL`
consequence. Rebuilding retained decision hash
`014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`; recommendations did not
change.
