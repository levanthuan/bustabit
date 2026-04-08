from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class GameHistory:
    id: int
    busted: Optional[str]
    hash: Optional[str]
    game_datetime: Optional[datetime]

