FROM python:3.11-slim

LABEL maintainer="FootageHub AI Bot"
LABEL description="AI content generation bot using Kie.ai API"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
COPY requirements/ai-bot.txt requirements/ai-bot.txt
RUN pip install --no-cache-dir -r requirements/ai-bot.txt

# Copy AI bot code
COPY ai_bot/ /app/ai_bot/

# Copy shared code if exists (for future database models, services)
# Will be added in Phase 1 of microservices migration
# COPY shared/ /app/shared/

# Copy alembic migrations if exists (for future database access)
# COPY alembic/ /app/alembic/
# COPY alembic.ini /app/alembic.ini

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the bot
CMD ["python", "-m", "ai_bot.main"]
