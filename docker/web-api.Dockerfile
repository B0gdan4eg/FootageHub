FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Зависимости
COPY requirements/base.txt requirements/base.txt
COPY requirements/web-api.txt requirements/web-api.txt
RUN pip install --no-cache-dir -r requirements/web-api.txt

# Код
COPY shared/ /app/shared/
COPY web_api/ /app/web_api/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/alembic.ini

ENV PYTHONPATH=/app
ENV PYTHONIOENCODING=utf-8

CMD ["uvicorn", "web_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
