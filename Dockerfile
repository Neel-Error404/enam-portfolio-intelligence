FROM python:3.12-slim

LABEL org.opencontainers.image.revision="4fb20a2304b9a56a59991b1ae8992c025e42e36d"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/appuser

WORKDIR /app

COPY ["pyproject.toml", "./"]
COPY ["src/", "./src/"]
RUN python -m pip install --no-cache-dir .

COPY ["app.py", "./"]
COPY [".streamlit/config.toml", "./.streamlit/"]
COPY ["decision/decision_snapshot.json", "./decision/"]
COPY ["evidence/normalized_snapshot.json", "./evidence/"]
COPY ["evidence/historical_analysis_summary.json", "./evidence/"]
COPY ["memos/company_memos.json", "./memos/"]
COPY ["prompts/portfolio_intelligence_prompt_v1.txt", "./prompts/"]

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home appuser \
    && mkdir -p /app/artifacts/phase8b \
    && chown appuser:appuser /app/artifacts/phase8b

USER 10001:10001

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3); raise SystemExit(0 if response.status == 200 and response.read().strip() == b\"ok\" else 1)"]

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
