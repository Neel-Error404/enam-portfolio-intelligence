# Phase 8A Verification

Verified on 10 September 2026 in the project-local Python 3.12 environment.

## Frozen baseline

- Pre-Phase-8 local commit: `e1c6ffa` (`Establish portfolio intelligence baseline`).
- Decision snapshot before work:
  `014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`.
- Decision replay after work produced the same hash. No score, gate, scenario, target weight, stance,
  or final action changed.

## Automated verification

- Foundation: 76 passed, 2 skipped. The skips are existing Windows symlink-permission cases.
- Component and prior-phase regressions: 49 passed.
- Phase 8A Integration: 1 passed.
- Phase 8A Workflow: 2 passed.
- Targeted context stress: 1 passed.
- Ruff formatting and linting: passed.
- Strict mypy: passed for `src` and `app.py`.
- `pip check`: no broken requirements.

An earlier combined Foundation run produced two setup errors because pytest could not scan
`%LOCALAPPDATA%\Temp\pytest-of-neela` (`WinError 5`). Rerunning the same level with an ignored,
project-local `--basetemp` produced 16 passes for that subset. This was an environment-permission
failure, not an application defect.

## Live Azure smoke ladder

The controlled ladder used:

- provider: `azure_openai_responses`;
- deployment: `gpt-5.6-terra`;
- reasoning effort: `low`;
- maximum output: 2,200 tokens;
- contract: `portfolio-answer-v1`;
- prompt: `portfolio-intelligence-prompt-v1`;
- plain connectivity: passed, response ID recorded in the ignored smoke artifact, output `OK`,
  10 input / 5 output / 0 reasoning / 15 total tokens;
- minimal strict structured output: passed with `{"status":"ok"}`, response ID recorded,
  47 input / 17 output / 0 reasoning / 64 total tokens;
- first Amber schema submission: rejected before inference with HTTP 400,
  `invalid_json_schema` on `text.format.schema`; request ID recorded and no usage confirmed;
- one authorized corrective Amber retry: generated and locally validated, response ID recorded,
  1,972 input / 1,141 output / 106 reasoning / 3,113 total tokens.

The exact schema compatibility defect was the non-scalar exact-value enum on the `company_ids`
array. Azure accepted the same contract after that array-valued enum was removed and the Amber
constraint was retained with `items.enum = ["amber"]` and `minItems = maxItems = 1`. The provider
adapter now preserves sanitized HTTP status, request ID, error code, parameter, error type, and
provider message. It does not record the API key or Azure endpoint.

The successful Amber request used six evidence records, excluded none, and sent a 2,830-character
bounded context. Its 1,972 actual input tokens are 67.7% below the original 6,104-input-token
baseline; its 1,141 output tokens are 64.6% below the original 3,222-output-token baseline.
Confirmed usage across the three successful ladder calls was 2,029 input, 1,163 output, and 3,192
total tokens. The rejected pre-inference schema request reported no usage, so no charge is confirmed
for it.

The accepted answer preserved Amber's `sell` underlying stance and `review_required` final action,
the decision/context hashes, scenario results, weights, and human-review state. All citations were
inside the six-record allow-list. Manual review confirmed that each claim was supported by the
cited frozen decision, price, fundamental, estimate, or guidance record. The answer directly
explained that a 27.435% base-case CAGR does not override bear-case downside, missing evidence, or
the material provisional-holdings constraint.

## Local workflow and visual review

- Streamlit health endpoint returned `ok` at `http://localhost:8501`.
- Automated workflow exercised holdings confirmation, cash inclusion, deterministic scenario
  recalculation, supervised disposition, audit recording, and reset to baseline.
- All four views and all four company selections loaded through Streamlit's application test API.
- The no-configuration path kept deterministic analysis visible and showed an explicit unavailable
  message without a network call.
- Generated, generation-failed, and validation-failed answer states were rendered from validated
  test artifacts; rejected prose remained hidden.
- Desktop and narrow screenshots were captured under the ignored `artifacts/phase8_dogfood/`
  directory. The institutional visual hierarchy, visible status labels, and responsive stacking were
  inspected. The Streamlit toolbar itself remains outside application styling.

## Pre-deployment dogfood closure

The strict response schema was audited recursively for company, portfolio, two-company comparison,
historical-behaviour, and scenario-delta contexts. The context builder now separates companies used
to select portfolio/behaviour evidence from the response identity. When a scope has companies,
`company_ids.items.enum` contains those non-empty IDs and the array has an exact item count. When a
scope intentionally has no company IDs, `company_ids` uses string items with `minItems = 0` and
`maxItems = 0`, without an empty enum. Every array has `items`; every enum is non-empty; and every
object is closed and requires all declared properties. Local validation still enforces the exact
identity tuple.

Three new Azure calls were made through the local application, using `gpt-5.6-terra`, low reasoning,
the bounded context builder, `portfolio-intelligence-prompt-v1`, and `portfolio-answer-v1`:

1. Historical behaviour reached inference and returned structured output, but local validation
   rejected it at 451 words against the 450-word maximum. The UI correctly withheld the answer.
   The browser harness closed before downloading that failed-response audit, so its response ID and
   provider usage were not retained. The prompt was narrowed to an explicit 250-400-word target and
   400-word maximum, and the schema tests were rerun. The call was not retried because the authorized
   three-call limit had to cover the remaining distinct scopes.
2. Welspun-versus-Zee comparison passed schema, identity, immutable-hash, citation allow-list, and
   manual evidence review. Response ID
   `resp_0644487b3be1f031006aa249539d088194991f9add40a2e81a`; usage 2,407 input,
   1,337 output, 242 reasoning, and 3,744 total tokens. The 4,297-character context included seven
   evidence IDs and excluded 21. The answer correctly distinguished Welspun's stronger expected
   return from Zee's stronger balance-sheet score, preserved both frozen actions, and stated the
   company-attribution limits of the compact evidence records.
3. Amber scenario delta passed schema, identity, immutable-hash, citation allow-list, and manual
   evidence review. Response ID
   `resp_0a9bc8402f5a415e006aa24a40f5248196b1b00b1dada3a8ef`; usage 2,151 input,
   1,461 output, 88 reasoning, and 3,612 total tokens. The 3,171-character context included seven
   evidence IDs and excluded none. It accurately explained the deterministic change from 19% to 20%
   annual revenue growth: target value increased from INR 15,124.04 to INR 15,508.53 and price CAGR
   from 27.435% to 28.506%, without changing Amber's `sell` stance or `review_required` action.

Known confirmed usage for the two accepted calls was 4,558 input, 2,798 output, 330 reasoning, and
7,356 total tokens. The historical-behaviour call's usage is unknown rather than estimated.

The browser journey verified a user-adjusted Amber share count and INR 1 crore cash, responsive
active weights and concentration, company evidence, deterministic scenario recalculation, cited
evidence expansion, a `deferred` owner disposition, sanitized audit download, and reset to the
calculated provisional baseline. The session audit retained the question, context, evidence IDs,
usage, scenario override, validation result, and disposition while leaving the engine decision
unchanged. Automated coverage separately verified that a repeated normalized question/context uses
the session cache (`provider.calls == 1`) and that missing Azure configuration leaves the
deterministic application usable with an explicit unavailable state.

Desktop and 390-pixel-wide layouts were inspected. `REVIEW_REQUIRED` wraps without truncation. A
reproduced mobile table problem was corrected by showing compact principle and hard-gate summaries
and moving full quality, rule, consequence, and explanation text into wrapping expanders. Final
screenshots and audit downloads remain under ignored `artifacts/phase8_dogfood/`.

The final verification ladder completed with 76 Foundation passes and two expected Windows
symlink-permission skips, 49 Component and prior-phase regression passes, one Integration pass, two
Workflow passes, and one targeted Stress pass. A final combined run reported **129 passed and 2
skipped**. Ruff formatting and linting, strict mypy over `src` and `app.py`, `pip check`, the local
Streamlit health check, and deterministic replay all passed. Replay retained snapshot hash
`014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`.

## Pre-deployment verdict

**NO-GO for Docker.** The comparison and scenario-delta paths are live-validated, but the historical
behaviour response was not accepted or manually claim-checked. Phase 8A therefore does not meet its
declared completion standard. No fallback model, blind retry, or uncited substitute narrative was
used. The next safe action is a separately authorized, single behaviour-only Azure call through the
UI using the tightened prompt, followed by audit capture, citation support review, and a final hash
check. No Docker work should start before that gate passes.

## Phase 8B shared conversation and supplied-data defaults

Phase 8B connected the four Streamlit workspaces to one sidebar conversation and made the supplied
workbook-derived shares and frozen prices active on first load. Cash was not supplied, so the default
is explicitly recorded as an assumed zero rather than a verified balance. Optional changes preserve
field-level supplied/assumed or user-entered provenance and remain session-only. Active shares, cash,
weights, concentration, selected artifacts, scenario deltas, bounded recent turns, and prompt and
contract versions now enter the response context and cache hash. Frozen scores, gates, scenarios,
targets, stances, actions, and the source workbook remain unchanged.

Compact evidence now identifies its company or instrument, kind/category, availability date,
reporting period or relevant date, unit, and evidence ID. Selected artifacts remain visible with
their originating page/company across navigation. Prior accepted answers retain their original
context and citations and are marked when they predate a relevant portfolio-state change. Provider
metadata is written immediately to the ignored Phase 8B JSONL audit, including when subsequent local
validation fails.

### Phase 8B live evidence and retry boundary

Two Azure inferences were made through the Portfolio Cockpit using `gpt-5.6-terra`, low reasoning,
`portfolio-intelligence-prompt-v1`, and `portfolio-answer-v1`. Both asked: "Which positions drive
concentration in the supplied-data default portfolio, and why do they need attention?"

1. `resp_08e68b001e8bc29d006aa26937fcfc81938c294f3777706ec1`: 2,213 input,
   942 output, 0 reasoning, and 3,155 total tokens.
2. `resp_0005d323838f48d6006aa269d525908196be30700f92a297ae`: 2,136 input,
   1,048 output, 66 reasoning, and 3,184 total tokens.

Both responses passed the strict schema, identity, immutable-hash, and citation allow-list checks,
but failed the mandatory manual claim-support check. The context contained active weights and an
allocation artifact, while the answers also attributed DBL gate statuses and consequences to that
artifact. The relevant frozen gate evidence was not present in the cited record. The second call was
the one permitted evidence-based corrective retry, but Streamlit had not reloaded the corrected
source and therefore submitted the same stale evidence shape. This was an application-session
reload error, not an Azure transport or schema error. No third call was made because the task allowed
only one corrective retry after a failed live response.

The corrected offline context now protects `decision:portfolio-summary`, which includes each
company's stance, final action, target weight, and non-pass gate code/status/consequence; it derives
HHI and top-two/top-three concentration from `session:active-portfolio`; and it no longer emits the
ambiguous `decision:portfolio-concentration` record. The exact corrected context passed the focused
Foundation and Component checks but has not been submitted live.

The earlier historical-behaviour gate also remains open: the only live behaviour response reached
inference but failed the word-count validator, and no accepted, manually supported replacement was
generated in Phase 8B before the live retry sequence stopped.

### Phase 8B browser dogfood

A fresh Streamlit session verified that the application is useful immediately with supplied-data
defaults. The browser journey exercised a session cash change and holding adjustment, responsive
active weights/concentration, an allocation artifact retained after navigation, the Amber company
workspace, a deterministic revenue-growth scenario change from 19.0% to 19.5%, and a supervised
`deferred` disposition. The scenario target moved from INR 15,124.04 to INR 15,315.48 and CAGR from
27.4% to 28.0% without changing the frozen decision. Reset and missing-provider behavior remain
covered by workflow and Component tests.

At 1,440 pixels, the five-column company metrics reproduced truncation of `REVIEW_REQUIRED`. The
metric value CSS was narrowed to permit wrapping and remove ellipsis; the final accessibility tree
exposed the complete label. A 390-pixel mobile pass confirmed single-column stacking and readable
warning content. Browser screenshot capture became unreliable after Streamlit hot reload, so the
final post-fix proof is the accessibility snapshot plus automated UI assertions rather than a new
persisted screenshot set.

### Phase 8B verification and verdict

- Foundation: 78 passed, 2 expected Windows symlink-permission skips.
- Component and prior-phase regression: 52 passed.
- Integration: 1 passed.
- Workflow: 2 passed.
- Targeted stress: 1 passed.
- Ruff format check and lint: passed.
- Strict mypy: passed across 19 source files.
- `pip check`: no broken requirements.
- Deterministic replay: unchanged at
  `014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`.

**NO-GO for Docker and deployment.** The offline Phase 8B product journey is complete and green, but
the required accepted historical-behaviour answer and a live manual support check of the corrected
shared-context path remain unproven. The next safe action is a separately authorized clean-server
live acceptance run: first submit the historical-behaviour question, then—only if it passes—submit
one corrected active-portfolio/artifact question, retain both audits, review every cited claim, and
rerun the focused tests and snapshot replay. Docker must wait for those two live gates.

## Phase 8C final Portfolio Intelligence UX closure

Phase 8C replaced the low sidebar conversation with one shared native Streamlit dialog. Every page
now exposes `Ask AI about this page` in its first viewport, while the sidebar retains only navigation,
the active-holdings basis, and a compact launcher. Meaningful analytical sections consistently use
`Ask AI about this`; the action attaches the section's existing structured data, shows its page,
company or portfolio scope as a removable chip, and opens the same conversation without calling the
provider. Page, company, section, active holdings, cash, scenario, bounded conversation history,
prompt version, and contract version remain part of the context identity.

The pages were reordered around the investor's decision sequence. The Portfolio Cockpit leads from
represented exposure and concentration to allocation, priorities, optional holding adjustments, and
comparison. Company Intelligence places hard gates before principles and valuation, then evidence,
change conditions, Scenario Lab, disposition, and collapsed legacy memo state. Investor Behaviour
establishes scope and limitations before performance and findings. Assumptions & Audit explains the
deterministic-versus-LLM boundary before hashes and runtime identifiers. Responsive metric wrapping
keeps the complete `REVIEW_REQUIRED` label visible.

### Phase 8C live evidence

Streamlit was completely restarted before the live sequence. Four Azure requests were made through
the local application using `gpt-5.6-terra`, low reasoning, `portfolio-intelligence-prompt-v1`, and
`portfolio-answer-v1`. This consumed the four remaining authorized Phase 8C requests and brought the
cumulative Phase 8B/8C count to six. Navigation, dialog open/close, context selection, and ordinary
rerenders generated no provider request.

1. **Portfolio allocation and concentration — accepted.** Response
   `resp_0f8b26462c8b075c006aa27d8872c88193a21765f4bffca4a3`, context
   `f8a884330d61105bb75b64b92a734d7cc69cc8815cfc432d902db05bc74f3437`;
   2,129 input, 1,128 output, 59 reasoning, and 3,257 total tokens. The answer cited the
   active-portfolio, concentration artifact, portfolio decision summary, and one DBL governance
   record. Manual review found the weights, frozen actions and targets, gate summary, and provisional
   denominator limitation supported by those records.
2. **Historical behaviour — rejected after local validation.** Response
   `resp_0f85bcb6ce5b81f6006aa282723448819486744755401a5801`, context
   `c03158f23140b41b7b7d083535b9183b1b1a15bcf76b1da7e444a61aefaa7e22`;
   2,139 input, 946 output, 0 reasoning, and 3,085 total tokens. Its wording blurred supplied
   workbook defaults with user-entered values. The response remains in the append-only audit with a
   failed manual-support verdict. The review form was corrected so no optimistic verdict is selected
   by default.
3. **Historical behaviour — accepted corrective answer.** Response
   `resp_0482eec1f58d9e15006aa2839f30848194bfa360e3e55d17aa`, context
   `457faa29164127bedd9feda017968d15fdefbe30822e7ccdf52b9139b983fa43`;
   2,118 input, 1,000 output, 91 reasoning, and 3,118 total tokens. It used the compact behaviour
   findings, portfolio decision summary, active-portfolio record, and one historical calculation.
   Manual review found the sizing, selling-asymmetry, concentration, decision-context, and limitation
   claims supported, without diagnosing intent, skill, or a disposition effect.
4. **DBL hard-gate follow-up after an active holding and cash change — rejected after local
   validation.** Response `resp_05172f02a333ddd0006aa28bf526688194a203cfe00e3f24bc`, context
   `f3c0cfad136e9ca3368cea35d12c885898233af9e6df9aa8f5f4dc109cd8dfe4`;
   2,112 input, 980 output, 81 reasoning, and 3,092 total tokens. The active overlay correctly showed
   Amber at 40,000 shares, entered cash of INR 5,000,000, and DBL at 46.3365% of the represented
   denominator. The answer preserved the frozen stance, action, target, score, and review state, but
   incorrectly said the consolidated net-debt threshold could not be assessed. The frozen gate had
   already calculated 4.10x FY26 EBITDA against the configurable 4.0x sell threshold. Manual review
   therefore failed the answer.

Phase 8C live usage was 8,498 input, 4,054 output, 231 reasoning, and 12,552 total tokens. The two
accepted answers account for 4,247 input, 2,128 output, 150 reasoning, and 6,375 total tokens. These
are provider usage units, not a confirmed currency charge.

The smallest evidence-backed correction after the DBL rejection was made offline: the compact
failing-gate artifact now includes the gate's deterministic calculation while passing gates remain a
compact code list. The full request estimator also counts bounded conversational history correctly,
and the model payload now uses the bounded history representation rather than its larger audit form.
The exact active-DBL follow-up remains within the 2,500-token request budget in Foundation tests.
There was no fifth live call during the original Phase 8C authorization, so the correction was not
live-verified at that checkpoint.

### Separately authorized final DBL checkpoint

A later, separately authorized single-call checkpoint first strengthened the hard-gate artifact and
repeated the full offline preflight. The selected artifact now carries a structured calculation with
consolidated net debt of INR 7,244 crore, FY26 EBITDA of INR 1,766 crore, their approximately 4.10x
ratio, the configured 4.0x sell threshold, and the two exact source evidence IDs. Selected artifacts
can mark source records as required; those records survive request-budget pruning, while less relevant
evidence or the oldest conversation content is removed first. The artifact also carries the citable
frozen stance, final action, target, principle score, review state, and named missing information.

The exact fresh-session preflight passed at an estimated 2,347 of 2,500 input tokens. Its context hash
was `685f1779b067a51796d9fcc5bc20889a77ef1cc009ac5897f3da59602791d75d` and its allow-list contained:

- `artifact:dbl-hard-gates`;
- `decision:dbl`;
- `fundamental-c02d7f1564a6c6e4`;
- `fundamental-dbl-consolidated-net-debt-fy26`;
- `session:active-portfolio`.

After confirming no old listener was running, Streamlit was started as a new process and a new
isolated browser session selected Dilip Buildcon and attached the Hard Gates section. Exactly one
Azure request was submitted. Response
`resp_0cd96d1d77f7b105006aa29d3bf3bc8190aabf01f938ad418c` used 2,224 input,
1,008 output, 30 reasoning, and 3,232 total tokens. The response passed schema, identity, immutable
snapshot, and citation allow-list validation.

Manual sentence-by-sentence review passed. The answer correctly stated that INR 7,244 crore divided
by INR 1,766 crore is approximately 4.10x, above the 4.0x sell threshold. It preserved DBL's frozen
`sell` stance, `review_required` action, zero target, 2.675 principle score, and required human review.
It separately described DBL's 41.9703% active-session weight as a supplied-data session calculation,
not a verified holding or a revision to the frozen decision. All material claims cited one or more of
the five included records. The explicit `passed` verdict and review note are retained in the ignored
sanitized JSONL audit.

### Phase 8C responsive and interaction verification

Chrome DevTools was used against the fully restarted local Streamlit process. At 1,440 x 1,000,
1,366 x 768, and 390 x 844, all four page titles and page-level AI actions were visible without
scrolling. The 1,366-pixel Company Intelligence view showed the complete `REVIEW_REQUIRED` state
without collision. At 390 pixels, the status strip, page identity, and AI action remained in the
first viewport; Company Intelligence metrics stacked; and the native dialog exposed the selected
context chip, remove and clear controls, question box, and explicit submit button. The four page
reading orders were also checked through the accessibility tree. DevTools returned the screenshots
to the verification session, but its file-writer rejected the project path as outside its configured
workspace root, so no screenshot file was added to the repository.

### Phase 8C verification and verdict

- Foundation: 82 passed, with 2 expected Windows symlink-permission skips.
- Component and prior-phase regression: 60 passed.
- Integration: 1 passed.
- Workflow: 2 passed.
- Targeted stress: 1 passed.
- Final whole suite: 146 passed, with the same 2 expected skips.
- Ruff format initially found three edited files needing mechanical formatting; after formatting,
  format check and lint passed.
- Strict mypy: passed across 19 source files.
- `pip check`: no broken requirements.
- Deterministic replay: unchanged before and after at
  `014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`.

The ordered tests initially encountered a Windows permission error in pytest's global temporary
directory. This was an environment ACL issue, not an application failure. The same level passed with
an ignored project-local pytest base directory, and all later levels used that explicit directory.

The separately authorized post-live checks passed: 17 focused intelligence Foundation tests and 25
focused intelligence Component/UI tests. Deterministic replay again produced
`014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89` and did not alter the generated
decision artifacts.

**GO for the Phase 8 application layer.** The final DBL answer closed the remaining live
claim-to-evidence gate without changing the deterministic decision, prompt, response contract,
deployment, or token limits. This is an application-verification verdict only; Docker and deployment
remain separate, explicitly deferred work.

## Phase 8D claim-level citation usability

Phase 8D changed only local provenance presentation. It did not call Azure, modify a generated
answer, change the citation allow-list or context hash, or touch the deterministic engine, prompt,
response contract, provider configuration, and token limits. The successful Phase 8C DBL answer and
its authentic audit history remain intact.

Every rendered factual claim now has a `Sources for this claim` control immediately below it. One
interaction reveals only that claim's cited records. Each source card leads with a readable label
such as `Frozen DBL decision`, `Current session portfolio calculation`, `Attached DBL hard-gate
analysis`, or `FY26 consolidated net debt — ₹7,244 crore`. The raw evidence ID remains visible as a
secondary audit field.

The opened card shows the evidence record, company or portfolio identity, provenance class,
evidence category, reporting period or observation date, unit, availability date, source title and
type, locator, and recorded conflicts. Derived structured records also show a deterministic summary
before their complete wrapped sanitized payload. The source metadata available to this application
does not include a verified public URL, so the UI does not manufacture an `Open original source`
link; it shows the in-app record and locator instead. The combined `Open cited evidence` appendix
remains available but is no longer the primary citation journey.

### Phase 8D verification

- Focused citation Foundation tests: 18 passed.
- All Foundation tests: 45 passed.
- Focused Streamlit UI tests: 21 passed.
- Component/UI tests: 26 passed.
- Phase 8A integration: 1 passed.
- Phase 8A workflow: 2 passed.
- Targeted stress: 1 passed.
- Complete suite: 148 passed, with 2 expected Windows symlink-permission skips.
- Ruff format check and lint: passed.
- Strict mypy: passed across 19 source files.
- `pip check`: no broken requirements.
- Deterministic replay: unchanged before and after at
  `014403f6ce1549d8b390a723870cbe709a18953782f6dffe6ae84ddd2b924e89`.

The first bare `py` test invocation selected the machine's Python 3.13 outside the project
environment and failed package import during collection. The same Foundation level was rerun with
the existing Python 3.12 project interpreter and passed. A separate pytest run encountered the
known Windows global-temp-directory ACL error; rerunning the same level with a unique isolated temp
base passed. Neither was an application defect.

The final browser dogfood used the already validated Phase 8C DBL response from the ignored local
audit and rebuilt and revalidated its exact context before display. Installed Chrome was exercised
at 1,440 x 1,000 and 390 x 844. At both sizes the claim-level source control was discoverable, one
interaction opened the exact DBL hard-gate record, the calculation summary and complete sanitized
record wrapped without horizontal overflow, and source/date/category/locator/conflict/raw-ID fields
remained readable. The shared conversation and selected DBL hard-gate context remained visible.
Network observation recorded zero external requests during either citation interaction. The first
browser-control integration could not initialize because its local kernel-assets path was missing;
the existing ignored Playwright harness then completed the same checks against installed Chrome.

**GO for deployment from the Phase 8D citation-usability gate.** The remaining limitation is that
the sanitized evidence contract does not carry original public URLs. The application therefore
provides precise in-app provenance and locators, but an original-source link can appear only if a
verified URL is added to the evidence metadata in a separately authorized future change.
