FROM python:3.11-slim

WORKDIR /app

# Install system dependencies first (before Playwright)
RUN apt-get update && apt-get install -y \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Fonts (using available packages in Debian)
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    # Display server
    xvfb \
    x11vnc \
    fluxbox \
    # PostgreSQL client
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
COPY requirements/media-bot.txt requirements/media-bot.txt
RUN pip install --no-cache-dir -r requirements/media-bot.txt

# Install Playwright browser only (without system deps, we already installed them)
RUN playwright install chromium

# Copy shared code
COPY shared/ /app/shared/

# Copy media bot code
COPY media_bot/ /app/media_bot/
COPY envato_utils/ /app/envato_utils/
COPY freepik_utils/ /app/freepik_utils/
COPY motion_utils/ /app/motion_utils/

# Copy migrations
COPY migrations/ /app/migrations/
COPY alembic.ini /app/alembic.ini

# Copy scripts (for seeding, etc.)
COPY scripts/ /app/scripts/

# Setup Xvfb for headless Playwright
COPY docker/xvfb-run.sh /usr/local/bin/xvfb-run.sh
RUN chmod +x /usr/local/bin/xvfb-run.sh

# Environment
ENV PYTHONPATH=/app
ENV DISPLAY=:99
ENV PYTHONIOENCODING=utf-8

CMD ["/usr/local/bin/xvfb-run.sh", "python", "-m", "media_bot.main"]
