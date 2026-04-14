FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_HEADLESS=0 \
    DISPLAY=:99

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN python -m playwright install --with-deps chromium

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN chmod +x /app/entrypoint.sh

# tini (PID 1): forward SIGTERM → entrypoint.sh → exec python
# entrypoint.sh: dọn lock file cũ → start Xvfb → exec python main_play.py
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/entrypoint.sh"]
