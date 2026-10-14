FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY pyproject.toml main.py ./
COPY domain ./domain
COPY application ./application
COPY adapters ./adapters
RUN pip install --no-cache-dir '.[dev]'
COPY tests ./tests
COPY alembic.ini ./

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
