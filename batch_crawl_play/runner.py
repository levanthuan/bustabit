from __future__ import annotations

import gc
from dataclasses import dataclass
from datetime import datetime

from .db import (
    DbConfig,
    connect_db,
    ensure_history_table,
    ensure_case_3_table,
    ensure_case_5_table,
    ensure_case_7_table,
    ensure_case_10_table,
)
from .models import GameHistory
from .repository import (
    upsert_history,
    upsert_case_3,
    upsert_case_5,
    upsert_case_7,
    upsert_case_10,
)
from .listener import ListenerConfig, listen_play


@dataclass(frozen=True)
class PlayCrawlConfig:
    domain: str
    headless: bool
    timeout_ms: int
    poll_interval_ms: int
    ws_dead_threshold_s: int
    max_run_seconds: int
    cloudflare_cookie: str
    db: DbConfig


def run_play(cfg: PlayCrawlConfig) -> None:
    print("[play_crawl] start")
    print(f"[play_crawl] domain={cfg.domain}")

    conn = connect_db(cfg.db)
    try:
        ensure_history_table(conn)
        ensure_case_3_table(conn)
        ensure_case_5_table(conn)
        ensure_case_7_table(conn)
        ensure_case_10_table(conn)
        print("[play_crawl] DB tables OK")
    except Exception as e:
        conn.close()
        raise RuntimeError(f"Không thể khởi tạo DB: {e}") from e

    def on_game(item: GameHistory) -> None:
        try:
            now = datetime.utcnow()
            upsert_history(conn, item, now=now)
            inserted = {
                "case_3":  upsert_case_3(conn, item, now=now),
                "case_5":  upsert_case_5(conn, item, now=now),
                "case_7":  upsert_case_7(conn, item, now=now),
                "case_10": upsert_case_10(conn, item, now=now),
            }
            conn.commit()
            cases = [t for t, v in inserted.items() if v]
            if cases:
                print(
                    f"[play_crawl] case_tables={cases} "
                    f"id={item.id} busted={item.busted}"
                )
        except Exception as e:
            conn.rollback()
            print(f"[play_crawl] db_error id={item.id} err={e}")

    listener_cfg = ListenerConfig(
        base_domain=cfg.domain,
        headless=cfg.headless,
        timeout_ms=cfg.timeout_ms,
        poll_interval_ms=cfg.poll_interval_ms,
        ws_dead_threshold_s=cfg.ws_dead_threshold_s,
        max_run_seconds=cfg.max_run_seconds,
        cloudflare_cookie=cfg.cloudflare_cookie,
    )

    try:
        listen_play(listener_cfg, on_game=on_game)
    except KeyboardInterrupt:
        print("\n[play_crawl] stopped by user")
    finally:
        conn.close()
        print("[play_crawl] DB connection closed")
        gc.collect()
