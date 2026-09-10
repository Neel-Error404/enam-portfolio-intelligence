# Phase 9: Azure Container Apps deployment and execution record

Status as of **2026-09-10: deployed and hosted-verified within the acceptance scope recorded
below.** The active budget-fix revision is healthy, all four application views were
browser-verified, and one new hosted user-facing AI generation after that fix passed validation
and manual claim-support review. The deterministic portfolio decision boundary is unchanged.

This document separates the verified execution record from retained operator procedures.
Commands below are for future, explicitly authorized operations; their presence does not mean
every optional acceptance, rollback, or hardening procedure was executed.

## Verified execution record: 10 September 2026

The deployment used baseline `4fb20a2304b9a56a59991b1ae8992c025e42e36d` plus the reviewed Phase 9
packaging changes and the subsequent AI request-budget fix. The source baseline alone does not
identify the deployed runtime; use the image digests and revision names below.

| Resource or boundary | Verified state |
|---|---|
| Resource group / region | `rg-enam-assessment-ci` / Central India |
| Container Apps environment | `cae-enam-assessment-ci` |
| Container registry | `acrenamassessmentci`, Basic, admin account disabled |
| Application | `ca-enam-assessment-ci` |
| User-assigned managed identity | `id-enam-assessment-ci` |
| Hosted URL | `https://ca-enam-assessment-ci.proudsand-d17a58a5.centralindia.azurecontainerapps.io/` |
| Active revision | `ca-enam-assessment-ci--phase9-b4000`, healthy |
| Credential-free rollback revision | `ca-enam-assessment-ci--wo9pv33`, healthy but inactive |
| Ingress / scaling / health | HTTPS-only, target port `8501`, minimum `0` / maximum `1` replica; health endpoint HTTP `200`, body `ok` |

The initial image `acrenamassessmentci.azurecr.io/enam:phase9-4fb20a2` was built by ACR run `cu1`.
Its digest is:

```text
sha256:baffad81b69ac25b8ed8c0bf1c264cac7da47fddbde58db9005f854aa544178a
```

The AI budget correction sets `DEFAULT_QUESTION_INPUT_TOKENS` to `4000` and prunes context against
the full request budget, not just the context payload. The active image is
`acrenamassessmentci.azurecr.io/enam:phase9-4fb20a2-b4000`, built by ACR run `cu2`, with digest:

```text
sha256:a1ca6be97c2320ac58fb51acccd8a9a78e6649e66c9ff9cd7d115c70e6ceac81
```

ACR run `cu2` succeeded despite an Azure CLI local CP1252 streaming-display error. That display
failure was not treated as evidence of a remote build failure; the successful ACR build and
resulting image digest established the outcome.

All four views were browser-verified: Portfolio Cockpit, Investor Behaviour, Company Intelligence,
and Assumptions & Audit. Navigation did not trigger inference. This proves the observed hosted
flow, not production reliability, concurrent-user isolation, or durable session retention.

### Earlier credential-free acceptance before AI enablement

The credential-free deployment was accepted before adding AI configuration. At that earlier
acceptance checkpoint, revision `ca-enam-assessment-ci--wo9pv33` was observed as `Healthy`, and
its HTTPS `/_stcore/health` endpoint returned HTTP `200` with body `ok`.

All four deterministic views loaded in the browser with frozen portfolio values unchanged:
Portfolio Cockpit, Investor Behaviour, Company Intelligence, and Assumptions & Audit. The UI
showed its explicit AI-not-configured state. Navigation and ordinary rendering made no Azure
OpenAI request.

These are recorded observations from the earlier accepted credential-free deployment, not
inferences from that revision's current healthy-but-inactive rollback state.

### Hosted AI acceptance after the budget fix

The app uses secret `aoai-api-key` through `AZURE_OPENAI_API_KEY`, with the endpoint in a nonsecret
environment variable. Neither the API key nor endpoint value is recorded here. Configuration was
deployment `gpt-5.6-terra`, reasoning effort `low`, and maximum output `2200` tokens.

Exactly **one new hosted user-facing generation after the 4000-token fix** was executed. This
count is scoped to that acceptance step, not a claim about all earlier local or hosted requests.

| Acceptance field | Recorded result |
|---|---|
| Status | `generated` |
| Response ID | `resp_0a3453afaed7d017006aa2dcd6e8e88197868ba1400dc8b1d9` |
| Provider-reported usage | Input `3527`, output `1021`, reasoning `0`, total `4548` tokens |
| Answer contract | `portfolio-answer-v1` |
| Prompt version | `portfolio-intelligence-prompt-v1` |
| Selected artifacts | `dbl-decision-summary`, `dbl-hard-gates` |
| Citation validation | Cited IDs were a subset of the included evidence IDs; no unsupported citations |
| Manual claim-support verdict | Passed for this answer |
| Deterministic boundary | Preserved DBL `SELL` / `REVIEW_REQUIRED`; explained `7244 / 1766 ~= 4.10x > 4.0x` |

The request included these evidence IDs:

```text
artifact:dbl-decision-summary
artifact:dbl-hard-gates
decision:dbl
fundamental-45adc13be8367240
fundamental-670dd97c37c6fd3b
fundamental-7dbb39273996c745
fundamental-c02d7f1564a6c6e4
fundamental-dbl-consolidated-net-debt-fy26
fundamental-dbl-standalone-net-debt-fy26
research-dbl-2026-05-15-p1-debt-summary
research-dbl-2026-05-15-p5-debt
session:active-portfolio
```

Citation allow-list validation establishes traceability; the manual verdict applies to this
reviewed answer and does not guarantee semantic correctness for future generations.

### Current operational and cost boundary

The hosted app is public and has no authentication. With paid AI configured, anyone who can reach
it can submit potentially billable questions. Explicit submit, token bounds, a one-replica limit,
and session caching are not access controls or a spending cap.

Minimum zero replicas permits scale-to-zero, cold starts, and session loss. Audit files are
container-local and ephemeral; there are no durable logs, authentication, or persistence. The
healthy credential-free revision is an inactive rollback source, not active protection: a
rollback operation still needs authorization and verification, and app-scoped secrets are not
reverted with revisions.

The current Azure consumption query succeeded and returned **0 posted items**. This is **not
proof of zero final charge** because billing can lag. The list-price estimates below remain
planning estimates, not confirmed charges; remaining sponsorship credit and its application
remain unverified.

## Verified boundary and observed environment

The Phase 9 starting baseline was `4fb20a2304b9a56a59991b1ae8992c025e42e36d` on branch `main`,
with a clean starting tree before container-readiness work. This baseline is retained for
provenance, not as a claim that it includes the packaging and budget changes identified above.

The preparation-stage read-only observations supplied for this runbook, dated 2026-09-10, are:

- Azure CLI `2.77.0`, `containerapp` extension `1.2.0b4`.
- Active, enabled **Microsoft Azure Sponsorship** subscription; subscription Owner and Azure AI
  Administrator roles observed. This does not establish remaining sponsorship credit.
- `Microsoft.App`, `Microsoft.ContainerRegistry`, and `Microsoft.OperationalInsights` registered.
- No local Docker, podman, or nerdctl. WSL2 is enabled but has no installed distribution.
- `dev-vm2` is Windows, deallocated, and was not used. Do not start it for this procedure.

Full subscription, tenant, and user identifiers are deliberately omitted. The preparation
observations alone did not prove regional provisioning or ACR Tasks availability; the execution
record above now establishes the deployed Central India outcome. They do not establish future
quota, remaining credit, or authorization for further charges. Reconfirm the selected subscription
privately before another approved operation. Do not read protected source inputs or credentials
to prepare deployment documentation.

## Runtime contract

The image uses `python:3.12-slim` (Linux), working directory `/app`, the project's normal runtime
dependencies (`pip install .`, without `[dev]`), and UID/GID `10001:10001`. No OS packages,
development tools, credential arguments, or source-ingestion commands are added. Dependency ranges
and the upstream base tag are not locked; record the resulting digest, since the source commit
alone does not make later rebuilds byte-identical.

The only repository payload copied into the image is:

| Input | Runtime purpose |
|---|---|
| `pyproject.toml`, `src/**` | Install the existing application package and runtime dependencies |
| `app.py` | Streamlit entry point |
| `.streamlit/config.toml` | Existing theme and disabled telemetry |
| `decision/decision_snapshot.json` | Frozen deterministic portfolio decisions |
| `evidence/normalized_snapshot.json` | Sanitized citation evidence |
| `evidence/historical_analysis_summary.json` | Structured historical presentation |
| `memos/company_memos.json` | Existing sanitized company-memo artifact |
| `prompts/portfolio_intelligence_prompt_v1.txt` | Explicit-submit intelligence prompt |

`.dockerignore` starts with `**`, then permits only Dockerfile and those inputs. Selective
directories are denied again before exact-file exceptions; `src/**` has final nested exclusions.
Protected `assessment_inputs`, PDF/XLS/XLSX/XLSM files, secrets, `.env`, credentials, Git metadata,
tests, docs, scripts, infra, raw data, generated artifacts, screenshots, caches, virtual
environments, and build outputs are excluded. The Docker build machinery may still transfer its
Dockerfile and ignore file as control files; neither is copied into `/app`.

This is a packaging boundary, not a content-classification engine: allowed source and curated JSON
must still be reviewed for sensitive content. In particular, sanitized portfolio artifacts still
contain information that must be approved for the intended audience. Never replace exact `COPY`
statements with `COPY . .`, append exceptions after the final denials, or run ACR Build with an
unreviewed context. Static tests check rules and sources, not Docker/ACR's actual context packing.

Streamlit runs headless at `0.0.0.0:8501` with usage telemetry disabled. The Docker health command
uses Python's standard-library `urllib.request`, a three-second timeout, HTTP 200 and body `ok`
from `http://127.0.0.1:8501/_stcore/health`; it needs neither curl nor Azure configuration.
Container Apps separately supplies HTTP Startup, Liveness, and Readiness probes on the same path.
A healthy process endpoint is not proof that portfolio loading, browser WebSockets, or AI works.

## Hosting design and state semantics

Deployed architecture: browser over HTTPS -> external Container Apps ingress -> one Linux
Streamlit container -> packaged frozen artifacts; explicit user submit optionally calls the
existing Azure OpenAI resource. A dedicated new resource group contains a Consumption Container
Apps environment, Basic ACR, and a user-assigned managed identity (UAMI). The UAMI pulls images;
it is not the app's OpenAI credential.

There is no database, vector store, microservice split, autonomous agent, application
authentication, or new OpenAI resource in this assessment design. ACR is build/image support, not
an application data service. Those additions would change the architecture, proof standard, and
cost boundary and therefore require separate authorization.

The first-deploy template is JSON-shaped valid YAML, parsed by the Foundation tests without
introducing a YAML dependency. It declares the entire app configuration: environment, Consumption
profile, UAMI, identity-backed registry, Single revision mode, latest-revision traffic 100%,
external HTTPS-only ingress (`allowInsecure: false`, target port 8501, `transport: auto`),
0.5 vCPU / 1 GiB, minimum zero / maximum one replica, and all three HTTP probes.
Its field structure was reviewed against the official Container Apps CLI and probe documentation.
The credential-free deployment was subsequently created in Azure; its recorded revision is
healthy and inactive after promotion of the budget-fix revision.

The first-deploy template image reference is `<ACR_LOGIN_SERVER>/enam:phase9-4fb20a2`; the active
deployment uses the `phase9-4fb20a2-b4000` image recorded above. These tags name the baseline plus
their reviewed changes, not the baseline alone. Tags become immutable only after the operator
locks the built manifest/tag. Preserve the recorded digests; do not infer a tag lock from a
successful build, and never rebuild into either recorded tag.

Session state (holdings overlays, cash, scenarios, dispositions, conversations, answer cache, and
manual claim review) is in Streamlit memory. Browser reload/reconnection, process replacement,
scale-to-zero, or a revision change can lose it. Maximum one replica does not make it durable.
Sticky sessions are unnecessary at maximum one replica and would not preserve session data.
Scale-to-zero may introduce cold-start delay; open browser/WebSocket activity may keep work active.

`/app/artifacts/phase8b` is created writable for the non-root account. The existing
`live_answer_audit.jsonl` is container-local, may include question/answer metadata from multiple
sessions handled by that process, and is not a durable or per-user audit database. There is no
volume mount, external audit sink, or persistence guarantee. It can disappear with container
replacement or scale-to-zero. Review and download session artifacts explicitly when needed; do
not claim audit retention or retrieve another session's information through a shared filesystem.

## Approval and inputs required for further operation

The execution record above describes the completed stages; this retained approval checklist is
not permission to repeat them. Obtain explicit approval for each further stage: resource
creation/build, public hosting with no AI key, adding or changing paid-inference credentials, and
any additional AI acceptance call. Required inputs are:

1. Privately confirmed sponsorship subscription and acceptable spending/credit exposure.
2. New resource-group, environment, globally unique ACR, app, and UAMI names.
3. Actual existing Azure OpenAI resource region and endpoint. Hosting was deployed in **Central
   India**, superseding the preparation-stage South India proposal. Do not infer the OpenAI
   resource's region from the hosting region or a resource name; reconfirm availability, quota,
   and price before a new deployment.
4. Permission to expose the curated portfolio publicly, plus the approved duration/audience.
5. Approved OpenAI deployment `gpt-5.6-terra`, valid key provided through a secure operator path,
   and endpoint or v1 base URL. No new OpenAI resource/deployment is part of this runbook.
6. Logging/retention choice. The example uses environment logs destination `none` to avoid
   silently provisioning Log Analytics; accept the corresponding diagnostic limits or approve
   a separate logging configuration and its costs.
7. Acceptance of `minReplicas: 0` and its cold-start/session-loss behavior, or an explicitly
   approved nonzero minimum with its additional compute cost. The reviewed template remains zero.

**Security gate:** this design has a public, no-auth URL. Anyone who can reach it could view the
sanitized portfolio and, once the key is configured, trigger paid inference through explicit
submits. One replica, session caching, and a token limit are not a spend cap or an access control.
Do not add the key unless this exposure is accepted or a separately authorized access-control
solution is in place. Authentication implementation is deferred, not silently included.

## Local checks and optional Docker smoke: retained local procedure

Use PowerShell from the repository root and the existing Python 3.12 project environment. On this
machine the literal `py -3.12 -m pytest ...` command selects the system interpreter, where pytest
and Ruff are not installed; it fails before test collection. Do not install project tooling
globally to change that. The equivalent bounded checks use the existing `.venv` interpreter:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_containerization.py `
    --basetemp artifacts/pytest-phase9-foundation
# Only after Foundation passes:
& .\.venv\Scripts\python.exe -m pytest tests/test_streamlit_app.py `
    --basetemp artifacts/pytest-phase9-component
& .\.venv\Scripts\python.exe -m ruff format --check tests/test_containerization.py
& .\.venv\Scripts\python.exe -m ruff check tests/test_containerization.py
```

The preparation-stage local result was 16 Foundation tests passed, 23 Component tests passed, and
both Ruff checks passed. These are historical static/local application checks, not a new test run
for the budget fix or the source of the hosted verification recorded above.

Docker is absent here. The following commands are **documentation only, not executed**, for an
approved machine with a Linux Docker engine. Installing Docker or using another machine requires
separate approval. This local smoke passes no OpenAI variables, key, bind mount, or source inputs:

```powershell
docker build --platform linux/amd64 --tag enam:phase9-4fb20a2 .
if ($LASTEXITCODE -ne 0) { throw 'Container build failed; stop and inspect its output.' }
docker run --detach --name enam-phase9-smoke --publish 127.0.0.1:8501:8501 enam:phase9-4fb20a2
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed; stop and inspect its output.' }
Invoke-WebRequest http://127.0.0.1:8501/_stcore/health
docker inspect enam-phase9-smoke --format '{{json .State.Health}}'
docker exec enam-phase9-smoke id
docker exec enam-phase9-smoke python -c "from pathlib import Path; p=Path('/app/artifacts/phase8b/smoke.txt'); p.write_text('writable'); p.unlink()"
docker exec enam-phase9-smoke python -c "from pathlib import Path; print('\n'.join(str(p) for p in Path('/app').rglob('*') if p.is_file()))"
```

Wait for healthy status, inspect the file inventory, then check all views in a browser at
`http://127.0.0.1:8501`, including a working WebSocket connection and clear no-config AI messaging.
Do not submit an inference. Inspect logs without publishing their contents. When finished,
`docker stop enam-phase9-smoke` then `docker rm enam-phase9-smoke` removes this named disposable
container and its ephemeral audit data; retain any deliberately created test evidence first.

## Azure provision, remote build, and first deployment: retained operator procedure

The execution record above captures the completed deployment. The following reusable commands
incur charges and change external state; do not rerun them as a status check.
Use a new, dedicated resource group, not an existing workload or `dev-vm2`. Run blocks one at a
time; stop on any nonzero exit code. The helper below raises explicit failures for native CLI
commands rather than allowing PowerShell to continue after a failed `az` call.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-EnamAz {
    & az @args
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed (exit $LASTEXITCODE); stop this stage." }
}
$Subscription = '<APPROVED_SUBSCRIPTION_ID>' # Keep private; never paste into this document.
$Region = '<APPROVED_REGION>' # Executed hosting region: centralindia; reapprove for a new deployment.
$ResourceGroup = '<NEW_RESOURCE_GROUP>'
$Environment = '<NEW_CONTAINER_APPS_ENVIRONMENT>'
$Registry = '<GLOBALLY_UNIQUE_ACR_NAME>'
$App = '<NEW_CONTAINER_APP_NAME>'
$Identity = '<NEW_UAMI_NAME>'
$ImageTag = 'phase9-4fb20a2'
if (@($Subscription, $Region, $ResourceGroup, $Environment, $Registry, $App, $Identity) |
        Where-Object { $_ -match '[<>]' }) {
    throw 'Approve and replace every placeholder before running Azure operations.'
}
Invoke-EnamAz account set --subscription $Subscription
Invoke-EnamAz group create --name $ResourceGroup --location $Region --output none
Invoke-EnamAz acr create --resource-group $ResourceGroup --name $Registry --location $Region `
    --sku Basic --admin-enabled false --role-assignment-mode rbac --output none
Invoke-EnamAz containerapp env create --name $Environment --resource-group $ResourceGroup `
    --location $Region --logs-destination none --output none
Invoke-EnamAz identity create --name $Identity --resource-group $ResourceGroup `
    --location $Region --output none

$AcrId = Invoke-EnamAz acr show --name $Registry --query id --output tsv
$AcrServer = Invoke-EnamAz acr show --name $Registry --query loginServer --output tsv
$UamiId = Invoke-EnamAz identity show --name $Identity --resource-group $ResourceGroup `
    --query id --output tsv
$PrincipalId = Invoke-EnamAz identity show --name $Identity --resource-group $ResourceGroup `
    --query principalId --output tsv
$EnvironmentId = Invoke-EnamAz containerapp env show --name $Environment `
    --resource-group $ResourceGroup --query id --output tsv
Invoke-EnamAz role assignment create --assignee-object-id $PrincipalId `
    --assignee-principal-type ServicePrincipal --role AcrPull --scope $AcrId --output none
```

Keep ACR in **RBAC registry permissions** mode for the `AcrPull` contract; do not silently switch
to ABAC repository permissions and assume the same role works. The ACR admin account stays disabled.
Managed-identity image pull also requires ACR ARM-audience authentication to be enabled. Check the
setting and, for this new dedicated registry, enable it if necessary after approval:

```powershell
Invoke-EnamAz acr config authentication-as-arm show --registry $Registry
# Only if disabled, and within the approved registry configuration:
Invoke-EnamAz acr config authentication-as-arm update --registry $Registry --status enabled
```

Allow role propagation and confirm the role is assigned before deployment. On a pull failure,
inspect the role, registry mode, identity, and ARM-audience setting; do not enable admin credentials
or add silent credential fallbacks.

Before the next block, rerun Foundation tests, review `.dockerignore`, enumerate its exact allowed
inputs, and confirm no protected files or secrets exist in the allowed payload. ACR Build uploads
the filtered local context and builds remotely without local Docker. Verify the CLI's actual
uploaded-context listing/package at this operator gate; static allowlist tests alone are not an
exfiltration proof. Stop if the upload includes anything outside the contract.

```powershell
Invoke-EnamAz acr build --registry $Registry --platform linux/amd64 `
    --image "enam:$ImageTag" --file Dockerfile .
$ImageDigest = Invoke-EnamAz acr repository show --name $Registry --image "enam:$ImageTag" `
    --query digest --output tsv
if ($ImageDigest -notmatch '^sha256:[a-f0-9]{64}$') {
    throw 'ACR did not return the expected image digest; do not deploy.'
}
Invoke-EnamAz acr repository update --name $Registry --image "enam:$ImageTag" `
    --write-enabled false --delete-enabled false --output none
```

Record build run ID, source baseline, reviewed packaging diff, actual runtime package versions,
Linux/amd64 platform, tag, and digest in the approved evidence location. The digest is the runtime
identity; the baseline label alone does not prove the full image contents.

Render placeholders only after values and the credential-free deployment are approved. The
temporary file belongs under existing Git-ignored `artifacts/phase9`, which is also excluded from
the build context. Never render the template in `infra` or commit resolved IDs. The tracked
template deliberately contains no `env`, secret, API key, or `secretRef`.

```powershell
$RenderDirectory = Join-Path (Get-Location) 'artifacts\phase9'
New-Item -ItemType Directory -Path $RenderDirectory -Force | Out-Null
$RenderedYaml = Join-Path $RenderDirectory 'containerapp.first-deploy.yaml'
$TemplateText = Get-Content -LiteralPath 'infra\containerapp.template.yaml' -Raw
$Replacements = @{
    '<APP_NAME>' = $App
    '<AZURE_REGION>' = $Region
    '<UAMI_RESOURCE_ID>' = $UamiId
    '<ENVIRONMENT_RESOURCE_ID>' = $EnvironmentId
    '<ACR_LOGIN_SERVER>' = $AcrServer
}
foreach ($Placeholder in $Replacements.Keys) {
    if ([string]::IsNullOrWhiteSpace($Replacements[$Placeholder])) {
        throw "Missing approved value for $Placeholder."
    }
    $TemplateText = $TemplateText.Replace($Placeholder, $Replacements[$Placeholder])
}
if ($TemplateText -match '<[A-Z_]+>') { throw 'Unresolved deployment placeholder.' }
$null = $TemplateText | ConvertFrom-Json
[System.IO.File]::WriteAllText($RenderedYaml, $TemplateText, [System.Text.UTF8Encoding]::new($false))
Invoke-EnamAz containerapp create --resource-group $ResourceGroup --name $App `
    --yaml $RenderedYaml --output none
$Fqdn = Invoke-EnamAz containerapp show --resource-group $ResourceGroup --name $App `
    --query properties.configuration.ingress.fqdn --output tsv
if ([string]::IsNullOrWhiteSpace($Fqdn)) { throw 'No hosted FQDN returned; inspect deployment state.' }
Invoke-WebRequest "https://$Fqdn/_stcore/health"
Invoke-EnamAz containerapp revision list --resource-group $ResourceGroup --name $App --output table
```

**`--yaml` is the complete app configuration surface.** Do not assume `--image`, ingress,
environment, identity, resource, or environment-variable flags combine with it. Put configuration
in the reviewed YAML when using that path. The CLI still requires both `--name` and
`--resource-group` selectors; they identify the target app and destination and do not replace
configuration omitted from the YAML. JSON parsing and static tests are not ARM validation.
If the installed extension rejects a field, stop and reconcile official CLI/service schema before
deployment; do not add an unreviewed alternate deployment path.

Run the credential-free hosted acceptance checks below before moving on.

## Optional OpenAI enablement: separate secret and configuration revision

This stage was executed with the configuration recorded above. The retained procedure requires
separate authorization for any repeat or change. No Key Vault is introduced for this
assessment. Use Container Apps secret `aoai-api-key`, referenced by environment variable
`AZURE_OPENAI_API_KEY`. Do not put the key in an image, Docker ARG, repository file, rendered
YAML, transcript, screenshot, or ordinary shell-history command.

The revision environment contract is:

| Name | Value |
|---|---|
| `AZURE_OPENAI_API_KEY` | App-secret reference `aoai-api-key` |
| `AZURE_OPENAI_ENDPOINT` **or** `AZURE_OPENAI_BASE_URL` | Approved Azure resource root, or complete URL ending `/openai/v1/`; choose one |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-5.6-terra` |
| `ENAM_INTELLIGENCE_REASONING_EFFORT` | `low` |
| `ENAM_INTELLIGENCE_MAX_OUTPUT_TOKENS` | `2200` |

Read the key interactively after approval. This avoids a literal key in shell history, but Azure
CLI still receives it as a process argument; a privileged local observer can inspect it. Do not
run with `--debug`, process tracing, or PowerShell transcription. If that local exposure is
unacceptable, use the Azure portal's secret editor instead; do not weaken the secret policy.

```powershell
$Endpoint = '<APPROVED_AZURE_OPENAI_RESOURCE_ROOT>'
if ($Endpoint -match '[<>]' -or $Endpoint -notmatch '^https://') {
    throw 'Set the approved HTTPS Azure OpenAI resource-root endpoint first.'
}
$SecureApiKey = Read-Host 'Azure OpenAI API key (not echoed)' -AsSecureString
$KeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureApiKey)
try {
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($KeyPointer)
    if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw 'An API key is required for this stage.' }
    Invoke-EnamAz containerapp secret set --resource-group $ResourceGroup --name $App `
        --secrets "aoai-api-key=$ApiKey" --output none
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($KeyPointer)
    Remove-Variable ApiKey, SecureApiKey, KeyPointer -ErrorAction SilentlyContinue
}
# This is a standalone update, NOT a combination with --yaml.
Invoke-EnamAz containerapp update --resource-group $ResourceGroup --name $App `
    --set-env-vars 'AZURE_OPENAI_API_KEY=secretref:aoai-api-key' `
        "AZURE_OPENAI_ENDPOINT=$Endpoint" 'AZURE_OPENAI_DEPLOYMENT=gpt-5.6-terra' `
        'ENAM_INTELLIGENCE_REASONING_EFFORT=low' 'ENAM_INTELLIGENCE_MAX_OUTPUT_TOKENS=2200' `
    --revision-suffix phase9-ai --output none
```

For a v1 base URL, replace the endpoint environment entry with
`AZURE_OPENAI_BASE_URL=https://<approved-host>/openai/v1/`; do not set both. Verify the runtime's
configured mode without displaying secret values. A partial or invalid configuration is an
explicit error, not an automatic inference fallback. With no key/endpoint, deterministic views
remain available and AI is clearly unconfigured. There is no startup model call.

Secrets are app-scoped, not revision-scoped. Changing a secret does not itself create a new
revision; the environment-variable update above creates the separate AI revision. Later key
rotation requires restarting affected replicas/revisions or creating a fresh revision so running
containers receive the new value. Reusing `phase9-ai` for a later update can conflict; use a fresh
reviewed revision suffix. Single mode moves traffic after the new revision becomes ready, but
browser sessions must not be assumed to survive the switch.

## Hosted acceptance gates: repeatable checklist and proof limits

Record evidence without keys or full account identifiers. Neither Foundation tests nor HTTP
health alone satisfies this checklist. The execution record above states what was verified;
this broader checklist does not imply that every item below was completed.

1. **First, no-config/no-inference:** confirm ready revision, external HTTPS, port 8501, all three
   probe definitions, min/max replicas, and registry identity. Resolve the deployed image tag to
   the recorded locked digest, confirm source label/build record, and inspect runtime UID and
   file inventory. Verify protected inputs, docs/tests, `.env`, credentials, and raw audit/source
   artifacts were not shipped. Check the writable audit directory without retaining a test file.
2. Open every application view and inspect the browser WebSocket connection. Verify frozen
   portfolio values and citation cards, historical view, session-only holdings, scenarios, and
   dispositions. Check unconfigured AI status; do not authorize or generate a provider request.
   Ordinary reruns, navigation, and citation interactions must not call the provider.
3. In two independent browser sessions, confirm overlays, cash, dispositions, conversation, and
   cache do not bleed between users. Confirm a new session/restart cannot claim durable saved
   state. Observe cold-start/reconnection behavior without promising persistence.
4. Only after separate approval of public access and paid usage, add the AI configuration revision.
   Submit **one** bounded question. Verify grounded answer validation, expected deployment and
   settings, response/token usage where returned, and a repeat identical submit served from the
   same-session cache. Do not imply another session shares that cache or that it prevents abuse.
   A changed question is another potentially paid call and needs the agreed test budget.
5. Verify session export semantics and audit ephemerality. Container-local audit is not a durable
   governance record; loss across replacement must be documented, not treated as data persistence.
6. Test an explicitly authorized rollback/redeploy, reconfirm image digest and active revision,
   health, browser operation, and no-config behavior. No inference is implicit in rollback testing.

Access controls, load/stress testing, managed OpenAI authentication, persistent storage, monitoring
alerts, automated deployment, and production hardening are deferred. This record does not claim
concurrent-session isolation, repeat-submit cache acceptance, a performed rollback/redeploy, or a
complete hosted Integration/Workflow/Stress suite beyond the specific observations recorded above.

## Cost envelope, not a bill or a credit balance

Observed public retail rates on **2026-09-10 for Central India**, supplied by the preparation
review, are estimates for planning only. Central India is the executed hosting region; rates for
other regions may differ.
USD, before taxes; actual chargeable usage and sponsorship application are unverified.

| Item | Observed estimate and simple arithmetic |
|---|---|
| Basic ACR | `$0.1666/day * 30.4 days = $5.06464`, approximately **$5.07/month** |
| ACR Tasks build | `$0.0001/vCPU-second`; e.g. `2 vCPU * 300 seconds * $0.0001 = $0.06` for a five-minute build at that allocation |
| ACA active CPU | `$0.000024/vCPU-second`; at 0.5 vCPU, `$0.0432/active hour` |
| ACA memory | `$0.000003/GiB-second`; at 1 GiB, `$0.0108/active hour` |
| Active compute subtotal | `$0.0432 + $0.0108 = $0.054/active hour` before free grants |
| Requests | `$0.40/million` billable requests, after applicable grants |

The monthly Consumption free grants are **180,000 vCPU-seconds, 360,000 GiB-seconds, and
2 million requests**, shared across eligible usage in the subscription, not reserved for this
app. With 0.5 vCPU / 1 GiB and the full CPU/memory grants unused elsewhere, each compute grant
covers 100 active hours. This is arithmetic, not a promise of free usage. At continuous active
allocation for 30.4 days, pre-grant compute is `729.6 hours * $0.054 = $39.3984`; with both full
compute grants available, that illustrative figure becomes about `$33.9984`, before registry,
builds, requests, or other costs.

At zero replicas there is no Container Apps compute charge; ACR and other retained services can
still cost money. Azure can distinguish active and idle usage, so the always-active illustration
is not a prediction of this app's bill. Long-lived sessions and traffic affect actual activity.
The one-replica ceiling is resource sizing, not financial authorization or an inference spend cap.

OpenAI inference, logs if enabled, egress, other storage, taxes, region differences, and actual
ACR build allocation/duration are unknown. No reliable total can be stated without those inputs.
Sponsorship exists; its **remaining credit and application to these charges are unverified**.
Cloud provisioning, two ACR builds, and hosted AI inference were executed. The successful current
Azure consumption query returned **0 posted items**, not a confirmed final bill of zero. Billing
lag can delay posted usage; no reliable total charge or remaining credit balance is established.

## Rollback, redeploy, and teardown gates

Record the credential-free and AI revision names and each immutable image digest before promotion.
For a code rollback in Single mode, copy the known-good revision to a new revision and verify
traffic/readiness. The recorded credential-free source is `ca-enam-assessment-ci--wo9pv33`
(healthy, inactive); the active revision is `ca-enam-assessment-ci--phase9-b4000`. The command
below is a retained procedure, not evidence that a rollback was performed:

```powershell
$KnownGoodRevision = '<RECORDED_KNOWN_GOOD_REVISION>'
$RollbackSuffix = '<NEW_UNIQUE_ROLLBACK_SUFFIX>'
Invoke-EnamAz containerapp revision copy --resource-group $ResourceGroup --name $App `
    --from-revision $KnownGoodRevision --revision-suffix $RollbackSuffix --output none
Invoke-EnamAz containerapp revision list --resource-group $ResourceGroup --name $App --output table
```

Copy the recorded **credential-free** revision to return to no-config behavior; copying an AI
revision retains its secret references. App-scoped secrets are not reverted with revisions.
For incident containment, first disable ingress or otherwise remove access under explicit
authorization, then remove the AI environment configuration and verify no live revision can
invoke the provider. Only after references are removed should `aoai-api-key` be removed. Do not
assume removing a secret immediately clears credentials from running processes.

For redeploy, use a fresh immutable tag for a changed source/packaging baseline, repeat context
review/build/digest/lock checks, and create a fresh revision. Never overwrite `phase9-4fb20a2` or
`phase9-4fb20a2-b4000`.
Do not apply the credential-free template to an AI-enabled app and assume it preserves secrets,
environment variables, or other settings: review the entire intended configuration.

Resource-group deletion is a separate destructive approval. Confirm the exact dedicated group
and its contents, export needed evidence, and explain that deleting it removes the app,
environment, registry images, UAMI, and associated group resources. Do not delete a broad or
pre-existing group and do not imply that scale-to-zero removes registry costs.

## Official references and verification limits

Official sources reviewed by the preparation phase on 2026-09-10:

- [Streamlit Docker tutorial](https://docs.streamlit.io/deploy/tutorials/docker)
- [Container Apps ingress](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview)
- [Health probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes)
- [Revisions](https://learn.microsoft.com/en-us/azure/container-apps/revisions)
- [Secrets](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)
- [Ephemeral and mounted storage](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts)
- [Sticky sessions](https://learn.microsoft.com/en-us/azure/container-apps/sticky-sessions)
- [Billing](https://learn.microsoft.com/en-us/azure/container-apps/billing)
- [Managed-identity image pull](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull)
- [Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp)
- [Revision CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp/revision)

Local static validation covers exact COPY/allowlist contracts, Python/non-root/start/health
configuration, required payload existence, and template fields. App Component tests cover local
Streamlit behavior with controlled provider configuration. Those tests alone do not prove remote
behavior. The execution record separately establishes ACR build success, the deployed image and
revision identities, hosted health, four-view browser operation, and one successful post-fix
user-facing generation with manual claim-support review.

It does not establish a final Azure charge, remaining credit, durable retention, production
security, load capacity, or every acceptance-checklist item. Before extending public operation or
authorizing more paid testing, confirm the accepted exposure duration and spending boundary.
Further hardening, rollback execution, teardown, and additional inference remain separately
authorized operations.
