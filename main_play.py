from __future__ import annotations

import glob
import shutil
import signal
import sys

from batch_crawl_play import DbConfig, PlayCrawlConfig, run_play

import config_play as cfg


def _register_sigterm() -> None:
    """
    Python khi chạy là PID 1 trong container sẽ ignore SIGTERM theo mặc định
    của Linux (PID 1 không nhận signal từ kernel trừ SIGKILL).
    Đăng ký handler tường minh để Docker stop → Python exit cleanly.
    """
    def _handler(signum, frame):
        print("[main_play] received SIGTERM – exiting cleanly", flush=True)
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
        print(f"[main_play] cleaned {removed} stale playwright tmp dir(s)", flush=True)


def main() -> None:
    _register_sigterm()
    _cleanup_playwright_tmp()

    play_cfg = PlayCrawlConfig(
        domain=cfg.DOMAIN,
        headless=cfg.PLAYWRIGHT_HEADLESS,
        timeout_ms=cfg.PLAYWRIGHT_TIMEOUT_MS,
        poll_interval_ms=cfg.POLL_INTERVAL_MS,
        ws_dead_threshold_s=cfg.WS_DEAD_THRESHOLD_S,
        max_run_seconds=cfg.MAX_RUN_SECONDS,
        cloudflare_cookie=cfg.CLOUDFLARE_COOKIE,
        db=DbConfig(
            host=cfg.DB_HOST,
            port=cfg.DB_PORT,
            user=cfg.DB_USER,
            password=cfg.DB_PASSWORD,
            database=cfg.DB_NAME,
        ),
    )
    run_play(play_cfg)


if __name__ == "__main__":
    main()
