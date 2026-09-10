"""Foundation contracts only; these checks do not build or run a container."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "4fb20a2304b9a56a59991b1ae8992c025e42e36d"
RUNTIME_FILES = (
    "pyproject.toml",
    "app.py",
    ".streamlit/config.toml",
    "decision/decision_snapshot.json",
    "evidence/normalized_snapshot.json",
    "evidence/historical_analysis_summary.json",
    "memos/company_memos.json",
    "prompts/portfolio_intelligence_prompt_v1.txt",
)
ALLOWED_CONTEXT = {
    "Dockerfile",
    *RUNTIME_FILES,
    ".streamlit/",
    "src/",
    "src/**",
    "decision/",
    "evidence/",
    "memos/",
    "prompts/",
}
NESTED_DENIALS = {
    "**/.env",
    "**/.env.*",
    "**/*[Ss]ecret*",
    "**/*[Cc]redential*",
    "**/*.key",
    "**/*.pem",
    "**/*.p12",
    "**/*.pfx",
    "**/*.crt",
    "**/*.cer",
    "**/*.xlsx",
    "**/*.xls",
    "**/*.xlsm",
    "**/*.pdf",
    "**/*.[Pp][Dd][Ff]",
    "**/*.[Xx][Ll][Ss]",
    "**/*.[Xx][Ll][Ss][Xx]",
    "**/*.[Xx][Ll][Ss][Mm]",
    "**/*[Ss][Ee][Cc][Rr][Ee][Tt]*",
    "**/*[Cc][Rr][Ee][Dd][Ee][Nn][Tt][Ii][Aa][Ll]*",
    "**/.git",
    "**/.venv",
    "**/venv",
    "**/__pycache__",
    "**/*.py[cod]",
    "**/*.egg-info",
    "**/.pytest_cache",
    "**/.mypy_cache",
    "**/.ruff_cache",
    "**/assessment_inputs",
    "**/data",
    "**/local_data",
    "**/raw",
    "**/decrypted",
    "**/artifacts",
    "**/outputs",
    "**/screenshots",
    "**/tests",
    "**/docs",
    "**/scripts",
    "**/infra",
    "**/.cache",
    "**/.firecrawl",
    "**/.azure",
    "**/.aws",
    "**/build",
    "**/dist",
}


def _dockerfile() -> str:
    return (ROOT / "Dockerfile").read_text(encoding="utf-8")


def _instruction(source: str, name: str) -> list[str]:
    return [
        line.removeprefix(name + " ") for line in source.splitlines() if line.startswith(name + " ")
    ]


@pytest.mark.parametrize("relative_path", RUNTIME_FILES)
def test_required_runtime_file_exists_inside_repository(relative_path: str) -> None:
    path = ROOT / relative_path
    assert path.is_file(), f"Required container input is missing: {relative_path}"
    assert path.resolve().is_relative_to(ROOT.resolve())
    assert not path.is_symlink(), f"Container input must not be a symlink: {relative_path}"


def test_runtime_source_package_exists_without_external_symlinks() -> None:
    source = ROOT / "src"
    assert (source / "enam_assessment" / "__init__.py").is_file()
    assert list(source.rglob("*.py")), "The runtime package has no Python source files."
    for path in source.rglob("*"):
        assert not path.is_symlink(), f"Runtime source must not contain symlinks: {path}"
        assert path.resolve().is_relative_to(source.resolve())


def test_dockerfile_uses_python312_and_only_project_runtime_dependencies() -> None:
    source = _dockerfile()
    assert _instruction(source, "FROM") == ["python:3.12-slim"]
    assert _instruction(source, "WORKDIR") == ["/app"]
    assert "python -m pip install --no-cache-dir ." in source
    assert ".[dev]" not in source
    assert "apt-get" not in source
    assert not _instruction(source, "ADD")
    assert not _instruction(source, "ARG")
    assert f'org.opencontainers.image.revision="{BASELINE}"' in source


def test_dockerfile_copies_only_the_exact_runtime_contract() -> None:
    copies = [json.loads(item) for item in _instruction(_dockerfile(), "COPY")]
    assert {item[0] for item in copies} == {*RUNTIME_FILES, "src/"}
    assert all(len(item) == 2 for item in copies)
    assert all(item[0] not in {".", "./", "**"} for item in copies)
    assert ["src/", "./src/"] in copies
    for relative_path in RUNTIME_FILES:
        destination = (
            "./" if "/" not in relative_path else "./" + relative_path.rsplit("/", 1)[0] + "/"
        )
        assert [relative_path, destination] in copies


def test_dockerfile_is_nonroot_with_a_writable_ephemeral_audit_directory() -> None:
    source = _dockerfile()
    assert _instruction(source, "USER") == ["10001:10001"]
    assert "groupadd --gid 10001 appuser" in source
    assert "useradd --uid 10001 --gid 10001 --create-home appuser" in source
    assert "mkdir -p /app/artifacts/phase8b" in source
    assert "chown appuser:appuser /app/artifacts/phase8b" in source
    assert source.index("chown appuser:appuser") < source.index("USER 10001:10001")
    assert "chmod 777" not in source
    assert "PYTHONDONTWRITEBYTECODE=1" in source
    assert not _instruction(source, "VOLUME"), "No persistence is part of this boundary."


def test_dockerfile_startup_needs_no_azure_configuration() -> None:
    source = _dockerfile()
    assert _instruction(source, "EXPOSE") == ["8501"]
    assert json.loads(_instruction(source, "CMD")[0]) == [
        "python",
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.address=0.0.0.0",
        "--server.port=8501",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    assert not _instruction(source, "ENTRYPOINT")
    assert "AZURE_OPENAI" not in source
    assert "API_KEY" not in source


def test_docker_healthcheck_uses_existing_streamlit_endpoint_and_stdlib() -> None:
    healthcheck = _instruction(_dockerfile(), "HEALTHCHECK")[0]
    options, command = healthcheck.split(" CMD ", maxsplit=1)
    assert options == "--interval=30s --timeout=5s --start-period=30s --retries=3"
    executable, flag, code = json.loads(command)
    assert (executable, flag) == ("python", "-c")
    assert "urllib.request" in code
    assert "http://127.0.0.1:8501/_stcore/health" in code
    assert "timeout=3" in code
    assert "response.status == 200" in code
    assert 'response.read().strip() == b"ok"' in code
    assert "else 1" in code
    compile(code, "<container-healthcheck>", "exec")
    assert "curl" not in code


def test_context_is_default_deny_with_exact_runtime_exceptions() -> None:
    rules = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert rules[0] == "**"
    exceptions = [rule[1:] for rule in rules if rule.startswith("!")]
    assert len(exceptions) == len(ALLOWED_CONTEXT)
    assert set(exceptions) == ALLOWED_CONTEXT
    # Selective directories are denied again before their one-file exceptions.
    for directory in (".streamlit", "decision", "evidence", "memos", "prompts"):
        assert rules.index(f"!{directory}/") < rules.index(f"{directory}/**")
        for relative_path in RUNTIME_FILES:
            if relative_path.startswith(directory + "/"):
                assert rules.index(f"{directory}/**") < rules.index(f"!{relative_path}")
    # Re-including src/** must never override nested secret/raw-data/cache denials.
    last_exception = max(index for index, rule in enumerate(rules) if rule.startswith("!"))
    assert NESTED_DENIALS <= set(rules[last_exception + 1 :])
    assert not any(rule.startswith("!") for rule in rules[last_exception + 1 :])


def test_first_deploy_template_is_complete_and_has_no_application_secret() -> None:
    # JSON is also valid YAML; stdlib parsing avoids a new test dependency.
    source = (ROOT / "infra/containerapp.template.yaml").read_text(encoding="utf-8")
    template = json.loads(source)
    assert template["identity"] == {
        "type": "UserAssigned",
        "userAssignedIdentities": {"<UAMI_RESOURCE_ID>": {}},
    }
    properties = template["properties"]
    assert properties["environmentId"] == "<ENVIRONMENT_RESOURCE_ID>"
    assert properties["workloadProfileName"] == "Consumption"
    configuration = properties["configuration"]
    assert configuration["activeRevisionsMode"] == "Single"
    assert configuration["ingress"] == {
        "external": True,
        "targetPort": 8501,
        "transport": "auto",
        "allowInsecure": False,
        "traffic": [{"latestRevision": True, "weight": 100}],
    }
    assert configuration["registries"] == [
        {"server": "<ACR_LOGIN_SERVER>", "identity": "<UAMI_RESOURCE_ID>"}
    ]
    assert "secrets" not in configuration
    assert "AZURE_OPENAI_API_KEY" not in source
    assert "secretRef" not in source
    runtime = properties["template"]
    assert runtime["scale"] == {"minReplicas": 0, "maxReplicas": 1}
    assert len(runtime["containers"]) == 1
    container = runtime["containers"][0]
    assert container["image"] == "<ACR_LOGIN_SERVER>/enam:phase9-4fb20a2"
    assert container["resources"] == {"cpu": 0.5, "memory": "1Gi"}
    assert {probe["type"] for probe in container["probes"]} == {
        "Startup",
        "Liveness",
        "Readiness",
    }
    for probe in container["probes"]:
        assert probe["httpGet"] == {"path": "/_stcore/health", "port": 8501, "scheme": "HTTP"}
        assert probe["timeoutSeconds"] >= 1
        assert probe["periodSeconds"] >= 1
        assert 1 <= probe["failureThreshold"] <= 10
    assert set(re.findall(r"<[A-Z_]+>", source)) == {
        "<APP_NAME>",
        "<AZURE_REGION>",
        "<UAMI_RESOURCE_ID>",
        "<ENVIRONMENT_RESOURCE_ID>",
        "<ACR_LOGIN_SERVER>",
    }
