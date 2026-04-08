from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
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
        # -------------------------------------------------------------------
        # Giải pháp 4: Headless New – gần giống headful hơn, ít bị detect hơn
        # -------------------------------------------------------------------
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ]
        if cfg.headless:
            # "new" headless mode (Chromium 112+): ít bị phát hiện hơn old
            launch_args.append("--headless=new")

        browser = p.chromium.launch(
            headless=cfg.headless,
            args=launch_args,
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
