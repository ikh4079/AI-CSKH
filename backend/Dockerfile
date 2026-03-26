FROM python:3.11-slim

WORKDIR /app

COPY backend /app/backend
COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir /app/backend

ENV PYTHONPATH=/app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

