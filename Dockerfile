FROM python:3.11-slim

# Установим минимально необходимые системные зависимости для Chromium и Xvfb
RUN apt-get update && apt-get install -y \
    xvfb \
    libnss3 \
    libatk-bridge2.0-0 \
    libxss1 \
    libasound2 \
    libgbm1 \
    libgtk-3-0 \
    libx11-xcb1 \
    libnotify4 \
    curl \
    wget \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Установка Python-зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка только Chromium и его зависимостей
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# Копируем весь проект
COPY . /app/

# Команда запуска
CMD ["python", "main.py"]
