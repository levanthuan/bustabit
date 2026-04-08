FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_HEADLESS=0 \
    DISPLAY=:99

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN python -m playwright install --with-deps chromium

# Cài Xvfb để chạy headed browser trong container (không cần màn hình thật)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

# Khởi động Xvfb (virtual display :99) rồi chạy crawler
# CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x800x24 -nolisten tcp & sleep 1 && python -m main"]

# Khởi động Xvfb (virtual display :99) rồi chạy play crawler
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x800x24 -nolisten tcp & sleep 1 && python main_play.py"]
