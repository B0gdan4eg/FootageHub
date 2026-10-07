FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (minimal set for AI bot)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
COPY requirements/ai-bot.txt requirements/ai-bot.txt
RUN pip install --no-cache-dir -r requirements/ai-bot.txt

# Copy shared code
COPY shared/ /app/shared/

# Copy AI bot code
COPY ai_bot/ /app/ai_bot/

# Copy migrations (shared database)
COPY migrations/ /app/migrations/
COPY alembic.ini /app/alembic.ini

# Environment
ENV PYTHONPATH=/app
ENV PYTHONIOENCODING=utf-8
ARG APP_REVISION=unknown
ENV APP_REVISION=$APP_REVISION

CMD ["python", "-m", "ai_bot.main"]
