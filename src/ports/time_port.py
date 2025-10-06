from __future__ import annotations

from typing import Protocol
from datetime import datetime, timezone


class TimePort(Protocol):
    def now(self) -> datetime: ...

    def to_timestamp_ms(self, dt: datetime) -> int: ...

    def from_timestamp_ms(self, ts: int) -> datetime: ...
