from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from .models import GameHistory


def _try_parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if re.fullmatch(r"\d{10,13}", text):
            return _try_parse_datetime(int(text))
        try:
            dt = dtparser.parse(text)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None
    return None


def parse_game_page(html: str, game_id: int) -> GameHistory:
    """
    Parse theo cấu trúc DOM thực tế:
    - busted: .css-0 .cY-cx
    - hash: .css-0 input[name='gameHash']
    - datetime: .css-0 .chakra-text chứa chuỗi ngày giờ
    """
    soup = BeautifulSoup(html, "html.parser")

    # xác nhận block game đúng id nếu có
    game_title = soup.find(string=re.compile(r"Game\s*#\s*\d+", re.IGNORECASE))
    if game_title:
        m = re.search(r"Game\s*#\s*(\d+)", str(game_title), re.IGNORECASE)
        if m and int(m.group(1)) != game_id:
            return GameHistory(id=game_id, busted=None, hash=None, game_datetime=None)

    busted = None
    hash_value = None
    game_datetime = None

    busted_node = soup.select_one(".css-0 .cY-cx")
    if busted_node:
        busted = busted_node.get_text(strip=True) or None
    if busted is not None:
        lowered = busted.strip().lower()
        if lowered in {"...", "loading...", "loading"}:
            busted = None
        else:
            busted = busted.strip().rstrip("x").strip()

    hash_input = soup.select_one(".css-0 input[name='gameHash']")
    if hash_input:
        hash_value = (hash_input.get("value") or "").strip() or None
    if hash_value is not None:
        lowered = hash_value.strip().lower()
        if lowered in {"...", "loading...", "loading"}:
            hash_value = None
        elif not re.fullmatch(r"[a-fA-F0-9]{64}", hash_value):
            # Chỉ chấp nhận hash game chuẩn 64 ký tự hex
            hash_value = None

    # fallback hash từ link verifier
    if hash_value is None:
        verifier_link = soup.find("a", href=re.compile(r"verifier\?hash=.*game=\d+", re.IGNORECASE))
        if verifier_link and verifier_link.get("href"):
            vm = re.search(r"hash=([a-fA-F0-9]{32,128}).*game=(\d+)", verifier_link["href"])
            if vm and int(vm.group(2)) == game_id:
                hash_value = vm.group(1)

    for node in soup.select(".css-0 .chakra-text"):
        text = node.get_text(" ", strip=True)
        dt_match = re.search(
            r"(\d{1,2}/\d{1,2}/\d{4},\s*\d{1,2}:\d{2}\s*(?:AM|PM))",
            text,
            re.IGNORECASE,
        )
        if dt_match:
            game_datetime = _try_parse_datetime(dt_match.group(1))
            if game_datetime is not None:
                break

    return GameHistory(
        id=game_id,
        busted=busted,
        hash=hash_value,
        game_datetime=game_datetime,
    )

