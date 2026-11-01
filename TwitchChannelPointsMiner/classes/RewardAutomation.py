"""Bounded clip/VOD visits adapted from mpforce1's reward workers.

Playback telemetry is an attempt, not proof: only a subsequent Twitch query
can confirm a weekly visit or a recovered streak.
"""

import base64
import copy
import json
import logging
import time
import uuid
from dataclasses import dataclass
from math import isfinite
from threading import Event, Thread

from TwitchChannelPointsMiner.classes.entities.Rewards import (
    Replay,
    StreakRecovery,
    WeeklyRewards,
)
from TwitchChannelPointsMiner.constants import GQLOperations

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RewardAutomationSettings:
    scan_interval_seconds: float = 300
    cooldown_seconds: float = 3600
    max_clip_watch_seconds: float = 30
    max_vod_watch_seconds: float = 480
    verification_interval_seconds: float = 15

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive, finite number")


class RewardAutomation(Thread):
    def __init__(
        self,
        twitch,
        streamers,
        *,
        weekly_rewards=True,
        watch_streak_recovery=True,
        settings=None,
    ):
        super().__init__(name="Weekly rewards / streak recovery", daemon=True)
        self.twitch = twitch
        self.streamers = streamers
        self.weekly_rewards = weekly_rewards
        self.watch_streak_recovery = watch_streak_recovery
        self.settings = settings or RewardAutomationSettings()
        self._stopping = Event()
        self._retry_after = {}

    def stop(self):
        self._stopping.set()

    def _active(self):
        return self.twitch.running and not self._stopping.is_set()

    def _wait(self, seconds):
        deadline = time.monotonic() + seconds
        while self._active():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            self._stopping.wait(min(remaining, 1))
        return False

    @staticmethod
    def _enabled(streamer):
        return (
            bool(streamer.channel_id)
            and streamer.settings is not None
            and streamer.channel_points_enabled
            and not streamer.chat_banned
        )

    def _job_active(self, streamer, kind):
        if not self._active() or not self._enabled(streamer) or streamer.is_online:
            return False
        if kind == "recovery":
            return self.watch_streak_recovery and streamer.needs_watch_streak_recovery()
        return (
            self.weekly_rewards
            and streamer.missing_weekly_reward()
            and not self.twitch._streamer_has_reached_points_limit(streamer)
        )

    def _query(self, operation, variables, path, *, weekly=False):
        if not self._active():
            return False, None
        request = copy.deepcopy(operation)
        request.setdefault("variables", {}).update(variables)
        response = self.twitch.post_gql_request(request)
        if not isinstance(response, dict):
            return False, None
        errors = response.get("errors")
        if errors:
            # Twitch returns this after the last available weekly tier is earned.
            if (
                weekly
                and isinstance(errors, list)
                and all(
                    isinstance(error, dict)
                    and error.get("message")
                    == 'graphql: got nil for non-null "WeeklyVisitRewardTier"'
                    and error.get("path")
                    == ["channel", "self", "weeklyVisitRewards", "currentReward"]
                    for error in errors
                )
            ):
                return True, None
            self.twitch._log_gql_errors(request["operationName"], response)
            return False, None
        value = response
        for key in path:
            if value is None:
                return True, None
            if not isinstance(value, dict) or key not in value:
                return False, None
            value = value[key]
        return True, value

    def refresh_weekly_rewards(self, streamer):
        ok, data = self._query(
            GQLOperations.WeeklyVisitRewardsQuery,
            {"channelID": streamer.channel_id},
            ("data", "channel", "self", "weeklyVisitRewards"),
            weekly=True,
        )
        state = WeeklyRewards.from_dict(data)
        if ok and (data is None or state is not None):
            streamer.weekly_rewards = state
            return state
        return None

    def refresh_streak_recovery(self, streamer):
        ok, data = self._query(
            GQLOperations.RewardList,
            {"channelID": streamer.channel_id},
            ("data", "channel", "self", "watchStreakMilestone"),
        )
        state = StreakRecovery.from_dict(data)
        if ok and (data is None or state is not None):
            streamer.streak_recovery = state
            return state
        return None

    def _replays(self, streamer, replay_kind, *, clip_filter="ALL_TIME"):
        if replay_kind == "clip":
            operation = GQLOperations.ClipsCards__User
            variables = {
                "login": streamer.username,
                "criteria": {"filter": clip_filter},
            }
            path = ("data", "user", "clips", "edges")
        else:
            operation = GQLOperations.FilterableVideoTower_Videos
            variables = {"channelOwnerLogin": streamer.username}
            path = ("data", "user", "videos", "edges")
        ok, edges = self._query(operation, variables, path)
        if not ok or not isinstance(edges, list):
            return []
        return [
            replay
            for edge in edges
            if isinstance(edge, dict)
            and (replay := Replay.from_dict(edge.get("node"), replay_kind)) is not None
        ]

    def _matches(self, replay, kind, baseline):
        return kind != "recovery" or replay.broadcast_id in baseline.missed_broadcasts

    def _vod_viewable(self, streamer, vod):
        ok, token = self._query(
            GQLOperations.PlaybackAccessToken,
            {
                "login": streamer.username,
                "isLive": False,
                "isVod": True,
                "vodID": vod.id,
                "playerBackend": "mediaplayer",
                "playerType": "site",
                "platform": "web",
            },
            ("data", "videoPlaybackAccessToken"),
        )
        if (
            not ok
            or not isinstance(token, dict)
            or not all(
                isinstance(token.get(key), str) and token[key]
                for key in ("signature", "value")
            )
        ):
            return False
        if not self._active():
            return False
        url = f"https://usher.ttvnw.net/vod/v2/{vod.id}.m3u8"
        response = self.twitch._request_with_retry(
            "GET",
            url,
            request_name=f"reward_vod_playlist:{streamer.username}",
            max_attempts=1,
            params={"sig": token["signature"], "token": token["value"]},
            headers={"User-Agent": self.twitch.user_agent},
            timeout=20,
        )
        return (
            response.status_code == 200
            and response.text.lstrip().startswith("#EXTM3U")
            and self.twitch._last_http_url_from_playlist(response.text, url) is not None
        )

    def _send(self, streamer, kind, payload):
        if not self._job_active(streamer, kind):
            return False
        if not streamer.stream.spade_url:
            self.twitch.get_spade_url(streamer)
        if not streamer.stream.spade_url or not self._job_active(streamer, kind):
            return False
        encoded = base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        response = self.twitch._request_with_retry(
            "POST",
            streamer.stream.spade_url,
            request_name=f"reward_playback:{streamer.username}",
            max_attempts=1,
            headers={"User-Agent": self.twitch.user_agent},
            data={"data": encoded},
            timeout=20,
        )
        return response.status_code == 204

    def _confirmed(self, streamer, kind, baseline):
        if not self._active():
            return False
        if kind == "recovery":
            state = self.refresh_streak_recovery(streamer)
            success = state is not None and state.recovered_from(baseline)
        else:
            state = self.refresh_weekly_rewards(streamer)
            success = state is not None and state.progressed_from(baseline)
        if not success:
            return False
        callback = getattr(self.twitch, "_dashboard_event", None)
        if callback:
            callback(kind + "_confirmed", channel=streamer.username, job_kind=kind,
                     streak_days=getattr(state, "streak_days", None),
                     message="Watch streak recovery confirmed by Twitch" if kind == "recovery" else "Weekly visit confirmed by Twitch")
        if kind == "recovery" and streamer.watch_streak_cache is not None:
            # Recovery preserves the count; it must not claim a new live broadcast.
            streamer.watch_streak_cache.set_streamer_status(
                streamer.username,
                watch_streak_detected=(
                    streamer.is_online and streamer.stream.watch_streak_missing is False
                ),
                is_online=streamer.is_online,
                watch_streak_days=state.streak_days,
                account_name=streamer.watch_streak_account,
            )
        if kind == "weekly":
            try:
                self.twitch.load_channel_points_context(streamer)
            except Exception as exc:
                logger.debug(
                    "Weekly balance refresh failed for %s (%s)",
                    streamer.username,
                    type(exc).__name__,
                )
        logger.info(
            "%s confirmed by Twitch for %s",
            "Watch streak recovery" if kind == "recovery" else "Weekly visit",
            streamer.username,
            extra={"emoji": ":calendar:"},
        )
        return True

    def _watch_clip(self, streamer, kind, baseline, clip):
        callback = getattr(self.twitch, "_dashboard_event", None)
        if callback:
            callback(kind + "_clip", channel=streamer.username, job_kind=kind,
                     replay_id=clip.id, replay_url=clip.url, method="Clip")
        properties = {
            "location": "vod",
            "url": clip.url,
            "channel_id": streamer.channel_id,
            "vod_type": "clip",
            "vod_id": clip.id,
            "live": False,
            "minutes_logged": 0,
            "play_session_id": uuid.uuid4().hex,
            "player": "site",
            "user_id": self.twitch.twitch_login.get_user_id(),
            "vod_timestamp": 0,
            "clip_slug": clip.slug,
        }
        if not self._send(
            streamer,
            kind,
            [
                {
                    "event": "video-play",
                    "properties": {**properties, "content_mode": "clip"},
                }
            ],
        ):
            return False
        started = time.monotonic()
        limit = min(clip.duration, self.settings.max_clip_watch_seconds)
        while self._job_active(streamer, kind):
            remaining = limit - (time.monotonic() - started)
            if remaining <= 0 or not self._wait(min(5, remaining)):
                break
            elapsed = min(limit, time.monotonic() - started)
            if not self._send(
                streamer,
                kind,
                [
                    {
                        "event": "n_second_play",
                        "properties": {
                            **properties,
                            "platform": "web",
                            "seconds_after_play": elapsed,
                            "vod_timestamp": max(0, elapsed - 0.1),
                        },
                    }
                ],
            ):
                break
            if elapsed >= 5 and self._confirmed(streamer, kind, baseline):
                return True
        return False

    def _watch_vod(self, streamer, kind, baseline, vod):
        callback = getattr(self.twitch, "_dashboard_event", None)
        if callback:
            callback(kind + "_vod", channel=streamer.username, job_kind=kind,
                     replay_id=vod.id, replay_url=f"https://www.twitch.tv/videos/{vod.id}", method="VOD")
        payload = [
            {
                "event": "minute-watched",
                "properties": {
                    "channel_id": streamer.channel_id,
                    "broadcast_id": None,
                    "player": "site",
                    "user_id": self.twitch.twitch_login.get_user_id(),
                    "live": False,
                    "channel": streamer.username,
                    "vod_id": vod.id,
                    "content_mode": "vod",
                },
            }
        ]
        started = time.monotonic()
        next_send = 0
        limit = min(vod.duration, self.settings.max_vod_watch_seconds)
        while self._job_active(streamer, kind):
            elapsed = time.monotonic() - started
            if elapsed > limit:
                break
            if elapsed >= next_send:
                if not self._send(streamer, kind, payload):
                    break
                next_send = elapsed + 60
            remaining = limit - (time.monotonic() - started)
            if remaining <= 0 or not self._wait(
                min(self.settings.verification_interval_seconds, remaining)
            ):
                break
            if self._confirmed(streamer, kind, baseline):
                return True
        return False

    def _attempt(self, streamer, kind):
        baseline = (
            self.refresh_streak_recovery(streamer)
            if kind == "recovery"
            else self.refresh_weekly_rewards(streamer)
        )
        if baseline is None or not self._job_active(streamer, kind):
            return False
        callback = getattr(self.twitch, "_dashboard_event", None)
        if callback:
            callback(kind + "_trying", channel=streamer.username, job_kind=kind,
                     expires_at=getattr(baseline, "expires_at", None),
                     streak_days=getattr(baseline, "streak_days", None))
        logger.info(
            "Trying %s for %s using a clip or VOD",
            "watch streak recovery" if kind == "recovery" else "a weekly visit",
            streamer.username,
            extra={"emoji": ":clapper_board:"},
        )
        filters = ("LAST_DAY", "LAST_WEEK") if kind == "recovery" else ("ALL_TIME",)
        clip = None
        for clip_filter in filters:
            clip = next(
                (
                    replay
                    for replay in self._replays(
                        streamer, "clip", clip_filter=clip_filter
                    )
                    if self._matches(replay, kind, baseline)
                ),
                None,
            )
            if clip is not None:
                break
        if clip is not None and self._watch_clip(streamer, kind, baseline, clip):
            return True
        if not self._job_active(streamer, kind):
            return False
        for vod in self._replays(streamer, "vod"):
            if not self._job_active(streamer, kind):
                break
            if self._matches(vod, kind, baseline) and self._vod_viewable(streamer, vod):
                return self._watch_vod(streamer, kind, baseline, vod)
        return False

    def scan_once(self):
        jobs = []
        for streamer in list(self.streamers):
            if not self._active():
                return
            if not self._enabled(streamer):
                continue
            try:
                if self.weekly_rewards and streamer.settings.weekly_rewards is True:
                    weekly = self.refresh_weekly_rewards(streamer)
                    if (
                        weekly is not None
                        and weekly.needs_visit()
                        and not streamer.is_online
                        and not self.twitch._streamer_has_reached_points_limit(streamer)
                    ):
                        jobs.append(
                            (1, weekly.ends_at, streamer, "weekly", weekly.event_id)
                        )
                if (
                    self.watch_streak_recovery
                    and streamer.settings.watch_streak is True
                    and streamer.settings.watch_streak_recovery is True
                    and not streamer.is_online
                ):
                    recovery = self.refresh_streak_recovery(streamer)
                    if recovery is not None and recovery.recoverable():
                        jobs.append(
                            (
                                0,
                                recovery.expires_at,
                                streamer,
                                "recovery",
                                tuple(sorted(recovery.missed_broadcasts)),
                            )
                        )
            except Exception as exc:
                logger.debug(
                    "Reward eligibility check failed for %s (%s)",
                    streamer.username,
                    type(exc).__name__,
                )
        now = time.time()
        self._retry_after = {
            key: deadline
            for key, deadline in self._retry_after.items()
            if deadline > now
        }
        for _, _, streamer, kind, identity in sorted(jobs, key=lambda job: job[:2]):
            if not self._active():
                return
            key = (streamer.username, kind, identity)
            if self._retry_after.get(key, 0) > time.time():
                continue
            self._retry_after[key] = time.time() + self.settings.cooldown_seconds
            try:
                if not self._attempt(streamer, kind):
                    callback = getattr(self.twitch, "_dashboard_event", None)
                    if callback:
                        callback(kind + "_unverified", channel=streamer.username, job_kind=kind,
                                 next_retry_at=self._retry_after[key],
                                 message="No Twitch-confirmed progress; retry deferred")
                    logger.debug(
                        "No Twitch-confirmed %s progress for %s; retry deferred",
                        kind,
                        streamer.username,
                    )
            except Exception as exc:
                callback = getattr(self.twitch, "_dashboard_event", None)
                if callback:
                    callback(kind + "_failed", channel=streamer.username, job_kind=kind,
                             next_retry_at=self._retry_after.get(key),
                             message=f"Reward attempt interrupted ({type(exc).__name__})")
                logger.debug(
                    "Reward playback failed for %s (%s)",
                    streamer.username,
                    type(exc).__name__,
                )

    def run(self):
        while self._active():
            self.scan_once()
            if not self._wait(self.settings.scan_interval_seconds):
                break
