from __future__ import annotations

import glob
import shutil
import signal
import sys

from batch_crawl import run_batch
from batch_crawl.db import DbConfig
from batch_crawl.runner import BatchCrawlConfig

import config


def _register_sigterm() -> None:
    """
    Python khi chạy là PID 1 trong container sẽ ignore SIGTERM theo mặc định
    của Linux (PID 1 không nhận signal từ kernel trừ SIGKILL).
    Đăng ký handler tường minh để Docker stop → Python exit cleanly.
    """
    def _handler(signum, frame):
        print("[main] received SIGTERM – exiting cleanly", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handler)


def _cleanup_playwright_tmp() -> None:
    """
    Xóa các thư mục tạm Playwright còn sót từ lần chạy trước.
    Docker --restart giữ nguyên filesystem container → các dir này tích lũy.
    """
    patterns = [
        "/tmp/playwright_chromium*",
        "/tmp/playwright_firefox*",
        "/tmp/.org.chromium*",
    ]
    removed = 0
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
            except Exception:
                pass
    if removed:
        print(f"[main] cleaned {removed} stale playwright tmp dir(s)", flush=True)


def main() -> None:
    _register_sigterm()
    _cleanup_playwright_tmp()

    cfg = BatchCrawlConfig(
        domain=config.DOMAIN,
        start_game_id=config.START_GAME_ID,
        batch_size=config.BATCH_SIZE,
        http_timeout_seconds=config.HTTP_TIMEOUT_SECONDS,
        cloudflare_cookie=config.CLOUDFLARE_COOKIE,
        debug_save_raw=getattr(config, "DEBUG_SAVE_RAW", False),
        use_playwright=getattr(config, "USE_PLAYWRIGHT", True),
        playwright_headless=getattr(config, "PLAYWRIGHT_HEADLESS", True),
        playwright_timeout_ms=getattr(config, "PLAYWRIGHT_TIMEOUT_MS", 60000),
        db=DbConfig(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
        ),
    )
    run_batch(cfg)


if __name__ == "__main__":
    main()
