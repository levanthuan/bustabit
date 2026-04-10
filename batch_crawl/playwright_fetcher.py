from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Generator, Tuple
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlaywrightFetchConfig:
    base_domain: str
    timeout_ms: int
    headless: bool
    cloudflare_cookie: str = ""


def _parse_cookie_header(cookie_header: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in cookie_header.split(";"):
        p = part.strip()
        if not p or "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


def _build_game_url(base_domain: str, game_id: int) -> str:
    return f"{base_domain.rstrip('/')}/game/{game_id}"


def _looks_like_cloudflare_block(html: str) -> bool:
    h = (html or "").lower()
    return (
        "just a moment" in h
        or "cf-chl" in h
        or ("cloudflare" in h and "attention required" in h)
        or "checking your browser" in h
    )


def _looks_like_lost_connection(html: str) -> bool:
    return "lost connection to server" in (html or "").lower()


# -----------------------------------------------------------------------
# Giải pháp 1: Playwright Stealth – patch toàn bộ fingerprint headless
# -----------------------------------------------------------------------
_STEALTH_INIT_SCRIPT = """
() => {
  // navigator.webdriver
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

  // navigator.plugins – headless thường rỗng, set giả 5 plugin
  Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

  // navigator.languages
  Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'vi'] });

  // navigator.platform
  Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });

  // navigator.hardwareConcurrency
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

  // navigator.deviceMemory
  Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

  // window.chrome – headless thiếu object này
  window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
  };

  // Permissions API – headless trả 'denied' ngay
  const originalQuery = window.navigator.permissions.query;
  window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters);

  // WebGL vendor / renderer
  const getParam = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParam.call(this, parameter);
  };

  // outerWidth / outerHeight – headless thường trả 0
  if (window.outerWidth === 0) {
    Object.defineProperty(window, 'outerWidth',  { get: () => window.innerWidth });
    Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight });
  }
}
"""

# -----------------------------------------------------------------------
# Giải pháp 2: User-Agent của người dùng thật (Chrome 122 macOS)
# -----------------------------------------------------------------------
_REAL_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# -----------------------------------------------------------------------
# Giải pháp 3: Tham số Context bổ sung giống trình duyệt thật
# -----------------------------------------------------------------------
_CONTEXT_EXTRAS: dict = {
    "locale": "en-US",
    "timezone_id": "Asia/Ho_Chi_Minh",
    "color_scheme": "light",
    "device_scale_factor": 2.0,
    "has_touch": False,
    "java_script_enabled": True,
    "accept_downloads": False,
    "extra_http_headers": {
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Cache-Control":   "no-cache",
        "Pragma":          "no-cache",
    },
}

# -----------------------------------------------------------------------
# JS check dữ liệu thật đã render (không còn placeholder)
# -----------------------------------------------------------------------
_WAIT_DATA_READY_JS = """
() => {
  const hashInput  = document.querySelector("input[name='gameHash']");
  const bustedNode = document.querySelector(".css-0 .cY-cx");
  const bodyText   = (document.body?.innerText || "").toLowerCase();
  const hashVal    = (hashInput?.value || "").trim().toLowerCase();
  const bustedVal  = (bustedNode?.textContent || "").trim().toLowerCase();
  const PLACEHOLDERS = ["", "...", "loading...", "loading"];
  const hashReady   = !PLACEHOLDERS.includes(hashVal);
  const bustedReady = !PLACEHOLDERS.includes(bustedVal);
  const noLostConn  = !bodyText.includes("lost connection to server");
  return hashReady && bustedReady && noLostConn;
}
"""


def fetch_game_html(cfg: PlaywrightFetchConfig, game_id: int) -> str:
    url = _build_game_url(cfg.base_domain, game_id)
    parsed = urlparse(cfg.base_domain)
    domain_host = parsed.hostname or "bustabit.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=cfg.headless,
            args=_build_launch_args(cfg.headless),
        )

        context = browser.new_context(
            user_agent=_REAL_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            **_CONTEXT_EXTRAS,
        )

        # Inject stealth script (Giải pháp 1)
        context.add_init_script(_STEALTH_INIT_SCRIPT)

        # Thêm cookie Cloudflare nếu có
        if cfg.cloudflare_cookie:
            kv = _parse_cookie_header(cfg.cloudflare_cookie)
            cookies = [
                {"name": k, "value": v, "domain": domain_host, "path": "/"}
                for k, v in kv.items()
                if k
            ]
            if cookies:
                context.add_cookies(cookies)

        page = context.new_page()
        # Chặn image/media/font trước khi download – không download thì không ghi cache
        page.route("**/*", _block_non_essential_resources)

        # Dùng playwright-stealth library nếu cài được (mạnh hơn script thủ công)
        if _STEALTH_AVAILABLE:
            stealth_sync(page)

        try:
            wait_ms = min(max(cfg.timeout_ms // 2, 5000), 30000)
            html = ""

            for attempt in range(3):
                try:
                    if attempt == 0:
                        page.goto(url, wait_until="domcontentloaded", timeout=cfg.timeout_ms)
                    else:
                        print(f"[playwright] retry #{attempt} game_id={game_id}")
                        page.reload(wait_until="domcontentloaded", timeout=cfg.timeout_ms)

                    # Chờ selector xuất hiện
                    page.wait_for_selector(
                        "input[name='gameHash']", timeout=wait_ms, state="attached"
                    )
                    # Chờ dữ liệu thật (không còn placeholder)
                    page.wait_for_function(_WAIT_DATA_READY_JS, timeout=wait_ms)
                    page.wait_for_timeout(800)
                    html = page.content() or ""
                    if not _looks_like_lost_connection(html):
                        break
                    # Lost connection → reload thêm lần nữa
                    continue

                except PlaywrightTimeoutError:
                    html = page.content() or ""
                    if _looks_like_cloudflare_block(html):
                        raise FetchError(
                            f"Bị Cloudflare challenge khi tải {url}. "
                            f"Hãy set CLOUDFLARE_COOKIE hợp lệ (cf_clearance)."
                        )
                    if attempt == 2:
                        break
                    continue

            if not html:
                html = page.content() or ""

        except FetchError:
            raise
        except PlaywrightTimeoutError:
            raise FetchError(f"Playwright timeout khi tải {url}")
        finally:
            context.close()
            browser.close()

    if _looks_like_cloudflare_block(html):
        raise FetchError(
            f"Bị Cloudflare challenge khi tải {url}. "
            f"Hãy set CLOUDFLARE_COOKIE hợp lệ (cf_clearance)."
        )
    if _looks_like_lost_connection(html):
        raise FetchError(f"Trang game bị 'Lost Connection to server' khi tải {url}.")
    return html


# -----------------------------------------------------------------------
# Launch args dùng chung – giảm disk write I/O từ Chromium cache
# -----------------------------------------------------------------------
def _build_launch_args(headless: bool) -> list:
    args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        # Giới hạn disk cache tại 64 MB thay vì vô hạn.
        # Không tắt hoàn toàn vì JS/CSS vẫn cần cache để SPA load nhanh.
        "--disk-cache-size=67108864",
        "--media-cache-size=1",
        # Tắt GPU hoàn toàn cho headless – loại bỏ GPU shader cache write
        # (chiếm vài trăm MB mỗi session, không cần thiết cho data crawl).
        "--disable-gpu",
        "--disable-software-rasterizer",
    ]
    if headless:
        args.append("--headless=new")
    return args


# -----------------------------------------------------------------------
# Route handler: chặn resource không cần thiết trước khi download.
# Không download → không ghi cache → giảm ~60-70% disk write.
# Chỉ chặn image/media/font, giữ nguyên JS/CSS/XHR/fetch/websocket.
# -----------------------------------------------------------------------
_BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}


def _block_non_essential_resources(route) -> None:
    if route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
        route.abort()
    else:
        route.continue_()


# -----------------------------------------------------------------------
# Selector nút Next trên trang game bustabit
# -----------------------------------------------------------------------
_NEXT_BUTTON_SELECTOR = "a.chakra-button:has-text('Next')"


def fetch_game_html_sequence(
    cfg: PlaywrightFetchConfig,
    start_game_id: int,
    batch_size: int,
) -> Generator[Tuple[int, str], None, None]:
    """
    Generator mở 1 browser duy nhất, navigate đến start_game_id, sau đó click
    nút "Next" liên tiếp thay vì reload từng page mới.

    Yields: (game_id, html) cho mỗi game theo thứ tự.
    Dừng khi:
      - Không còn nút "Next" trên trang
      - Đã yield đủ batch_size lần
      - Gặp lỗi nghiêm trọng (Cloudflare, timeout) → raise FetchError
    """
    parsed = urlparse(cfg.base_domain)
    domain_host = parsed.hostname or "bustabit.com"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.headless, args=_build_launch_args(cfg.headless))
        context = browser.new_context(
            user_agent=_REAL_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            **_CONTEXT_EXTRAS,
        )
        context.add_init_script(_STEALTH_INIT_SCRIPT)

        if cfg.cloudflare_cookie:
            kv = _parse_cookie_header(cfg.cloudflare_cookie)
            cookies = [
                {"name": k, "value": v, "domain": domain_host, "path": "/"}
                for k, v in kv.items()
                if k
            ]
            if cookies:
                context.add_cookies(cookies)

        page = context.new_page()
        # Chặn image/media/font trước khi download – không download thì không ghi cache
        page.route("**/*", _block_non_essential_resources)
        if _STEALTH_AVAILABLE:
            stealth_sync(page)

        try:
            start_url = _build_game_url(cfg.base_domain, start_game_id)
            wait_ms = min(max(cfg.timeout_ms // 2, 5000), 30000)

            # --- Navigate đến trang đầu tiên ---
            page.goto(start_url, wait_until="domcontentloaded", timeout=cfg.timeout_ms)
            page.wait_for_selector(
                "input[name='gameHash']", timeout=wait_ms, state="attached"
            )
            page.wait_for_function(_WAIT_DATA_READY_JS, timeout=wait_ms)
            page.wait_for_timeout(800)

            count = 0
            while count <= batch_size:
                # Lấy game_id từ URL hiện tại (ví dụ: https://bustabit.com/game/12993561)
                current_url = page.url
                m = re.search(r"/game/(\d+)", current_url)
                if not m:
                    print(f"[playwright] không parse được game_id từ URL={current_url}, dừng.")
                    break
                game_id = int(m.group(1))

                html = page.content() or ""

                if _looks_like_cloudflare_block(html):
                    raise FetchError(
                        f"Bị Cloudflare challenge tại game_id={game_id}. "
                        "Hãy set CLOUDFLARE_COOKIE hợp lệ (cf_clearance)."
                    )
                if _looks_like_lost_connection(html):
                    raise FetchError(
                        f"Trang game bị 'Lost Connection to server' tại game_id={game_id}."
                    )

                yield game_id, html
                count += 1

                if count >= batch_size:
                    break

                # --- Tìm nút Next ---
                next_btn = page.query_selector(_NEXT_BUTTON_SELECTOR)
                if next_btn is None:
                    print(
                        f"[playwright] không tìm thấy nút Next tại game_id={game_id} "
                        f"(đã crawl {count}/{batch_size}), dừng."
                    )
                    break

                # Chụp hash hiện tại TRƯỚC khi click để detect thay đổi sau khi navigate.
                # Đây là fix cho race condition: SPA đổi URL trước nhưng DOM render sau,
                # khiến _WAIT_DATA_READY_JS pass ngay với data cũ của game trước.
                prev_hash = (
                    page.eval_on_selector(
                        "input[name='gameHash']", "el => el.value"
                    )
                    or ""
                ).strip().lower()

                # --- Click Next và chờ trang mới load ---
                try:
                    with page.expect_navigation(
                        wait_until="domcontentloaded", timeout=cfg.timeout_ms
                    ):
                        next_btn.click()

                    page.wait_for_selector(
                        "input[name='gameHash']", timeout=wait_ms, state="attached"
                    )

                    # Chờ data thật ĐÃ THAY ĐỔI sang game mới (không chỉ non-placeholder).
                    # Inject prev_hash vào JS để so sánh, tránh yield html của game cũ
                    # khi URL đã đổi nhưng DOM chưa re-render xong.
                    escaped_prev_hash = prev_hash.replace("'", "\\'")
                    wait_changed_js = f"""
() => {{
  const hashInput  = document.querySelector("input[name='gameHash']");
  const bustedNode = document.querySelector(".css-0 .cY-cx");
  const bodyText   = (document.body?.innerText || "").toLowerCase();
  const hashVal    = (hashInput?.value || "").trim().toLowerCase();
  const bustedVal  = (bustedNode?.textContent || "").trim().toLowerCase();
  const PLACEHOLDERS = ["", "...", "loading...", "loading"];
  const hashReady   = !PLACEHOLDERS.includes(hashVal);
  const bustedReady = !PLACEHOLDERS.includes(bustedVal);
  const noLostConn  = !bodyText.includes("lost connection to server");
  const hashChanged = hashVal !== '{escaped_prev_hash}';
  return hashReady && bustedReady && noLostConn && hashChanged;
}}
"""
                    page.wait_for_function(wait_changed_js, timeout=wait_ms)
                    # page.wait_for_timeout(500)

                except PlaywrightTimeoutError:
                    html_after = page.content() or ""
                    if _looks_like_cloudflare_block(html_after):
                        raise FetchError(
                            "Bị Cloudflare challenge sau khi click Next "
                            f"từ game_id={game_id}."
                        )
                    print(
                        f"[playwright] timeout sau khi click Next từ game_id={game_id}, dừng."
                    )
                    break

        except FetchError:
            raise
        except PlaywrightTimeoutError as exc:
            raise FetchError(f"Playwright timeout không mong đợi: {exc}") from exc
        finally:
            context.close()
            browser.close()
