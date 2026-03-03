FROM python:3.11-slim

# Системные зависимости для Chrome
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libxss1 \
    libasound2 \
    libgbm1 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxrandr2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    curl \
    wget \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Установка Google Chrome (нужен для nodriver)
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    rm -rf /var/lib/apt/lists/*

# Установка Python-зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка только Chromium (для остальных сервисов — Envato, Motion)
RUN python -m playwright install chromium

# Копируем весь проект
COPY . /app/

# Команда запуска
CMD ["python", "main.py"]
