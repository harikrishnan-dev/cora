FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
# The image already has the exact frozen, no-dev environment synced above --
# don't let `uv run` re-sync (and pull dev deps, and hit the network) on
# every container start.
ENV UV_NO_SYNC=1

EXPOSE 8501

ENTRYPOINT ["./docker-entrypoint.sh"]
