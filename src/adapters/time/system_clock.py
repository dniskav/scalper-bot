from __future__ import annotations

from datetime import datetime, timezone
from ports.time_port import TimePort


class SystemClock(TimePort):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def to_timestamp_ms(self, dt: datetime) -> int:
        return int(dt.timestamp() * 1000)

    def from_timestamp_ms(self, ts: int) -> datetime:
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
