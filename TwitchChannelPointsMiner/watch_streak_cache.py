import threading
import time
from typing import Dict

from TwitchChannelPointsMiner.utils import dump_json, load_json


WATCH_STREAK_CACHE_TTL_SECONDS = 30 * 60


class WatchStreakCache:
    def __init__(self, data: Dict[str, Dict] | None = None):
        self._data: Dict[str, Dict] = data or {}
        self._lock = threading.Lock()
        self._dirty = False

    @classmethod
    def load_from_disk(cls, path: str) -> "WatchStreakCache":
        data = load_json(path, {})
        return cls(data if isinstance(data, dict) else {})

    def mark_streak_claimed(self, username: str, now: float | None = None) -> None:
        now = now or time.time()
        with self._lock:
            self._data[username] = {"last_streak": now}
            self._dirty = True

    def was_streak_claimed_recently(
        self, username: str, now: float | None = None, ttl_seconds: int = WATCH_STREAK_CACHE_TTL_SECONDS
    ) -> bool:
        now = now or time.time()
        with self._lock:
            entry = self._data.get(username)
            if not entry:
                return False
            last_streak = entry.get("last_streak", 0)
            if not isinstance(last_streak, (int, float)):
                return False
            return (now - last_streak) < ttl_seconds

    def save_to_disk_if_dirty(self, path: str) -> None:
        with self._lock:
            if not self._dirty:
                return
            dump_json(path, self._data)
            self._dirty = False
