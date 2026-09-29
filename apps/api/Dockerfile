FROM python:3.12.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/alembic.ini /app/apps/api/
ENV UV_NO_CACHE=1
RUN uv sync --project /app/apps/api --frozen --no-dev --no-install-project
COPY apps/api/src /app/apps/api/src
COPY apps/api/migrations /app/apps/api/migrations
RUN uv sync --project /app/apps/api --frozen --no-dev
COPY scripts /app/scripts
RUN mkdir -p /app/data/generated
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
ENV PATH="/app/apps/api/.venv/bin:${PATH}"
CMD ["uvicorn", "datatalk.main:app", "--host", "0.0.0.0", "--port", "8000"]
