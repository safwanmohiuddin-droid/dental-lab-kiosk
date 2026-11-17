FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN SECRET_KEY=build-only DATABASE_URL=postgres://build@localhost/build \
    python manage.py collectstatic --noinput \
    && useradd --system --no-create-home app

USER app
EXPOSE 8000
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
