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

# Playwright settings
PLAYWRIGHT_HEADLESS    = _env_int("PLAYWRIGHT_HEADLESS", 0) == 1
PLAYWRIGHT_TIMEOUT_MS  = _env_int("PLAYWRIGHT_TIMEOUT_MS", 60000)

# Chu kỳ poll JS queue (ms) – nên nhỏ để không miss game
POLL_INTERVAL_MS = _env_int("POLL_INTERVAL_MS", 500)

# Coi WS chết nếu không có game mới trong N giây → reload
WS_DEAD_THRESHOLD_S = _env_int("WS_DEAD_THRESHOLD_S", 60)

# Thời gian chạy tối đa (giây). Hết thời gian sẽ tự dừng toàn bộ tiến trình.
# Đặt 0 để chạy không giới hạn.
MAX_RUN_SECONDS = _env_int("MAX_RUN_SECONDS", 0) # 3600s = 1h

# Cookie Cloudflare nếu cần
CLOUDFLARE_COOKIE = _env("CLOUDFLARE_COOKIE", "")

# DB settings (MySQL)
DB_HOST     = _env("DB_HOST", "host.docker.internal")
DB_PORT     = _env_int("DB_PORT", 3306)
DB_USER     = _env("DB_USER", "root")
DB_PASSWORD = _env("DB_PASSWORD", "password")
DB_NAME     = _env("DB_NAME", "bustabit_db")
