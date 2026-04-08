from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pymysql
from pymysql.connections import Connection


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def connect_db(cfg: DbConfig) -> Connection:
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _ensure_case_table(conn: Connection, table_name: str) -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{table_name}` (
      `id` int NOT NULL,
      `busted` int NOT NULL,
      `created_at` datetime NOT NULL,
      `updated_at` datetime NOT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def ensure_history_table(conn: Connection) -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS `history` (
      `id` int NOT NULL,
      `busted` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `created_at` datetime NOT NULL,
      `updated_at` datetime NOT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def ensure_case_3_table(conn: Connection) -> None:
    _ensure_case_table(conn, "case_3")


def ensure_case_5_table(conn: Connection) -> None:
    _ensure_case_table(conn, "case_5")


def ensure_case_7_table(conn: Connection) -> None:
    _ensure_case_table(conn, "case_7")


def ensure_case_10_table(conn: Connection) -> None:
    _ensure_case_table(conn, "case_10")
