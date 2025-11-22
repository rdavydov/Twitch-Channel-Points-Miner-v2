import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from TwitchChannelPointsMiner.utils import dump_json


WATCH_STREAK_CACHE_TTL_SECONDS = 6 * 60 * 60

logger = logging.getLogger(__name__)


class WatchStreakCache:
    def __init__(self, data: Dict[str, Dict] | None = None):
        self._data: Dict[str, Dict] = data or {}
        self._lock = threading.Lock()
        self._dirty = False

    @classmethod
    def load_from_disk(cls, path: str) -> "WatchStreakCache":
        data: Dict[str, Dict] = {}
        if not os.path.isfile(path):
            logger.debug(
                "WatchStreakCache: watch streak cache not found at %s, starting empty",
                path,
            )
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                logger.warning(
                    "Failed to read watch streak cache from %s, starting empty: %s",
                    path,
                    exc,
                )
                data = {}

        if not isinstance(data, dict):
            logger.warning(
                "Invalid watch streak cache format in %s (expected object, got %s); starting empty",
                path,
                type(data).__name__,
            )
            data = {}

        cache = cls(data)
        logger.debug(
            "WatchStreakCache: loaded %d watch streak cache entries from %s",
            len(cache._data),
            path,
        )
        return cache

    def mark_streak_claimed(self, username: str, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._data[username] = {"last_streak_timestamp": now}
            self._dirty = True
        logger.debug(
            "WatchStreakCache: mark_streak_claimed(%s) at %s",
            username,
            datetime.fromtimestamp(now, tz=timezone.utc),
        )

    def last_streak_timestamp(self, username: str) -> Optional[float]:
        with self._lock:
            entry = self._data.get(username)
            if not entry:
                return None
            last_streak = entry.get("last_streak_timestamp")
            # Backwards compatibility with older key name
            if last_streak is None:
                last_streak = entry.get("last_streak")
            if not isinstance(last_streak, (int, float)):
                return None
            return float(last_streak)

    def was_streak_claimed_recently(
        self,
        username: str,
        now: Optional[float] = None,
        ttl_seconds: int = WATCH_STREAK_CACHE_TTL_SECONDS,
    ) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            entry = self._data.get(username)
            if not entry:
                return False
            last_streak = entry.get("last_streak_timestamp")
            if last_streak is None:
                last_streak = entry.get("last_streak")
            if not isinstance(last_streak, (int, float)):
                return False
            age = now - last_streak
            if age < 0:
                return False
            is_recent = age < ttl_seconds
        if is_recent:
            logger.debug(
                "WatchStreakCache: skipping STREAK for %s (last=%s, age=%.1fs, ttl=%ds)",
                username,
                datetime.fromtimestamp(last_streak, tz=timezone.utc),
                age,
                ttl_seconds,
            )
        return is_recent

    def save_to_disk_if_dirty(self, path: str) -> None:
        with self._lock:
            if not self._dirty:
                return
            dump_json(path, self._data)
            self._dirty = False
        logger.debug("WatchStreakCache: saved %d entries to %s", len(self._data), path)


def _self_check_watch_streak_cache():
    now = time.time()
    cache = WatchStreakCache()
    cache.mark_streak_claimed("test_user", now)
    assert cache.was_streak_claimed_recently(
        "test_user", now + 60, WATCH_STREAK_CACHE_TTL_SECONDS
    )
    assert not cache.was_streak_claimed_recently(
        "test_user", now + WATCH_STREAK_CACHE_TTL_SECONDS + 10, WATCH_STREAK_CACHE_TTL_SECONDS
    )
    print("Watch streak cache self-check passed.")


if __name__ == "__main__":
    _self_check_watch_streak_cache()
