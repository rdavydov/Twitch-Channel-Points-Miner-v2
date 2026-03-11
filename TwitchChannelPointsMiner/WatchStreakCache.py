import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from TwitchChannelPointsMiner.utils import dump_json

logger = logging.getLogger(__name__)

WATCH_STREAK_CACHE_VERSION = 4
MIN_OFFLINE_FOR_NEW_STREAK = 30 * 60  # 30 minutes
MAX_STREAK_ATTEMPTS_PER_BROADCAST = 2
STALE_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # drop ended sessions after a week


@dataclass
class WatchStreakSession:
    account_name: str
    streamer_login: str
    broadcast_id: str
    started_at: float
    attempts: int = 0
    claimed: bool = False
    last_attempt_at: float | None = None
    ended_at: float | None = None

    def key(self) -> str:
        return f"{self.account_name}:{self.streamer_login}:{self.broadcast_id}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "account_name": self.account_name,
            "streamer_login": self.streamer_login,
            "broadcast_id": self.broadcast_id,
            "started_at": self.started_at,
            "attempts": self.attempts,
            "claimed": self.claimed,
            "last_attempt_at": self.last_attempt_at,
            "ended_at": self.ended_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "WatchStreakSession":
        return cls(
            account_name=str(data.get("account_name", "")),
            streamer_login=str(data.get("streamer_login", "")),
            broadcast_id=str(data.get("broadcast_id", "")),
            started_at=float(data.get("started_at", 0) or 0),
            attempts=int(data.get("attempts", 0) or 0),
            claimed=bool(data.get("claimed", False)),
            last_attempt_at=(
                float(data["last_attempt_at"])
                if data.get("last_attempt_at") not in [None, ""]
                else None
            ),
            ended_at=(
                float(data["ended_at"]) if data.get("ended_at") not in [None, ""] else None
            ),
        )


@dataclass
class StreamerPresence:
    last_broadcast_id: str | None = None
    previous_broadcast_id: str | None = None
    last_online_at: float | None = None
    last_offline_at: float | None = None
    seen_online: bool = False


@dataclass
class StreamerWatchStreakStatus:
    account_name: str
    streamer_login: str
    watch_streak_detected: bool = False
    watch_streak_days: int | None = None
    last_stream_started_at: float | None = None
    is_online: bool = False
    broadcast_id: str | None = None
    checked_at: float | None = None

    def key(self) -> str:
        return f"{self.account_name}:{self.streamer_login}"

    def to_dict(self) -> Dict[str, object]:
        return {
            "account_name": self.account_name,
            "streamer_login": self.streamer_login,
            "watch_streak_detected": self.watch_streak_detected,
            "watch_streak_days": self.watch_streak_days,
            "last_stream_started_at": self.last_stream_started_at,
            "is_online": self.is_online,
            "broadcast_id": self.broadcast_id,
            "checked_at": self.checked_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "StreamerWatchStreakStatus":
        return cls(
            account_name=str(data.get("account_name", "")),
            streamer_login=str(data.get("streamer_login", "")),
            watch_streak_detected=bool(data.get("watch_streak_detected", False)),
            watch_streak_days=(
                max(0, int(data.get("watch_streak_days")))
                if data.get("watch_streak_days") not in [None, ""]
                else None
            ),
            last_stream_started_at=(
                float(data["last_stream_started_at"])
                if data.get("last_stream_started_at") not in [None, ""]
                else None
            ),
            is_online=bool(data.get("is_online", False)),
            broadcast_id=(
                str(data.get("broadcast_id"))
                if data.get("broadcast_id") not in [None, ""]
                else None
            ),
            checked_at=(
                float(data["checked_at"]) if data.get("checked_at") not in [None, ""] else None
            ),
        )


class WatchStreakCache:
    def __init__(
        self,
        sessions: Dict[str, WatchStreakSession] | None = None,
        default_account_name: str | None = None,
        min_offline_for_new_streak: int = MIN_OFFLINE_FOR_NEW_STREAK,
        streamer_statuses: Dict[str, StreamerWatchStreakStatus] | None = None,
    ):
        self._sessions: Dict[str, WatchStreakSession] = sessions or {}
        self.default_account_name = default_account_name
        self.min_offline_for_new_streak = max(0, int(min_offline_for_new_streak))
        self._lock = threading.Lock()
        self._dirty = False
        self._presence: Dict[str, StreamerPresence] = {}
        self._streamer_statuses: Dict[str, StreamerWatchStreakStatus] = (
            streamer_statuses or {}
        )
        self.bootstrap_done: bool = False

    @classmethod
    def load_from_disk(
        cls,
        path: str,
        default_account_name: str | None = None,
        account_filter: str | None = None,
        min_offline_for_new_streak: int = MIN_OFFLINE_FOR_NEW_STREAK,
    ) -> "WatchStreakCache":
        raw_data: Dict[str, object] = {}
        if not os.path.isfile(path):
            logger.debug(
                "WatchStreakCache: cache not found at %s, starting empty",
                path,
            )
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as exc:
                logger.warning(
                    "Failed to read watch streak cache from %s, starting empty: %s",
                    path,
                    exc,
                )
                raw_data = {}

        sessions: Dict[str, WatchStreakSession] = {}
        streamer_statuses: Dict[str, StreamerWatchStreakStatus] = {}
        normalized_account_filter = (
            account_filter.lower() if isinstance(account_filter, str) else None
        )
        if isinstance(raw_data, dict) and isinstance(raw_data.get("sessions"), list):
            for raw_session in raw_data.get("sessions", []):
                if not isinstance(raw_session, dict):
                    continue
                try:
                    session = WatchStreakSession.from_dict(raw_session)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("Skipping invalid watch streak session: %s", exc)
                    continue
                if not session.account_name or not session.streamer_login or not session.broadcast_id:
                    continue
                if normalized_account_filter is not None:
                    if session.account_name.lower() != normalized_account_filter:
                        continue
                sessions[session.key()] = session
        elif isinstance(raw_data, dict) and raw_data:
            # Backwards compatibility: old format was {<streamer_login>: {"last_streak_timestamp": ts}}
            logger.debug(
                "WatchStreakCache: detected legacy cache format with %d entries, starting fresh",
                len(raw_data),
            )

        if isinstance(raw_data, dict) and isinstance(raw_data.get("streamer_statuses"), list):
            for raw_status in raw_data.get("streamer_statuses", []):
                if not isinstance(raw_status, dict):
                    continue
                try:
                    status = StreamerWatchStreakStatus.from_dict(raw_status)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("Skipping invalid watch streak status: %s", exc)
                    continue
                if not status.account_name or not status.streamer_login:
                    continue
                if normalized_account_filter is not None:
                    if status.account_name.lower() != normalized_account_filter:
                        continue
                streamer_statuses[status.key()] = status

        cache = cls(
            sessions,
            default_account_name,
            min_offline_for_new_streak=min_offline_for_new_streak,
            streamer_statuses=streamer_statuses,
        )
        cache._prune_stale_sessions(time.time())
        logger.debug(
            "WatchStreakCache: loaded %d sessions from %s",
            len(cache._sessions),
            path,
        )
        return cache

    def set_default_account(self, account_name: str) -> None:
        self.default_account_name = account_name

    def _resolve_account(self, account_name: str | None) -> str:
        account = account_name or self.default_account_name
        if not account:
            raise ValueError("account_name is required for watch streak tracking")
        return account

    def _presence_key(self, account_name: str, streamer_login: str) -> str:
        return f"{account_name}:{streamer_login}"

    def _session_key(self, account_name: str, streamer_login: str, broadcast_id: str) -> str:
        return f"{account_name}:{streamer_login}:{broadcast_id}"

    def _status_key(self, account_name: str, streamer_login: str) -> str:
        return f"{account_name}:{streamer_login}"

    def get_streamer_status(
        self, streamer_login: str, account_name: str | None = None
    ) -> Optional[StreamerWatchStreakStatus]:
        account = self._resolve_account(account_name)
        key = self._status_key(account, streamer_login)
        with self._lock:
            return self._streamer_statuses.get(key)

    def set_streamer_status(
        self,
        streamer_login: str,
        watch_streak_detected: bool,
        is_online: bool,
        watch_streak_days: int | None = None,
        last_stream_started_at: float | None = None,
        broadcast_id: str | None = None,
        checked_at: float | None = None,
        account_name: str | None = None,
    ) -> StreamerWatchStreakStatus:
        account = self._resolve_account(account_name)
        checked_at = time.time() if checked_at is None else checked_at
        key = self._status_key(account, streamer_login)
        normalized_watch_streak_days = (
            max(0, int(watch_streak_days))
            if watch_streak_days not in [None, ""]
            else None
        )
        normalized_last_stream_started_at = (
            float(last_stream_started_at)
            if last_stream_started_at not in [None, ""]
            else None
        )
        normalized_broadcast_id = (
            str(broadcast_id) if broadcast_id not in [None, ""] else None
        )
        with self._lock:
            status = self._streamer_statuses.get(key)
            if status is None:
                status = StreamerWatchStreakStatus(
                    account_name=account,
                    streamer_login=streamer_login,
                    watch_streak_detected=bool(watch_streak_detected),
                    watch_streak_days=normalized_watch_streak_days,
                    last_stream_started_at=normalized_last_stream_started_at,
                    is_online=bool(is_online),
                    broadcast_id=normalized_broadcast_id,
                    checked_at=checked_at,
                )
                self._streamer_statuses[key] = status
                self._dirty = True
                return status

            next_watch_streak_days = (
                status.watch_streak_days
                if normalized_watch_streak_days is None
                else normalized_watch_streak_days
            )
            next_last_stream_started_at = (
                status.last_stream_started_at
                if normalized_last_stream_started_at is None
                else normalized_last_stream_started_at
            )

            changed = (
                status.watch_streak_detected != bool(watch_streak_detected)
                or status.watch_streak_days != next_watch_streak_days
                or status.last_stream_started_at != next_last_stream_started_at
                or status.is_online != bool(is_online)
                or status.broadcast_id != normalized_broadcast_id
                or status.checked_at != checked_at
            )
            if changed:
                status.watch_streak_detected = bool(watch_streak_detected)
                status.watch_streak_days = next_watch_streak_days
                status.last_stream_started_at = next_last_stream_started_at
                status.is_online = bool(is_online)
                status.broadcast_id = normalized_broadcast_id
                status.checked_at = checked_at
                self._dirty = True
            return status

    def latest_session_for_streamer(
        self, streamer_login: str, account_name: str | None = None
    ) -> Optional[WatchStreakSession]:
        account = self._resolve_account(account_name)
        with self._lock:
            sessions = [
                s
                for s in self._sessions.values()
                if s.account_name == account and s.streamer_login == streamer_login
            ]
        if not sessions:
            return None
        return max(sessions, key=lambda s: s.started_at)

    def claimed_streak_days(
        self, streamer_login: str, account_name: str | None = None
    ) -> int:
        account = self._resolve_account(account_name)
        with self._lock:
            return sum(
                1
                for session in self._sessions.values()
                if session.account_name == account
                and session.streamer_login == streamer_login
                and session.claimed is True
            )

    def get_session(
        self, streamer_login: str, broadcast_id: str, account_name: str | None = None
    ) -> Optional[WatchStreakSession]:
        account = self._resolve_account(account_name)
        key = self._session_key(account, streamer_login, broadcast_id)
        with self._lock:
            return self._sessions.get(key)

    def ensure_session(
        self,
        streamer_login: str,
        broadcast_id: str,
        started_at: float,
        account_name: str | None = None,
    ) -> WatchStreakSession:
        account = self._resolve_account(account_name)
        key = self._session_key(account, streamer_login, broadcast_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                for other in self._sessions.values():
                    if (
                        other.account_name == account
                        and other.streamer_login == streamer_login
                        and other.ended_at is None
                        and other.broadcast_id != broadcast_id
                    ):
                        other.ended_at = started_at
                        self._dirty = True
                session = WatchStreakSession(
                    account_name=account,
                    streamer_login=streamer_login,
                    broadcast_id=broadcast_id,
                    started_at=started_at,
                )
                self._sessions[key] = session
                self._dirty = True
            return session

    def mark_attempt(
        self,
        streamer_login: str,
        broadcast_id: str,
        attempt_end_time: float,
        account_name: str | None = None,
        max_attempts: int = MAX_STREAK_ATTEMPTS_PER_BROADCAST,
    ) -> WatchStreakSession:
        account = self._resolve_account(account_name)
        session = self.ensure_session(
            streamer_login, broadcast_id, attempt_end_time, account_name=account
        )
        with self._lock:
            session.attempts += 1
            session.last_attempt_at = attempt_end_time
            if session.attempts >= max_attempts and session.ended_at is None:
                session.ended_at = attempt_end_time
            self._dirty = True
            return session

    def mark_claimed(
        self,
        streamer_login: str,
        broadcast_id: str | None = None,
        now: Optional[float] = None,
        account_name: str | None = None,
    ) -> WatchStreakSession:
        account = self._resolve_account(account_name)
        now = time.time() if now is None else now
        session: Optional[WatchStreakSession] = None
        if broadcast_id:
            session = self.get_session(streamer_login, broadcast_id, account_name=account)
        if session is None:
            session = self.latest_session_for_streamer(streamer_login, account_name=account)
        if session is None:
            session = self.ensure_session(
                streamer_login,
                broadcast_id or f"{streamer_login}:{int(now)}",
                now,
                account_name=account,
            )
        with self._lock:
            session.claimed = True
            session.ended_at = session.ended_at or now
            self._dirty = True
            return session

    def mark_ended(
        self,
        streamer_login: str,
        broadcast_id: str,
        ended_at: Optional[float] = None,
        account_name: str | None = None,
    ) -> Optional[WatchStreakSession]:
        account = self._resolve_account(account_name)
        ended_at = time.time() if ended_at is None else ended_at
        key = self._session_key(account, streamer_login, broadcast_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            if session.ended_at is None:
                session.ended_at = ended_at
                self._dirty = True
            return session

    def end_other_sessions(
        self,
        streamer_login: str,
        broadcast_id: str,
        ended_at: Optional[float] = None,
        account_name: str | None = None,
    ) -> None:
        account = self._resolve_account(account_name)
        ended_at = time.time() if ended_at is None else ended_at
        with self._lock:
            for session in self._sessions.values():
                if (
                    session.account_name == account
                    and session.streamer_login == streamer_login
                    and session.broadcast_id != broadcast_id
                    and session.ended_at is None
                ):
                    session.ended_at = ended_at
                    self._dirty = True

    def pending_sessions(
        self,
        account_name: str | None = None,
        max_attempts: int = MAX_STREAK_ATTEMPTS_PER_BROADCAST,
    ) -> list[WatchStreakSession]:
        account = self._resolve_account(account_name)
        with self._lock:
            return [
                s
                for s in self._sessions.values()
                if s.account_name == account
                and s.ended_at is None
                and s.claimed is False
                and s.attempts < max_attempts
            ]

    def record_online(
        self,
        streamer_login: str,
        broadcast_id: str,
        online_at: float,
        account_name: str | None = None,
    ) -> None:
        account = self._resolve_account(account_name)
        key = self._presence_key(account, streamer_login)
        with self._lock:
            presence = self._presence.get(key)
            if presence is None:
                presence = StreamerPresence()
                self._presence[key] = presence
            broadcast_changed = presence.last_broadcast_id not in [None, broadcast_id]
            presence.previous_broadcast_id = presence.last_broadcast_id if broadcast_changed else None
            presence.last_broadcast_id = broadcast_id
            presence.last_online_at = online_at
            presence.seen_online = True

    def record_offline(
        self,
        streamer_login: str,
        offline_at: float,
        account_name: str | None = None,
    ) -> None:
        account = self._resolve_account(account_name)
        key = self._presence_key(account, streamer_login)
        with self._lock:
            presence = self._presence.get(key)
            if presence is None:
                presence = StreamerPresence()
                self._presence[key] = presence
            presence.last_offline_at = offline_at

    def mark_bootstrap_done(self) -> None:
        with self._lock:
            self.bootstrap_done = True

    def _offline_gap_from_presence(self, presence: StreamerPresence) -> Optional[float]:
        if (
            presence.last_online_at is None
            or presence.last_offline_at is None
            or presence.last_online_at < presence.last_offline_at
        ):
            return None
        return presence.last_online_at - presence.last_offline_at

    def should_create_session(
        self,
        streamer_login: str,
        account_name: str | None = None,
    ) -> bool:
        account = self._resolve_account(account_name)
        key = self._presence_key(account, streamer_login)
        with self._lock:
            presence = self._presence.get(key)
            bootstrap_done = self.bootstrap_done
            offline_gap = self._offline_gap_from_presence(presence) if presence else None
            broadcast_changed = (
                presence is not None
                and presence.previous_broadcast_id is not None
                and presence.last_broadcast_id is not None
                and presence.previous_broadcast_id != presence.last_broadcast_id
            )
        if presence is None:
            return False
        if not bootstrap_done:
            return False

        if offline_gap is None:
            # Startup/restart probe: if the streamer is currently online and we have not
            # observed an offline transition in this runtime yet, allow creating a session
            # so missing streaks can be checked without waiting for a future offline gap.
            return presence.last_online_at is not None and presence.last_offline_at is None

        if offline_gap < self.min_offline_for_new_streak:
            return False

        if broadcast_changed:
            return True

        return True

    def _prune_stale_sessions(self, now: float, ttl_seconds: int = STALE_SESSION_TTL_SECONDS):
        with self._lock:
            stale_keys = [
                key
                for key, session in self._sessions.items()
                if session.ended_at is not None and (now - session.ended_at) > ttl_seconds
            ]
            for key in stale_keys:
                del self._sessions[key]
            if stale_keys:
                self._dirty = True

    def save_to_disk_if_dirty(self, path: str) -> None:
        with self._lock:
            if not self._dirty:
                return
            data = {
                "version": WATCH_STREAK_CACHE_VERSION,
                "sessions": [session.to_dict() for session in self._sessions.values()],
                "streamer_statuses": [
                    status.to_dict() for status in self._streamer_statuses.values()
                ],
            }
            dump_json(path, data)
            self._dirty = False
        logger.debug(
            "WatchStreakCache: saved %d sessions and %d streamer statuses to %s",
            len(self._sessions),
            len(self._streamer_statuses),
            path,
        )

