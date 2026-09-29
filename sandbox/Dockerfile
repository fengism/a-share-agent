FROM python:3.11-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.1 /uv /usr/local/bin/uv

FROM base AS worker
RUN uv pip install --system --no-cache numpy==2.4.6 pandas==3.0.5
COPY worker.py /opt/worker.py
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python", "-I", "-u", "/opt/worker.py"]

FROM base AS runner
COPY --from=docker:27.5.1-cli /usr/local/bin/docker /usr/local/bin/docker
RUN uv pip install --system --no-cache fastapi==0.141.1 uvicorn==0.52.4
COPY runner.py verify_runtime.py /opt/
WORKDIR /opt
# Exactly one control-plane worker; subprocesses execute docker CLI, NEVER submitted Python.
CMD ["uvicorn", "runner:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--limit-concurrency", "32", "--no-access-log"]
