"""
Playwright listener cho trang /play.

Cơ chế:
  - KHÔNG override WebSocket (tránh bị server detect)
  - Inject MutationObserver qua add_init_script
  - Fallback: nếu table chưa có, poll DOM trực tiếp
  - Python poll queue mỗi POLL_INTERVAL_MS ms → gọi on_game()
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .models import GameHistory

# -----------------------------------------------------------------------
# Stealth – KHÔNG override WebSocket để tránh server detect
# -----------------------------------------------------------------------
_STEALTH_INIT = """
() => {
  Object.defineProperty(navigator, 'webdriver',          { get: () => undefined });
  Object.defineProperty(navigator, 'plugins',            { get: () => [1,2,3,4,5] });
  Object.defineProperty(navigator, 'languages',          { get: () => ['en-US','en','vi'] });
  Object.defineProperty(navigator, 'hardwareConcurrency',{ get: () => 8 });
  Object.defineProperty(navigator, 'platform',           { get: () => 'MacIntel' });
  window.chrome = { runtime: {} };
  const orig = window.navigator.permissions.query;
  window.navigator.permissions.query = p =>
    p.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : orig(p);
}
"""

# -----------------------------------------------------------------------
# MutationObserver – inject TRƯỚC khi trang load
# -----------------------------------------------------------------------
_OBSERVER_INIT = """
() => {
  window.__newGames  = [];
  window.__seenIds   = new Set();
  window.__totalSeen = 0;
  window.__observing = false;
  window.__lastGameTs = Date.now();

  function _extract(tr) {
    try {
      const link   = tr.querySelector('td a[href^="/game/"]');
      const hashEl = tr.querySelector('td button p.chakra-text');
      if (!link || !hashEl) return null;
      const m = (link.getAttribute('href') || '').match(/\\/game\\/(\\d+)/);
      if (!m) return null;
      const gameId = parseInt(m[1], 10);
      const busted = link.textContent.trim().replace(/,/g,'').replace(/x$/i,'');
      const hash   = hashEl.textContent.trim();
      return (gameId && busted && hash) ? { game_id: gameId, busted, hash } : null;
    } catch(e) { return null; }
  }

  function _attach() {
    const tbody = document.querySelector('table.chakra-table tbody');
    if (!tbody || window.__observing) return false;

    tbody.querySelectorAll('tr.RHP-W').forEach(tr => {
      const d = _extract(tr);
      if (d) window.__seenIds.add(d.game_id);
    });
    console.log('[observer] attached, seeded', window.__seenIds.size, 'rows');

    new MutationObserver(muts => {
      for (const mut of muts) {
        for (const node of mut.addedNodes) {
          if (node.nodeType !== 1) continue;
          const rows = node.classList && node.classList.contains('RHP-W')
            ? [node]
            : Array.from(node.querySelectorAll ? node.querySelectorAll('tr.RHP-W') : []);
          for (const tr of rows) {
            const d = _extract(tr);
            if (!d || window.__seenIds.has(d.game_id)) continue;
            window.__seenIds.add(d.game_id);
            window.__newGames.push(d);
            window.__totalSeen++;
            window.__lastGameTs = Date.now();
            console.log('[observer] new game:', d.game_id, d.busted);
          }
        }
      }
    }).observe(tbody, { childList: true, subtree: true });

    window.__observing = true;
    return true;
  }

  // Retry mỗi 1s cho đến khi tbody xuất hiện (SPA render chậm)
  const iv = setInterval(() => { if (_attach()) clearInterval(iv); }, 1000);
  document.addEventListener('DOMContentLoaded', _attach);
}
"""

# Đọc trực tiếp DOM table (fallback khi observer miss)
_READ_TABLE_JS = """
() => {
  const rows = document.querySelectorAll('table.chakra-table tbody tr.RHP-W');
  const results = [];
  rows.forEach(tr => {
    const link   = tr.querySelector('td a[href^="/game/"]');
    const hashEl = tr.querySelector('td button p.chakra-text');
    if (!link || !hashEl) return;
    const m = (link.getAttribute('href') || '').match(/\\/game\\/(\\d+)/);
    if (!m) return;
    const gameId = parseInt(m[1], 10);
    const busted = link.textContent.trim().replace(/,/g,'').replace(/x$/i,'');
    const hash   = hashEl.textContent.trim();
    if (gameId && busted && hash) results.push({ game_id: gameId, busted, hash });
  });
  return results;
}
"""

_DRAIN_JS  = "() => (window.__newGames || []).splice(0)"
_STATUS_JS = """
() => ({
  observing:  !!(window.__observing),
  seeded:     window.__seenIds ? window.__seenIds.size : 0,
  total:      window.__totalSeen || 0,
  lastAgoMs:  Date.now() - (window.__lastGameTs || Date.now()),
  tableRows:  document.querySelectorAll('table.chakra-table tbody tr.RHP-W').length,
})
"""

# Chỉ block những domain không ảnh hưởng đến app
_BLOCKED = [
    "sentry.io",
    "ingest.sentry.io",
    "browser.sentry-cdn.com",
    "mt.bustabit.com",
    "google-analytics.com",
    "googletagmanager.com",
]


@dataclass(frozen=True)
class ListenerConfig:
    base_domain: str
    headless: bool
    timeout_ms: int
    poll_interval_ms: int
    ws_dead_threshold_s: int
    max_run_seconds: int
    cloudflare_cookie: str = ""


def _parse_cookie_header(s: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in s.split(";"):
        p = part.strip()
        if not p or "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip()
        if k:
            out[k] = v.strip()
    return out


def listen_play(cfg: ListenerConfig, on_game: Callable[[GameHistory], None]) -> None:
    play_url = f"{cfg.base_domain.rstrip('/')}/play"
    start_ts = time.time()

    try:
        from playwright_stealth import stealth_sync as _stealth
        _stealth_ok = True
    except ImportError:
        _stealth_ok = False

    with sync_playwright() as p:
        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ]
        if cfg.headless:
            args.append("--headless=new")

        browser: Browser = p.chromium.launch(headless=cfg.headless, args=args)
        context: BrowserContext = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="Asia/Ho_Chi_Minh",
            color_scheme="light",
        )
        context.add_init_script(_STEALTH_INIT)
        context.add_init_script(_OBSERVER_INIT)

        if cfg.cloudflare_cookie:
            host = urlparse(cfg.base_domain).hostname or "bustabit.com"
            kv = _parse_cookie_header(cfg.cloudflare_cookie)
            cookies = [
                {"name": k, "value": v, "domain": host, "path": "/"}
                for k, v in kv.items() if k
            ]
            if cookies:
                context.add_cookies(cookies)

        page: Page = context.new_page()
        if _stealth_ok:
            _stealth(page)

        # Chỉ block analytics, KHÔNG block các resource khác
        page.route(
            "**/*",
            lambda r: r.abort()
            if any(d in r.request.url for d in _BLOCKED)
            else r.continue_(),
        )

        # Log console browser để debug
        page.on("console", lambda msg: (
            print(f"  [browser] {msg.text}")
            if msg.type in ("log",) else None
        ))

        def _open_play() -> None:
            print(f"[play_crawl] opening {play_url} ...")
            page.goto(play_url, wait_until="domcontentloaded", timeout=cfg.timeout_ms)

            # Bước 1: đợi tab bar render rồi click vào tab "History"
            print("[play_crawl] waiting for History tab...")
            try:
                page.wait_for_selector(
                    ".chakra-tabs__tablist button",
                    timeout=20000,
                    state="attached",
                )
                # Click tab History (data-index="1" hoặc text "History")
                history_tab = page.query_selector(
                    ".chakra-tabs__tablist button[data-index='1']"
                )
                if not history_tab:
                    # Fallback: tìm theo text
                    history_tab = page.get_by_role("tab", name="History")
                if history_tab:
                    history_tab.click()
                    print("[play_crawl] clicked History tab ✓")
                else:
                    print("[play_crawl] warn: không tìm thấy tab History")
            except PlaywrightTimeoutError:
                print("[play_crawl] warn: tab bar chưa xuất hiện sau 20s")

            # Bước 2: đợi table xuất hiện sau khi click tab
            print("[play_crawl] waiting for table to render...")
            try:
                page.wait_for_selector(
                    "table.chakra-table tbody tr.RHP-W",
                    timeout=30000,
                    state="attached",
                )
                print("[play_crawl] table found ✓")
            except PlaywrightTimeoutError:
                print("[play_crawl] warn: table chưa có sau 30s")

            # Bước 2: đợi observer tự attach (interval trong JS)
            try:
                page.wait_for_function(
                    "() => !!(window.__observing)", timeout=10000
                )
            except PlaywrightTimeoutError:
                pass

            st = page.evaluate(_STATUS_JS)
            print(
                f"[play_crawl] status: observing={st['observing']} "
                f"seeded={st['seeded']} tableRows={st['tableRows']}"
            )
            print(f"[play_crawl] {'NO':>5}  {'GAME_ID':>12}  {'BUSTED':>12}  HASH")
            print("[play_crawl] " + "-" * 62)

        _open_play()

        poll_s    = cfg.poll_interval_ms / 1000.0
        dead_s    = cfg.ws_dead_threshold_s
        game_cnt  = 0
        seen_ids: set = set()

        while True:
            if cfg.max_run_seconds > 0:
                elapsed_s = time.time() - start_ts
                if elapsed_s >= cfg.max_run_seconds:
                    print(
                        "[play_crawl] reached MAX_RUN_SECONDS="
                        f"{cfg.max_run_seconds}s -> stopping process"
                    )
                    # Đóng chủ động để giải phóng tài nguyên sớm
                    try:
                        page.close()
                    except Exception:
                        pass
                    try:
                        context.close()
                    except Exception:
                        pass
                    try:
                        browser.close()
                    except Exception:
                        pass
                    break

            time.sleep(poll_s)

            # Kiểm tra tình trạng
            try:
                st = page.evaluate(_STATUS_JS)
            except Exception as e:
                print(f"[play_crawl] page err: {e} → reload")
                try:
                    _open_play()
                    seen_ids.clear()
                except Exception:
                    pass
                continue

            # Drain từ MutationObserver queue
            try:
                items: List[dict] = page.evaluate(_DRAIN_JS)
            except Exception:
                items = []

            # Fallback: nếu observer chưa chạy được, đọc table trực tiếp
            if not st["observing"] and st["tableRows"] > 0:
                try:
                    all_rows: List[dict] = page.evaluate(_READ_TABLE_JS)
                    items = [r for r in all_rows if r["game_id"] not in seen_ids]
                except Exception:
                    items = []

            # Luôn sort tăng dần theo game_id (cũ → mới) trước khi insert DB
            items = sorted(items, key=lambda r: r["game_id"])

            for item in items:
                gid      = item["game_id"]
                busted   = item["busted"]
                hash_val = item["hash"]

                if gid in seen_ids:
                    continue
                seen_ids.add(gid)

                if not re.fullmatch(r"[a-fA-F0-9]{64}", hash_val):
                    continue

                game_cnt += 1
                print(
                    f"[play_crawl] {game_cnt:>5}  {gid:>12}  "
                    f"{busted:>12}  {hash_val[:20]}..."
                )
                on_game(GameHistory(
                    id=gid,
                    busted=busted,
                    hash=hash_val,
                    game_datetime=None,
                ))

            # Auto-reload nếu WS chết quá lâu
            if st["lastAgoMs"] > dead_s * 1000 and game_cnt > 0:
                print(f"[play_crawl] im lặng {st['lastAgoMs']/1000:.0f}s → reload")
                _open_play()
                seen_ids.clear()
