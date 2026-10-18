FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/code/.venv/bin:$PATH"

WORKDIR /code

COPY pyproject.toml uv.lock composition.py ./
COPY entrypoints ./entrypoints
COPY domain ./domain
COPY application ./application
COPY adapters ./adapters
RUN uv sync --locked --extra dev --no-editable
COPY tests ./tests
COPY scripts ./scripts
COPY alembic.ini ./

EXPOSE 8000

CMD ["uvicorn", "entrypoints.server.api:app", "--host", "0.0.0.0", "--port", "8000"]
