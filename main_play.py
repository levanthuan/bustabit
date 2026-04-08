from batch_crawl_play import DbConfig, PlayCrawlConfig, run_play

import config_play as cfg


def main() -> None:
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
