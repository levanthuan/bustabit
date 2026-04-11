from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from .db import (
    DbConfig,
    connect_db,
    ensure_case_3_table,
    ensure_case_5_table,
    ensure_case_7_table,
    ensure_case_10_table,
    ensure_history_table,
    get_max_history_id,
)
from .models import GameHistory
from .parser import parse_game_page
from .playwright_fetcher import FetchError, PlaywrightFetchConfig, fetch_game_html_sequence
from .repository import upsert_case_3, upsert_case_5, upsert_case_7, upsert_case_10, upsert_history


@dataclass(frozen=True)
class BatchCrawlConfig:
    domain: str
    start_game_id: int
    batch_size: int
    http_timeout_seconds: int  # giữ tương thích main.py, không dùng trong Playwright-only
    cloudflare_cookie: str
    db: DbConfig
    debug_save_raw: bool = False
    use_playwright: bool = True
    playwright_headless: bool = True
    playwright_timeout_ms: int = 60000


def _resolve_start_id(max_id: int | None, start_game_id: int) -> int:
    return start_game_id if max_id is None else max_id + 1


def run_batch(cfg: BatchCrawlConfig) -> None:
    print("[batch_crawl] start")
    print(f"[batch_crawl] domain={cfg.domain} batch_size={cfg.batch_size}")

    conn = connect_db(cfg.db)
    try:
        ensure_history_table(conn)
        ensure_case_3_table(conn)
        ensure_case_5_table(conn)
        ensure_case_7_table(conn)
        ensure_case_10_table(conn)
        max_id = get_max_history_id(conn)
        start_id = _resolve_start_id(max_id, cfg.start_game_id)
        print(f"[batch_crawl] max_id_in_db={max_id} -> start_id={start_id} batch_size={cfg.batch_size}")

        fetch_cfg = PlaywrightFetchConfig(
            base_domain=cfg.domain,
            timeout_ms=cfg.playwright_timeout_ms,
            headless=cfg.playwright_headless,
            cloudflare_cookie=cfg.cloudflare_cookie,
        )

        ok = 0
        failed: List[Tuple[int, str]] = []

        try:
            for game_id, html in fetch_game_html_sequence(fetch_cfg, start_id, cfg.batch_size):
                try:
                    if cfg.debug_save_raw:
                        out_dir = Path("/tmp/batch_crawl_debug")
                        out_dir.mkdir(parents=True, exist_ok=True)
                        (out_dir / f"game_{game_id}.html").write_text(
                            html, encoding="utf-8", errors="ignore"
                        )

                    item: GameHistory = parse_game_page(html, game_id)

                    if item.busted is None and item.hash is None and item.game_datetime is None:
                        failed.append((game_id, "parse_empty"))
                        print(f"[batch_crawl] warn id={game_id} parse_ra_rong")
                        continue

                    print(
                        "[batch_crawl] crawled "
                        f"id={item.id} "
                        f"busted={item.busted} "
                        f"hash={item.hash} "
                        f"game_datetime={item.game_datetime}"
                    )

                    now = datetime.utcnow()
                    upsert_history(conn, item, now=now)
                    inserted: dict = {
                        "case_3":  upsert_case_3(conn, item, now=now),
                        "case_5":  upsert_case_5(conn, item, now=now),
                        "case_7":  upsert_case_7(conn, item, now=now),
                        "case_10": upsert_case_10(conn, item, now=now),
                    }
                    conn.commit()
                    ok += 1
                    cases = [t for t, v in inserted.items() if v]
                    if cases:
                        print(f"[batch_crawl] case_tables={cases} id={item.id} busted={item.busted}")
                    if ok % 200 == 0:
                        print(f"[batch_crawl] progress ok={ok}/{cfg.batch_size} last_id={game_id}")
                except Exception as e:
                    conn.rollback()
                    failed.append((game_id, f"{type(e).__name__}: {e}"))
                    print(f"[batch_crawl] parse_or_db_failed id={game_id} err={type(e).__name__}: {e}")

        except FetchError as e:
            print(f"[batch_crawl] fatal fetch error: {e}")
            failed.append((-1, str(e)))

        print(f"[batch_crawl] done ok={ok} failed={len(failed)}")
        if failed:
            print("[batch_crawl] failed_ids (first 10):")
            for gid, err in failed[:10]:
                print(f"  - id={gid} err={err}")
    finally:
        conn.close()

