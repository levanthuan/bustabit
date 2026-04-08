import os


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None or v == "" else v


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return int(v)


# Domain site bustabit (không kèm slash cuối)
DOMAIN = _env("BUSTABIT_DOMAIN", "https://bustabit.com")

# Nếu bảng history chưa có bản ghi nào, bắt đầu crawl từ ID này
START_GAME_ID = _env_int("START_GAME_ID", 12900000) # 12000001 (27/7/2025), 12600001(28/12/2025), 12900000(15/03/2026)

# Mỗi lần chạy crawl bao nhiêu URL
BATCH_SIZE = _env_int("BATCH_SIZE", 5000)

# Timeout HTTP (giây)
HTTP_TIMEOUT_SECONDS = _env_int("HTTP_TIMEOUT_SECONDS", 30)

# Bật debug để lưu raw HTML/JSON khi parse ra rỗng
DEBUG_SAVE_RAW = _env_int("DEBUG_SAVE_RAW", 0) == 1

# Dùng Playwright để crawl (khuyến nghị cho site có JS/Cloudflare)
USE_PLAYWRIGHT = _env_int("USE_PLAYWRIGHT", 1) == 1
PLAYWRIGHT_HEADLESS = _env_int("PLAYWRIGHT_HEADLESS", 0) == 1
PLAYWRIGHT_TIMEOUT_MS = _env_int("PLAYWRIGHT_TIMEOUT_MS", 60000)

# Nếu site bị Cloudflare chặn, có thể cần cookie `cf_clearance` lấy từ trình duyệt.
# Format: "cf_clearance=...; __cf_bm=...; ..."
CLOUDFLARE_COOKIE = _env("CLOUDFLARE_COOKIE", "")

# DB settings (MySQL)
DB_HOST = _env("DB_HOST", "host.docker.internal")
DB_PORT = _env_int("DB_PORT", 3306)
DB_USER = _env("DB_USER", "root")
DB_PASSWORD = _env("DB_PASSWORD", "password")
DB_NAME = _env("DB_NAME", "bustabit_db")

