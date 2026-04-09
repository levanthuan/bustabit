# Bustabit Crawler

Dự án Python crawl dữ liệu game từ [bustabit.com](https://bustabit.com), ghi vào MySQL. Gồm hai luồng: **crawl lịch sử theo ID** và **theo dõi realtime trên trang `/play`**.

## Yêu cầu

- Python 3.11+ (khuyến nghị)
- MySQL 8.x (hoặc tương thích InnoDB)
- Playwright + Chromium (cài qua `playwright install`)

## Cài đặt nhanh (máy local)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Cơ sở dữ liệu

1. Tạo database và chạy schema trong `db/ddl.sql`.
2. (Tùy chọn) Áp dụng trigger trong `db/triggers/` cho các bảng `case_*` nếu bạn dùng logic `count` / `dead_flg` tự động.
3. Nếu cột `count` đang là `smallint` và gặp lỗi *Out of range*, chạy:

```sql
ALTER TABLE `case_3`  MODIFY COLUMN `count` int DEFAULT NULL;
ALTER TABLE `case_5`  MODIFY COLUMN `count` int DEFAULT NULL;
ALTER TABLE `case_7`  MODIFY COLUMN `count` int DEFAULT NULL;
ALTER TABLE `case_10` MODIFY COLUMN `count` int DEFAULT NULL;
```

Các module crawl có thể tự `CREATE TABLE IF NOT EXISTS` cho bảng cơ bản; schema đầy đủ (trigger, kiểu cột) nên đồng bộ với `db/ddl.sql`.

## Hai module

| Module | Entry | Mục đích |
|--------|--------|----------|
| **batch_crawl** | `python main.py` | Duyệt từng game `/game/{id}` (Playwright), bù lịch sử từ cũ lên mới. |
| **batch_crawl_play** | `python main_play.py` | Mở `/play`, tab History, lắng nghe cập nhật; ghi game mới gần realtime. |

Cả hai dùng **upsert** (`ON DUPLICATE KEY UPDATE`) trên `id` → có thể chạy song song; vùng trùng ID không gây lỗi, chỉ cập nhật bản ghi.

**Gợi ý vận hành:** bật `batch_crawl_play` trước để không lỡ game mới; chạy `batch_crawl` để lấp lịch sử đến khi `MAX(id)` trong DB gần với game hiện tại, sau đó có thể chỉ giữ module realtime.

## Biến môi trường

### Crawl lịch sử (`config.py` / `main.py`)

| Biến | Mô tả | Mặc định |
|------|--------|----------|
| `BUSTABIT_DOMAIN` | URL site, không slash cuối | `https://bustabit.com` |
| `START_GAME_ID` | ID bắt đầu nếu `history` rỗng | `12900000` |
| `BATCH_SIZE` | Số game mỗi lần chạy | `5000` |
| `CLOUDFLARE_COOKIE` | Cookie trình duyệt (vd. `cf_clearance`) nếu bị chặn | rỗng |
| `USE_PLAYWRIGHT` | `1` bật Playwright | `1` |
| `PLAYWRIGHT_HEADLESS` | `1` headless | `0` |
| `PLAYWRIGHT_TIMEOUT_MS` | Timeout mỗi thao tác (ms) | `60000` |
| `DEBUG_SAVE_RAW` | `1` lưu HTML debug | `0` |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Kết nối MySQL | `host.docker.internal`, `3306`, `root`, `password`, `bustabit_db` |

### Crawl `/play` (`config_play.py` / `main_play.py`)

| Biến | Mô tả | Mặc định |
|------|--------|----------|
| `BUSTABIT_DOMAIN` | Giống trên | `https://bustabit.com` |
| `PLAYWRIGHT_HEADLESS` | Headless | `0` |
| `PLAYWRIGHT_TIMEOUT_MS` | Timeout (ms) | `60000` |
| `POLL_INTERVAL_MS` | Chu kỳ poll hàng đợi game (ms) | `500` |
| `WS_DEAD_THRESHOLD_S` | Không có game mới trong N giây → coi WS chết, reload | `60` |
| `MAX_RUN_SECONDS` | Giới hạn thời gian chạy; `0` = không giới hạn | `3600` |
| `CLOUDFLARE_COOKIE` | Giống trên | rỗng |
| `DB_*` | Giống crawl lịch sử | như bảng trên |

## Chạy thủ công

```bash
# Lịch sử theo ID
python3 main.py

# Realtime /play
python3 main_play.py
```

## Docker

Image cài Playwright Chromium, Xvfb (display ảo) và mặc định chạy **`main_play.py`** (xem `Dockerfile`).

```bash
docker build -t bustabit-crawler .
docker run --rm bustabit-crawler
```

Để chạy crawl lịch sử trong container, đổi `CMD` trong `Dockerfile` thành lệnh gọi `python main.py` (hoặc override `docker run ... python main.py`).

## Cấu trúc thư mục (chính)

```
batch_crawl/          # Crawl /game/{id}, parser HTML trang game
batch_crawl_play/     # Crawl /play, listener + ghi DB
config.py             # Cấu hình main.py
config_play.py        # Cấu hình main_play.py
db/ddl.sql            # Schema MySQL
db/triggers/          # Trigger case_3 / 5 / 7 / 10
main.py               # Entry crawl lịch sử
main_play.py          # Entry crawl /play
```

## Lưu ý

- Site có thể dùng Cloudflare; khi gặp challenge, cần cookie hợp lệ (`CLOUDFLARE_COOKIE`).
- Playwright headless đôi khi bị phát hiện; trong Docker thường dùng headed + Xvfb (`PLAYWRIGHT_HEADLESS=0`).
- Crawl hàng loạt dễ bị giới hạn tốc độ; nên điều chỉnh `BATCH_SIZE` và tần suất chạy cho phù hợp.

## Giấy phép

Dự án phục vụ mục đích cá nhân / nghiên cứu. Tuân thủ điều khoản sử dụng của bustabit và pháp luật địa phương khi crawl và lưu trữ dữ liệu.
