from __future__ import annotations

from datetime import datetime
from typing import Optional

from pymysql.connections import Connection

from .models import GameHistory


def upsert_history(conn: Connection, item: GameHistory, now: datetime) -> None:
    sql = """
    INSERT INTO `history` (`id`, `busted`, `hash`, `game_datetime`, `created_at`, `updated_at`)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      `busted` = VALUES(`busted`),
      `hash` = VALUES(`hash`),
      `updated_at` = VALUES(`updated_at`)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                item.id,
                item.busted,
                item.hash,
                item.game_datetime if item.game_datetime is not None else now,
                now,
                now,
            ),
        )


def _busted_int(busted: Optional[str]) -> Optional[int]:
    """'3.16' → 3, '4.14' → 4. Trả None nếu không parse được."""
    if busted is None:
        return None
    try:
        return int(float(busted))
    except (ValueError, TypeError):
        return None


def _upsert_case_table(
    conn: Connection,
    table_name: str,
    threshold: int,
    dead_threshold: int,
    item: GameHistory,
    now: datetime,
) -> bool:
    """
    Insert vào bảng case_X nếu busted >= threshold.
    Lưu phần nguyên của busted (3.16 → 3, 4.14 → 4).
    Tính count = ID hiện tại - ID gần nhất nhỏ hơn (hoặc 1 nếu chưa có bản ghi).
    Tính dead_flg = 1 nếu count >= dead_threshold.
    Trả về True nếu đã insert/update, False nếu bỏ qua.
    """
    busted_int = _busted_int(item.busted)
    if busted_int is None or busted_int < threshold:
        return False

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT MAX(id) AS prev_id FROM `{table_name}` WHERE id < %s",
            (item.id,),
        )
        row = cur.fetchone()
        prev_id = row["prev_id"] if row and row.get("prev_id") is not None else None

    count = (item.id - prev_id) if prev_id is not None else 1
    dead_flg = 1 if count >= dead_threshold else None

    sql = f"""
    INSERT INTO `{table_name}`
      (`id`, `busted`, `game_datetime`, `count`, `dead_flg`, `created_at`, `updated_at`)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      `busted`    = VALUES(`busted`),
      `count`     = VALUES(`count`),
      `dead_flg`  = VALUES(`dead_flg`),
      `updated_at`= VALUES(`updated_at`)
    """
    game_dt = item.game_datetime if item.game_datetime is not None else now
    with conn.cursor() as cur:
        cur.execute(sql, (item.id, busted_int, game_dt, count, dead_flg, now, now))
    return True


def upsert_case_3(conn: Connection, item: GameHistory, now: datetime) -> bool:
    return _upsert_case_table(conn, "case_3", 3, 8, item, now)


def upsert_case_5(conn: Connection, item: GameHistory, now: datetime) -> bool:
    return _upsert_case_table(conn, "case_5", 5, 16, item, now)


def upsert_case_7(conn: Connection, item: GameHistory, now: datetime) -> bool:
    return _upsert_case_table(conn, "case_7", 7, 25, item, now)


def upsert_case_10(conn: Connection, item: GameHistory, now: datetime) -> bool:
    return _upsert_case_table(conn, "case_10", 10, 36, item, now)
