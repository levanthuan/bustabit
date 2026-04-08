from batch_crawl import run_batch
from batch_crawl.db import DbConfig
from batch_crawl.runner import BatchCrawlConfig

import config


def main() -> None:
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

