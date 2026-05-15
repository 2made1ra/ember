FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_CACHE_DIR=/app/.uv-cache \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/backend \
    PYTHONUNBUFFERED=1

COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --locked --no-dev

COPY backend ./backend

EXPOSE 8000

CMD ["uv", "run", "--project", "backend", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
