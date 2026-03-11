# For documentation on Twitch GraphQL API see:
# https://www.apollographql.com/docs/
# https://github.com/mauricew/twitch-graphql-api
# Full list of available methods: https://azr.ivr.fi/schema/query.doc.html (a bit outdated)


import copy
import logging
import os
import random
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed

import requests
import validators
# import json

from pathlib import Path
from secrets import choice, token_hex
from typing import Dict, Any, Optional
# from urllib.parse import quote
# from base64 import urlsafe_b64decode
# from datetime import datetime

from dataclasses import dataclass
from datetime import timezone
from TwitchChannelPointsMiner.classes.entities.Campaign import Campaign
from TwitchChannelPointsMiner.classes.entities.CommunityGoal import CommunityGoal
from TwitchChannelPointsMiner.classes.entities.Drop import Drop
from TwitchChannelPointsMiner.classes.Exceptions import (
    StreamerDoesNotExistException,
    StreamerIsOfflineException,
)
from TwitchChannelPointsMiner.classes.Settings import (
    Events,
    FollowersOrder,
    Priority,
    Settings,
)
from TwitchChannelPointsMiner.classes.TwitchLogin import TwitchLogin
from TwitchChannelPointsMiner.constants import (
    CLIENT_ID,
    CLIENT_VERSION,
    URL,
    GQLOperations,
)
from TwitchChannelPointsMiner.WatchStreakCache import (
    MAX_STREAK_ATTEMPTS_PER_BROADCAST,
    MIN_OFFLINE_FOR_NEW_STREAK,
    WatchStreakSession,
)
from datetime import datetime
from TwitchChannelPointsMiner.utils import (
    _millify,
    create_chunks,
    internet_connection_available,
    interruptible_sleep,
)

logger = logging.getLogger(__name__)
JsonType = Dict[str, Any]
STREAMER_INIT_TIMEOUT_PER_STREAMER = 5  # seconds
STREAM_INFO_CACHE_TTL = 30  # seconds
GQL_ERROR_LOG_TTL = 60  # seconds
GQL_REQUEST_WARNING_TTL = 5 * 60  # seconds
STREAK_MIN_SECONDS = 5 * 60  # Qualifying watch time before attempting a streak
STREAK_WATCH_EVENTS_TARGET = 2
STREAK_ATTEMPT_TIMEOUT_SECONDS = 12 * 60
SUBSCRIPTION_CONTEXT_REFRESH_SECONDS = 120
CLIENT_VERSION_REFRESH_TTL = 10 * 60  # Avoid refetching client version on every GQL call
CLIENT_VERSION_ERROR_LOG_TTL = 5 * 60
HTTP_RETRY_ATTEMPTS = 3
HTTP_RETRY_BACKOFF_BASE = 0.5
HTTP_RETRY_BACKOFF_CAP = 5.0
RETRYABLE_CONNECTION_SETUP_MARKERS = (
    "failed to establish a new connection",
    "failed to create new connection",
    "temporary failure in name resolution",
    "name or service not known",
    "nodename nor servname provided",
    "getaddrinfo failed",
    "name resolution",
)
SUPPRESSED_GQL_SERVICE_TIMEOUT_OPERATIONS = {
    "VideoPlayerStreamInfoOverlayChannel",
    "ChannelFollows",
    "ChatRoomBanStatus",
    "ChannelPointsContext",
    "Inventory",
    "RewardList",
}


@dataclass
class ActiveWatchStreakAttempt:
    session_key: str
    streamer: str
    broadcast_id: str
    started_at: float
    watch_counter_at_start: int = 0


class Twitch(object):
    __slots__ = [
        "cookies_file",
        "account_username",
        "user_agent",
        "twitch_login",
        "running",
        "device_id",
        # "integrity",
        # "integrity_expire",
        "client_session",
        "client_version",
        "twilight_build_id_pattern",
        "_stream_info_cache",
        "watch_streak_cache",
        "_last_gql_error_log",
        "_last_watch_issue_log",
        "_drop_progress_log",
        "watch_streak_max_parallel",
        "max_watch_amount",
        "_last_selection_was_streak",
        "_last_streak_selection",
        "max_streak_sessions",
        "streak_watch_seconds",
        "streak_watch_events_target",
        "streak_attempt_timeout_seconds",
        "max_streak_attempts",
        "_active_streak_attempts",
        "_streak_outcomes_logged",
        "_streak_rotation_cursor",
        "_client_version_checked_at",
        "_last_client_version_error_log",
    ]

    def __init__(self, username, user_agent, password=None, watch_streak_max_parallel=None):
        cookies_path = os.path.join(Path().absolute(), "cookies")
        Path(cookies_path).mkdir(parents=True, exist_ok=True)
        self.cookies_file = os.path.join(cookies_path, f"{username}.pkl")
        self.account_username = username
        self.user_agent = user_agent
        self.device_id = "".join(
            choice(string.ascii_letters + string.digits) for _ in range(32)
        )
        self.twitch_login = TwitchLogin(
            CLIENT_ID, self.device_id, username, self.user_agent, password=password
        )
        self.running = True
        # self.integrity = None
        # self.integrity_expire = 0
        self.client_session = token_hex(16)
        self.client_version = CLIENT_VERSION
        self.twilight_build_id_pattern = re.compile(
            r'window\.__twilightBuildID\s*=\s*"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"'
        )
        self._stream_info_cache = {}
        self.watch_streak_cache = None
        self._last_gql_error_log = {}
        self._last_watch_issue_log = {}
        self._drop_progress_log: Dict[str, int] = {}
        self.watch_streak_max_parallel = (
            max(1, int(watch_streak_max_parallel))
            if watch_streak_max_parallel is not None
            else None
        )
        self.max_watch_amount = 2
        self._last_selection_was_streak = False
        self._last_streak_selection: set[str] = set()
        self.max_streak_sessions = min(
            2,
            2 if self.watch_streak_max_parallel is None else self.watch_streak_max_parallel,
        )
        self.max_streak_attempts = MAX_STREAK_ATTEMPTS_PER_BROADCAST
        self.streak_watch_seconds = STREAK_MIN_SECONDS
        self.streak_watch_events_target = STREAK_WATCH_EVENTS_TARGET
        self.streak_attempt_timeout_seconds = max(
            STREAK_ATTEMPT_TIMEOUT_SECONDS,
            self.streak_watch_seconds * 2,
        )
        self._active_streak_attempts: Dict[str, ActiveWatchStreakAttempt] = {}
        # Track which sessions we've already logged a terminal outcome for
        self._streak_outcomes_logged: set[str] = set()
        self._streak_rotation_cursor = 0
        self._client_version_checked_at = 0.0
        self._last_client_version_error_log = 0.0

    def login(self):
        if not os.path.isfile(self.cookies_file):
            if self.twitch_login.login_flow():
                self.twitch_login.save_cookies(self.cookies_file)
        else:
            self.twitch_login.load_cookies(self.cookies_file)
            self.twitch_login.set_token(self.twitch_login.get_auth_token())

    # === STREAMER / STREAM / INFO === #
    def update_stream(self, streamer):
        if streamer.stream.update_required() is False:
            return True

        stream_info = self.get_stream_info(streamer)
        if stream_info is None:
            return False

        try:
            streamer.stream.update(
                broadcast_id=stream_info["stream"]["id"],
                title=stream_info["broadcastSettings"]["title"],
                game=stream_info["broadcastSettings"]["game"],
                tags=stream_info["stream"]["tags"],
                viewers_count=stream_info["stream"]["viewersCount"],
                created_at=stream_info["stream"].get("createdAt"),
            )
        except (KeyError, TypeError):
            logger.debug("Invalid stream info for %s", streamer.username)
            return False

        streamer.chat_banned = self._is_chat_banned(
            stream_info.get("chatRoomBanStatus")
        )

        streak_was_missing = streamer.stream.watch_streak_missing
        startup_streak_probe = (
            self.watch_streak_cache is not None
            and self.watch_streak_cache.bootstrap_done is False
        )
        if stream_info.get("watchStreakMissing") is False:
            streamer.stream.watch_streak_missing = False
            watch_streak_history = streamer.history.get("WATCH_STREAK", {})
            has_runtime_watch_streak_reward = (
                isinstance(watch_streak_history, dict)
                and int(watch_streak_history.get("counter", 0) or 0) > 0
            )
            should_log_detected = streak_was_missing or (
                startup_streak_probe and not has_runtime_watch_streak_reward
            )
            if self.watch_streak_cache is not None and streamer.stream.broadcast_id:
                session = self.watch_streak_cache.get_session(
                    streamer.username,
                    streamer.stream.broadcast_id,
                    account_name=self.account_username,
                )
                if session is None or session.claimed is False:
                    session = self.watch_streak_cache.mark_claimed(
                        streamer.username,
                        broadcast_id=streamer.stream.broadcast_id,
                        now=time.time(),
                        account_name=self.account_username,
                    )
                if should_log_detected and session is not None:
                    self._log_streak_claimed(session, streamer)
            elif should_log_detected:
                logger.info(
                    "Detected WATCH_STREAK for %s",
                    streamer,
                    extra={"emoji": ":rocket:", "event": Events.GAIN_FOR_WATCH_STREAK},
                )

        if self.watch_streak_cache is not None:
            self.watch_streak_cache.set_streamer_status(
                streamer.username,
                watch_streak_detected=(
                    streamer.settings.watch_streak is True
                    and streamer.stream.watch_streak_missing is False
                ),
                is_online=True,
                watch_streak_days=stream_info.get("watchStreakDays"),
                last_stream_started_at=stream_info.get("stream", {}).get("createdAt"),
                broadcast_id=streamer.stream.broadcast_id,
                checked_at=time.time(),
                account_name=self.account_username,
            )

        event_properties = {
            "channel_id": streamer.channel_id,
            "broadcast_id": streamer.stream.broadcast_id,
            "player": "site",
            "user_id": self.twitch_login.get_user_id(),
            "live": True,
            "channel": streamer.username,
        }

        if (
            streamer.stream.game_name() is not None
            and streamer.stream.game_id() is not None
            and streamer.settings.claim_drops is True
        ):
            event_properties["game"] = streamer.stream.game_name()
            event_properties["game_id"] = streamer.stream.game_id()
            # Update also the campaigns_ids so we are sure to tracking the correct campaign
            streamer.stream.campaigns_ids = (
                self.__get_campaign_ids_from_streamer(streamer)
            )

        streamer.stream.payload = [
            {"event": "minute-watched", "properties": event_properties}
        ]
        return True

    def get_spade_url(self, streamer):
        try:
            # fixes AttributeError: 'NoneType' object has no attribute 'group'
            # headers = {"User-Agent": self.user_agent}
            from TwitchChannelPointsMiner.constants import USER_AGENTS

            headers = {"User-Agent": USER_AGENTS["Linux"]["FIREFOX"]}

            main_page_request = self._request_with_retry(
                "GET",
                streamer.streamer_url,
                request_name=f"get_spade_url_main:{streamer.username}",
                headers=headers,
                timeout=20,
            )
            response = main_page_request.text
            # logger.info(response)
            regex_settings = "(https://static.twitchcdn.net/config/settings.*?js|https://assets.twitch.tv/config/settings.*?.js)"
            settings_match = re.search(regex_settings, response)
            if settings_match is None:
                logger.debug("Unable to find settings URL while extracting spade_url for %s", streamer.username)
                return
            settings_url = settings_match.group(1)

            settings_request = self._request_with_retry(
                "GET",
                settings_url,
                request_name=f"get_spade_url_settings:{streamer.username}",
                headers=headers,
                timeout=20,
            )
            response = settings_request.text
            regex_spade = '"spade_url":"(.*?)"'
            spade_match = re.search(regex_spade, response)
            if spade_match is None:
                logger.debug("Unable to find spade_url in settings response for %s", streamer.username)
                return
            streamer.stream.spade_url = spade_match.group(1)
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Something went wrong during extraction of 'spade_url': {e}")

    def get_broadcast_id(self, streamer):
        json_data = copy.deepcopy(GQLOperations.WithIsStreamLiveQuery)
        json_data["variables"] = {"id": streamer.channel_id}
        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            raise StreamerIsOfflineException
        stream = (
            response.get("data", {}).get("user", {}).get("stream")
            if isinstance(response, dict)
            else None
        )
        if stream is not None and stream.get("id") is not None:
            return stream.get("id")
        raise StreamerIsOfflineException

    def get_stream_info(self, streamer):
        cache_key = streamer.username
        now = time.time()
        cached_entry = self._get_cached_stream_info(cache_key, now)
        if cached_entry:
            return cached_entry

        json_data = copy.deepcopy(GQLOperations.VideoPlayerStreamInfoOverlayChannel)
        json_data["variables"] = {"channel": streamer.username}
        response = self.post_gql_request(json_data)
        if not response:
            return cached_entry

        self._log_gql_errors(json_data.get("operationName"), response)

        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            logger.debug(
                "Stream info response missing data for %s", streamer.username
            )
            return cached_entry

        user = data.get("user")
        if user is None:
            self._invalidate_stream_info_cache(cache_key)
            raise StreamerIsOfflineException

        stream = user.get("stream") if isinstance(user, dict) else None
        if stream is None:
            self._invalidate_stream_info_cache(cache_key)
            raise StreamerIsOfflineException

        broadcast_settings = (
            stream.get("broadcastSettings") if isinstance(stream, dict) else None
        )
        if not isinstance(broadcast_settings, dict):
            broadcast_settings = {}

        if not isinstance(stream.get("tags"), list):
            stream["tags"] = []
        viewers_count = (
            stream.get("viewersCount") if stream.get("viewersCount") is not None else 0
        )
        stream_id = stream.get("id")
        if stream_id is None:
            self._invalidate_stream_info_cache(cache_key)
            raise StreamerIsOfflineException
        title = broadcast_settings.get("title") or ""
        game = broadcast_settings.get("game") or {}

        stream_info = {
            "stream": {
                "id": stream_id,
                "tags": stream.get("tags"),
                "viewersCount": viewers_count,
            },
            "broadcastSettings": {
                "title": title,
                "game": game,
            },
        }

        stream_created_at = self._parse_iso8601_timestamp(stream.get("createdAt"))
        if stream_created_at is None and streamer.channel_id:
            is_live_request = copy.deepcopy(GQLOperations.WithIsStreamLiveQuery)
            is_live_request["variables"] = {"id": streamer.channel_id}
            is_live_response = self.post_gql_request(is_live_request)
            self._log_gql_errors(is_live_request.get("operationName"), is_live_response)
            stream_created_at = self._extract_stream_created_timestamp(is_live_response)
        if stream_created_at is not None:
            stream_info["stream"]["createdAt"] = stream_created_at

        if streamer.settings.watch_streak is True and streamer.channel_id:
            reward_response = self._get_reward_list_response(streamer)
            watch_streak_days = self._extract_watch_streak_days(reward_response)
            if watch_streak_days is not None:
                stream_info["watchStreakDays"] = watch_streak_days
            milestone_achievement_at = self._extract_watch_streak_achievement_timestamp(
                reward_response
            )
            if (
                milestone_achievement_at is not None
                and stream_created_at is not None
                and milestone_achievement_at > stream_created_at
            ):
                stream_info["watchStreakMissing"] = False

        chat_banned = self.get_chat_ban_status(streamer)
        if chat_banned is not None:
            stream_info["chatRoomBanStatus"] = chat_banned

        self._stream_info_cache[cache_key] = {
            "data": stream_info,
            "timestamp": now,
        }
        return stream_info

    def check_streamer_online(self, streamer):
        if time.time() < streamer.offline_at + 60:
            return

        if streamer.is_online is False:
            try:
                self.get_spade_url(streamer)
                updated = self.update_stream(streamer)
            except StreamerIsOfflineException:
                streamer.set_offline()
            else:
                if updated:
                    streamer.set_online()
        else:
            try:
                updated = self.update_stream(streamer)
            except StreamerIsOfflineException:
                streamer.set_offline()
            else:
                if updated is False:
                    # Transient error, keep current state
                    return

    def get_channel_id(self, streamer_username):
        json_data = copy.deepcopy(GQLOperations.GetIDFromLogin)
        json_data["variables"]["login"] = streamer_username
        json_response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), json_response):
            raise StreamerDoesNotExistException
        user = (
            json_response.get("data", {}).get("user")
            if isinstance(json_response, dict)
            else None
        )
        if not user or user.get("id") is None:
            raise StreamerDoesNotExistException
        return user["id"]

    def _get_reward_list_response(self, streamer):
        if not getattr(streamer, "channel_id", None):
            return None
        reward_list_request = copy.deepcopy(GQLOperations.RewardList)
        reward_list_request["variables"]["channelID"] = streamer.channel_id
        reward_response = self.post_gql_request(reward_list_request)
        self._log_gql_errors(reward_list_request.get("operationName"), reward_response)
        return reward_response

    def get_watch_streak_days(self, streamer):
        reward_response = self._get_reward_list_response(streamer)
        if reward_response is None:
            return None
        return self._extract_watch_streak_days(reward_response)

    def get_chat_ban_status(self, streamer):
        viewer_user_id = self.twitch_login.get_user_id()
        if not getattr(streamer, "channel_id", None) or viewer_user_id is None:
            return None

        chat_room_ban_request = copy.deepcopy(GQLOperations.ChatRoomBanStatus)
        chat_room_ban_request["variables"] = {
            "targetUserID": f"{viewer_user_id}",
            "channelID": streamer.channel_id,
        }
        chat_room_ban_response = self.post_gql_request(chat_room_ban_request)
        self._log_gql_errors(
            chat_room_ban_request.get("operationName"),
            chat_room_ban_response,
        )
        if not isinstance(chat_room_ban_response, dict):
            return None
        data = chat_room_ban_response.get("data")
        if not isinstance(data, dict) or "chatRoomBanStatus" not in data:
            return None
        return self._is_chat_banned(data.get("chatRoomBanStatus"))

    def get_followers(
        self, limit: int = 100, order: FollowersOrder = FollowersOrder.ASC
    ):
        json_data = copy.deepcopy(GQLOperations.ChannelFollows)
        json_data["variables"] = {"limit": limit, "order": str(order)}
        has_next = True
        last_cursor = ""
        follows = []
        timeouts_in_a_row = 0
        while has_next is True:
            json_data["variables"]["cursor"] = last_cursor
            while True:
                json_response = self.post_gql_request(json_data)
                is_timeout = self._has_service_timeout(json_response)
                if self._log_gql_errors(json_data.get("operationName"), json_response):
                    if is_timeout:
                        timeouts_in_a_row += 1
                        logger.debug(
                            "[follows] ChannelFollows service timeout (attempt %d)",
                            timeouts_in_a_row,
                        )
                        if timeouts_in_a_row == 2:
                            logger.info(
                                "[follows] ChannelFollows got %d service timeouts, retrying...",
                                timeouts_in_a_row,
                            )
                        time.sleep(min(3, 0.5 * timeouts_in_a_row + 0.5))
                        continue
                    return follows
                break
            if timeouts_in_a_row > 1:
                logger.debug(
                    "[follows] ChannelFollows recovered after %d service timeouts",
                    timeouts_in_a_row,
                )
            timeouts_in_a_row = 0
            follows_response = (
                json_response.get("data", {})
                .get("user", {})
                .get("follows", {})
                if isinstance(json_response, dict)
                else {}
            )
            if not follows_response:
                return follows

            last_cursor = None
            for f in follows_response.get("edges", []):
                try:
                    follows.append(f["node"]["login"].lower())
                    last_cursor = f.get("cursor", last_cursor)
                except (KeyError, TypeError):
                    continue

            has_next = (
                follows_response.get("pageInfo", {}).get("hasNextPage", False)
                if isinstance(follows_response, dict)
                else False
            )
        return follows

    def get_followers_with_dates(
        self, limit: int = 100, order: FollowersOrder = FollowersOrder.ASC
    ) -> dict[str, str | None]:
        json_data = copy.deepcopy(GQLOperations.ChannelFollows)
        json_data["variables"] = {"limit": limit, "order": str(order)}
        has_next = True
        last_cursor = ""
        follows: dict[str, str | None] = {}
        timeouts_in_a_row = 0
        while has_next is True:
            json_data["variables"]["cursor"] = last_cursor
            while True:
                json_response = self.post_gql_request(json_data)
                is_timeout = self._has_service_timeout(json_response)
                if self._log_gql_errors(json_data.get("operationName"), json_response):
                    if is_timeout:
                        timeouts_in_a_row += 1
                        logger.debug(
                            "[follows] ChannelFollows service timeout (attempt %d)",
                            timeouts_in_a_row,
                        )
                        if timeouts_in_a_row == 2:
                            logger.info(
                                "[follows] ChannelFollows got %d service timeouts, retrying...",
                                timeouts_in_a_row,
                            )
                        time.sleep(min(3, 0.5 * timeouts_in_a_row + 0.5))
                        continue
                    return follows
                break

            if timeouts_in_a_row > 1:
                logger.debug(
                    "[follows] ChannelFollows recovered after %d service timeouts",
                    timeouts_in_a_row,
                )
            timeouts_in_a_row = 0
            follows_response = (
                json_response.get("data", {})
                .get("user", {})
                .get("follows", {})
                if isinstance(json_response, dict)
                else {}
            )
            if not follows_response:
                return follows

            last_cursor = None
            for edge in follows_response.get("edges", []):
                if not isinstance(edge, dict):
                    continue
                try:
                    node = edge.get("node", {})
                    if not isinstance(node, dict):
                        continue
                    login = node.get("login")
                    if not login:
                        continue
                    self_data = node.get("self", {})
                    follower_data = self_data.get("follower", {}) if isinstance(self_data, dict) else {}
                    followed_at = (
                        follower_data.get("followedAt")
                        if isinstance(follower_data, dict)
                        else None
                    )
                    follows[str(login).lower()] = followed_at
                    last_cursor = edge.get("cursor", last_cursor)
                except (KeyError, TypeError, AttributeError):
                    continue

            has_next = (
                follows_response.get("pageInfo", {}).get("hasNextPage", False)
                if isinstance(follows_response, dict)
                else False
            )
        return follows

    def update_raid(self, streamer, raid):
        if streamer.raid != raid:
            streamer.raid = raid
            json_data = copy.deepcopy(GQLOperations.JoinRaid)
            json_data["variables"] = {"input": {"raidID": raid.raid_id}}
            self.post_gql_request(json_data)

            logger.info(
                f"Joining raid from {streamer} to {raid.target_login}!",
                extra={"emoji": ":performing_arts:",
                       "event": Events.JOIN_RAID},
            )

    def viewer_is_mod(self, streamer):
        json_data = copy.deepcopy(GQLOperations.ModViewChannelQuery)
        json_data["variables"] = {"channelLogin": streamer.username}
        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            streamer.viewer_is_mod = False
            return
        try:
            streamer.viewer_is_mod = (
                response.get("data", {})
                .get("user", {})
                .get("self", {})
                .get("isModerator", False)
            )
        except (ValueError, AttributeError):
            streamer.viewer_is_mod = False

    # === 'GLOBALS' METHODS === #
    # Create chunk of sleep of speed-up the break loop after CTRL+C
    def __chuncked_sleep(self, seconds, chunk_size=3):
        step = max(seconds / max(chunk_size, 1), 0.5)
        interruptible_sleep(lambda: self.running, seconds, step=step)

    def __check_connection_handler(self, chunk_size):
        # The success rate It's very hight usually. Why we have failed?
        # Check internet connection ...
        while internet_connection_available() is False:
            random_sleep = random.randint(1, 3)
            logger.warning(
                f"No internet connection available! Retry after {random_sleep}m"
            )
            self.__chuncked_sleep(random_sleep * 60, chunk_size=chunk_size)

    def _is_retryable_connection_setup_error(self, exception):
        if isinstance(
            exception,
            (
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ChunkedEncodingError,
            ),
        ):
            return True
        if not isinstance(exception, requests.exceptions.ConnectionError):
            return False

        message = str(exception).lower()
        return any(marker in message for marker in RETRYABLE_CONNECTION_SETUP_MARKERS)

    def _request_with_retry(
        self,
        method,
        url,
        *,
        request_name,
        max_attempts=HTTP_RETRY_ATTEMPTS,
        backoff_base=HTTP_RETRY_BACKOFF_BASE,
        backoff_cap=HTTP_RETRY_BACKOFF_CAP,
        **kwargs,
    ):
        attempt = 1
        while True:
            try:
                return requests.request(method, url, **kwargs)
            except requests.exceptions.RequestException as exc:
                if (
                    attempt >= max_attempts
                    or self._is_retryable_connection_setup_error(exc) is False
                ):
                    raise

                delay = min(backoff_cap, backoff_base * (2 ** (attempt - 1)))
                if delay > 0:
                    delay += random.uniform(0.0, min(0.25, delay / 2))

                logger.debug(
                    "%s failed with transient connection setup error (%d/%d): %s. Retrying in %.2fs",
                    request_name,
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                if delay > 0:
                    interruptible_sleep(
                        lambda: self.running,
                        delay,
                        step=max(0.1, min(0.5, delay)),
                    )
                attempt += 1

    def _effective_streak_min_offline_seconds(self) -> int:
        if self.watch_streak_cache is None:
            return MIN_OFFLINE_FOR_NEW_STREAK
        return max(
            0,
            int(
                getattr(
                    self.watch_streak_cache,
                    "min_offline_for_new_streak",
                    MIN_OFFLINE_FOR_NEW_STREAK,
                )
            ),
        )

    def _summarize_gql_error_messages(self, messages) -> tuple[str, bool]:
        normalized_messages = []
        service_timeout_count = 0
        for message in messages:
            if isinstance(message, str) and "service timeout" in message.lower():
                service_timeout_count += 1
            else:
                normalized_messages.append(message)

        if service_timeout_count == 1:
            normalized_messages.append("service timeout")
        elif service_timeout_count > 1:
            normalized_messages.append(f"service timeout (x{service_timeout_count})")

        if not normalized_messages:
            normalized_messages.append("Unknown GQL error")

        return "; ".join(normalized_messages), service_timeout_count > 0

    def _log_gql_errors(self, operation_name, response):
        if not isinstance(response, dict):
            return False
        errors = response.get("errors") or []
        if errors in [[], None]:
            return False
        messages = []
        for error in errors:
            if isinstance(error, dict):
                message = error.get("message", str(error))
            else:
                message = str(error)
            messages.append(message)
        message, has_service_timeout = self._summarize_gql_error_messages(messages)
        if (
            has_service_timeout
            and operation_name in SUPPRESSED_GQL_SERVICE_TIMEOUT_OPERATIONS
        ):
            logger.debug(
                "GQL operation %s returned service timeout (suppressed): %s",
                operation_name,
                message,
            )
            return True
        now = time.time()
        key = (operation_name, message)
        last_logged = self._last_gql_error_log.get(key, 0)
        if now - last_logged >= GQL_ERROR_LOG_TTL:
            logger.warning(
                "GQL operation %s returned errors: %s", operation_name, message
            )
            self._last_gql_error_log[key] = now
        return True

    def _log_request_exception(self, operation_name, error_message):
        now = time.time()
        key = (operation_name, error_message)
        last_logged = self._last_gql_error_log.get(key, 0)
        if now - last_logged >= GQL_ERROR_LOG_TTL:
            logger.error(
                "Error with GQLOperations (%s): %s", operation_name, error_message
            )
            self._last_gql_error_log[key] = now

    def _has_service_timeout(self, response):
        if not isinstance(response, dict):
            return False
        errors = response.get("errors") or []
        for error in errors:
            message = error.get("message") if isinstance(error, dict) else str(error)
            if isinstance(message, str) and "service timeout" in message.lower():
                return True
        return False

    def _render_drop_progress_bar(self, percent: int) -> str:
        percent = max(0, min(100, percent))
        length = 20
        filled = int((percent * length) / 100)
        return f"[{'█' * filled}{'░' * (length - filled)}]"

    def _log_drop_progress(self, streamer, drop, drops_logging_enabled: bool):
        if not drops_logging_enabled:
            return
        drop_id = getattr(drop, "drop_instance_id", None) or getattr(drop, "id", None)
        if drop_id is None or drop.is_claimed or drop.minutes_required <= 0:
            return

        progress_ratio = drop.current_minutes_watched / drop.minutes_required
        progress_ratio = max(0.0, min(1.0, progress_ratio))
        percent = int(progress_ratio * 100)

        # Always emit an initial log for a new drop progress entry
        last_logged = self._drop_progress_log.get(drop_id)
        if last_logged is None:
            logger.info(
                "[DROPS] %s - \"%s\" %s/%s min (%d%%)",
                streamer.username,
                drop.name,
                drop.current_minutes_watched,
                drop.minutes_required,
                percent,
            )
            self._drop_progress_log[drop_id] = max(0, percent)
            if percent >= 100:
                self._drop_progress_log.pop(drop_id, None)
            return

        if percent >= 100:
            logger.info(
                f"[DROPS] {streamer.username} - \"{drop.name}\" {drop.minutes_required}/{drop.minutes_required} min (100%)"
            )
            self._drop_progress_log.pop(drop_id, None)
            return

        if percent < last_logged + 10 and percent != 100:
            return

        current_minutes = min(drop.current_minutes_watched, drop.minutes_required)
        logger.info(
            f"[DROPS] {streamer.username} - \"{drop.name}\" {current_minutes}/{drop.minutes_required} min ({percent}%)"
        )
        self._drop_progress_log[drop_id] = percent

    def _get_cached_stream_info(self, cache_key, now):
        cached_entry = self._stream_info_cache.get(cache_key)
        if cached_entry and (now - cached_entry["timestamp"]) <= STREAM_INFO_CACHE_TTL:
            return cached_entry["data"]
        return None

    def _invalidate_stream_info_cache(self, cache_key):
        self._stream_info_cache.pop(cache_key, None)

    def _parse_iso8601_timestamp(self, value):
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None

    def _is_chat_banned(self, chat_room_ban_status):
        if chat_room_ban_status is None:
            return False
        if isinstance(chat_room_ban_status, dict):
            if "banStatus" in chat_room_ban_status:
                return self._is_chat_banned(chat_room_ban_status.get("banStatus"))
            if "isBanned" in chat_room_ban_status:
                return bool(chat_room_ban_status.get("isBanned"))
            if not chat_room_ban_status:
                return False
            known_ban_fields = {
                "bannedUser",
                "createdAt",
                "expiresAt",
                "expiresInMs",
                "isPermanent",
                "moderator",
                "reason",
                "roomOwner",
            }
            return any(field in chat_room_ban_status for field in known_ban_fields)
        return bool(chat_room_ban_status)

    def _extract_stream_created_timestamp(self, response):
        if not isinstance(response, dict):
            return None
        data = response.get("data")
        if not isinstance(data, dict):
            return None
        user = data.get("user")
        if not isinstance(user, dict):
            return None
        stream = user.get("stream")
        if not isinstance(stream, dict):
            return None
        created_at = stream.get("createdAt")
        return self._parse_iso8601_timestamp(created_at)

    def _extract_watch_streak_achievement_timestamp(self, response):
        if not isinstance(response, dict):
            return None
        data = response.get("data")
        if not isinstance(data, dict):
            return None
        channel = data.get("channel")
        if not isinstance(channel, dict):
            return None
        viewer_self = channel.get("self")
        if not isinstance(viewer_self, dict):
            return None
        milestone = viewer_self.get("watchStreakMilestone")
        if not isinstance(milestone, dict):
            return None

        viewer_milestone = milestone.get("watchStreakMilestone")
        if not isinstance(viewer_milestone, dict):
            return None
        return self._parse_iso8601_timestamp(
            viewer_milestone.get("achievementTimestamp")
        )

    def _extract_watch_streak_days(self, response):
        if not isinstance(response, dict):
            return None
        data = response.get("data")
        if not isinstance(data, dict):
            return None
        channel = data.get("channel")
        if not isinstance(channel, dict):
            return None
        viewer_self = channel.get("self")
        if not isinstance(viewer_self, dict):
            return None
        milestone = viewer_self.get("watchStreakMilestone")
        if not isinstance(milestone, dict):
            return None

        candidates: list[dict] = []
        viewer_milestone = milestone.get("watchStreakMilestone")
        if isinstance(viewer_milestone, dict):
            candidates.append(viewer_milestone)
        candidates.append(milestone)

        explicit_keys = (
            "watchStreakDays",
            "currentStreakDays",
            "streakDays",
            "daysWatched",
            "streakDayCount",
            "dayCount",
            "currentDay",
        )

        def _to_non_negative_int(value):
            if isinstance(value, bool):
                return None
            if isinstance(value, int):
                return value if value >= 0 else None
            if isinstance(value, float):
                if value.is_integer() and value >= 0:
                    return int(value)
                return None
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.isdigit():
                    return int(stripped)
            return None

        def _walk(node, depth=0):
            if depth > 6:
                return None
            if isinstance(node, dict):
                if str(node.get("category", "")).upper() == "WATCH_STREAK":
                    parsed_value = _to_non_negative_int(node.get("value"))
                    if parsed_value is not None:
                        return parsed_value
                for key in explicit_keys:
                    if key in node:
                        parsed = _to_non_negative_int(node.get(key))
                        if parsed is not None:
                            return parsed
                for key, value in node.items():
                    key_lower = str(key).lower()
                    parsed = _to_non_negative_int(value)
                    if (
                        parsed is not None
                        and "day" in key_lower
                        and "timestamp" not in key_lower
                        and "until" not in key_lower
                        and parsed <= 3650
                    ):
                        return parsed
                for value in node.values():
                    nested = _walk(value, depth + 1)
                    if nested is not None:
                        return nested
            elif isinstance(node, list):
                for item in node:
                    nested = _walk(item, depth + 1)
                    if nested is not None:
                        return nested
            return None

        for candidate in candidates:
            extracted = _walk(candidate)
            if extracted is not None:
                return extracted
        return None

    def _operation_name_from_json_data(self, json_data):
        if isinstance(json_data, dict):
            return json_data.get("operationName", "UnknownOperation")
        if isinstance(json_data, list) and json_data:
            first = json_data[0]
            if isinstance(first, dict):
                return first.get("operationName", "UnknownOperation")
        return "UnknownOperation"

    def _log_watch_issue(
        self,
        streamer_username: str,
        issue_key: str,
        message: str,
        *args,
        ttl: int = 120,
        level: int = logging.WARNING,
    ):
        key = (streamer_username, issue_key)
        now = time.time()
        last_logged = self._last_watch_issue_log.get(key, 0)
        if now - last_logged >= ttl:
            logger.log(level, message, *args)
            self._last_watch_issue_log[key] = now

    def post_gql_request(self, json_data):
        operation_name = self._operation_name_from_json_data(json_data)
        try:
            response = self._request_with_retry(
                "POST",
                GQLOperations.url,
                request_name=f"post_gql_request:{operation_name}",
                json=json_data,
                headers={
                    "Authorization": f"OAuth {self.twitch_login.get_auth_token()}",
                    "Client-Id": CLIENT_ID,
                    # "Client-Integrity": self.post_integrity(),
                    "Client-Session-Id": self.client_session,
                    "Client-Version": self.update_client_version(),
                    "User-Agent": self.user_agent,
                    "X-Device-Id": self.device_id,
                },
                timeout=20,
            )
            logger.debug(
                f"Data: {json_data}, Status code: {response.status_code}, Content: {response.text}"
            )
            if response.status_code < 200 or response.status_code >= 300:
                key = ("gql_http_status", operation_name, response.status_code)
                now = time.time()
                last_logged = self._last_gql_error_log.get(key, 0)
                if now - last_logged >= GQL_REQUEST_WARNING_TTL:
                    logger.warning(
                        "GQL operation %s returned HTTP status %s",
                        operation_name,
                        response.status_code,
                    )
                    self._last_gql_error_log[key] = now
                else:
                    logger.debug(
                        "GQL operation %s returned HTTP status %s (suppressed)",
                        operation_name,
                        response.status_code,
                    )
            try:
                return response.json()
            except ValueError:
                key = ("gql_invalid_json", operation_name, response.status_code)
                now = time.time()
                last_logged = self._last_gql_error_log.get(key, 0)
                if now - last_logged >= GQL_REQUEST_WARNING_TTL:
                    logger.warning(
                        "Invalid JSON response for %s (status %s)",
                        operation_name,
                        response.status_code,
                    )
                    self._last_gql_error_log[key] = now
                else:
                    logger.debug(
                        "Invalid JSON response for %s (status %s) (suppressed)",
                        operation_name,
                        response.status_code,
                    )
                return {}
        except requests.exceptions.RequestException as e:
            self._log_request_exception(operation_name, str(e))
            return {}

    # Request for Integrity Token
    # Twitch needs Authorization, Client-Id, X-Device-Id to generate JWT which is used for authorize gql requests
    # Regenerate Integrity Token 5 minutes before expire
    """def post_integrity(self):
        if (
            self.integrity_expire - datetime.now().timestamp() * 1000 > 5 * 60 * 1000
            and self.integrity is not None
        ):
            return self.integrity
        try:
            response = requests.post(
                GQLOperations.integrity_url,
                json={},
                headers={
                    "Authorization": f"OAuth {self.twitch_login.get_auth_token()}",
                    "Client-Id": CLIENT_ID,
                    "Client-Session-Id": self.client_session,
                    "Client-Version": self.update_client_version(),
                    "User-Agent": self.user_agent,
                    "X-Device-Id": self.device_id,
                },
            )
            logger.debug(
                f"Data: [], Status code: {response.status_code}, Content: {response.text}"
            )
            self.integrity = response.json().get("token", None)
            # logger.info(f"integrity: {self.integrity}")

            if self.isBadBot(self.integrity) is True:
                logger.info(
                    "Uh-oh, Twitch has detected this miner as a \"Bad Bot\". Don't worry.")

            self.integrity_expire = response.json().get("expiration", 0)
            # logger.info(f"integrity_expire: {self.integrity_expire}")
            return self.integrity
        except requests.exceptions.RequestException as e:
            logger.error(f"Error with post_integrity: {e}")
            return self.integrity

    # verify the integrity token's contents for the "is_bad_bot" flag
    def isBadBot(self, integrity):
        stripped_token: str = self.integrity.split('.')[2] + "=="
        messy_json: str = urlsafe_b64decode(
            stripped_token.encode()).decode(errors="ignore")
        match = re.search(r'(.+)(?<="}).+$', messy_json)
        if match is None:
            # raise MinerException("Unable to parse the integrity token")
            logger.info("Unable to parse the integrity token. Don't worry.")
            return
        decoded_header = json.loads(match.group(1))
        # logger.info(f"decoded_header: {decoded_header}")
        if decoded_header.get("is_bad_bot", "false") != "false":
            return True
        else:
            return False"""

    def update_client_version(self):
        now = time.time()
        if (now - self._client_version_checked_at) < CLIENT_VERSION_REFRESH_TTL:
            return self.client_version

        try:
            response = self._request_with_retry(
                "GET",
                URL,
                request_name="update_client_version",
                timeout=20,
            )
            self._client_version_checked_at = now
            if response.status_code != 200:
                logger.debug(
                    f"Error with update_client_version: {response.status_code}"
                )
                return self.client_version
            matcher = re.search(self.twilight_build_id_pattern, response.text)
            if not matcher:
                logger.debug("Error with update_client_version: no match")
                return self.client_version
            self.client_version = matcher.group(1)
            logger.debug(f"Client version: {self.client_version}")
            return self.client_version
        except requests.exceptions.RequestException as e:
            if (now - self._last_client_version_error_log) >= CLIENT_VERSION_ERROR_LOG_TTL:
                logger.warning("Error with update_client_version: %s", e)
                self._last_client_version_error_log = now
            else:
                logger.debug("Error with update_client_version: %s", e)
            # Avoid retrying this request every single GQL call while Twitch is flaky.
            self._client_version_checked_at = now
            return self.client_version

    def _drop_progress_value(self, streamer):
        campaigns = getattr(streamer.stream, "campaigns", []) or []
        progress_values = []
        for campaign in campaigns:
            for drop in getattr(campaign, "drops", []) or []:
                if getattr(drop, "is_claimed", False) or getattr(drop, "dt_match", True) is False:
                    continue
                progress = getattr(drop, "percentage_progress", None)
                if progress is None:
                    continue
                progress_values.append(progress)
        if progress_values:
            return min(progress_values)
        return float("inf")

    def _points_limit_value(self, streamer) -> Optional[int]:
        settings = getattr(streamer, "settings", None)
        limit = getattr(settings, "points_limit", None) if settings is not None else None
        if limit in [None, ""]:
            return None
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError):
            return None
        return parsed_limit if parsed_limit >= 0 else None

    def _has_pending_watch_streak(self, streamer, now: float) -> bool:
        settings = getattr(streamer, "settings", None)
        if getattr(settings, "watch_streak", False) is not True:
            return False
        session = self._ensure_watch_streak_session(streamer, now)
        return self._session_is_eligible(session, streamer)

    def _streamer_has_reached_points_limit(self, streamer) -> bool:
        limit = self._points_limit_value(streamer)
        if limit is None:
            return False

        current_points = getattr(streamer, "channel_points", None)
        if current_points in [None, ""]:
            return False
        try:
            current_points = int(current_points)
        except (TypeError, ValueError):
            return False

        return current_points >= limit

    def _should_skip_streamer_for_points_limit(self, streamer, now: float) -> bool:
        if self._streamer_has_reached_points_limit(streamer) is False:
            return False

        return self._has_pending_watch_streak(streamer, now) is False

    def _select_capped_streak_streamers(self, streamers, streamers_index, now: float):
        capped_candidates = [
            idx
            for idx in streamers_index
            if self._streamer_has_reached_points_limit(streamers[idx])
        ]
        if not capped_candidates:
            return []
        return self._select_streak_streamers(
            streamers,
            capped_candidates,
            [Priority.STREAK],
            now,
        )

    # Apply the configured priorities in order; each one appends to the sort key so later priorities
    # only break ties from earlier ones (e.g., [STREAK, DROPS, ORDER] builds a tuple in that order).
    def _priority_sort_key(self, streamers, idx, priorities, order_map, now):
        streamer = streamers[idx]
        effective_priorities = priorities or [Priority.ORDER]
        key_parts = []
        for prior in effective_priorities:
            if prior == Priority.ORDER:
                key_parts.append(order_map.get(idx, idx))
            elif prior == Priority.POINTS_ASCENDING:
                points = (
                    streamer.channel_points
                    if streamer.channel_points is not None
                    else float("inf")
                )
                key_parts.append(points)
            elif prior == Priority.POINTS_DESCENDING:
                points = streamer.channel_points
                key_parts.append(-points if points is not None else float("inf"))
            elif prior == Priority.DROPS:
                drop_rank = 0 if streamer.drops_condition() else 1
                drop_progress = (
                    self._drop_progress_value(streamer) if drop_rank == 0 else float("inf")
                )
                key_parts.append((drop_rank, drop_progress))
            elif prior == Priority.SUBSCRIBED:
                sub_rank = 0 if streamer.viewer_has_points_multiplier() else 1
                points = (
                    streamer.channel_points
                    if streamer.channel_points is not None
                    else float("inf")
                )
                key_parts.append((sub_rank, points))
            elif prior == Priority.FAVORITE:
                favorite_rank = (
                    0 if getattr(streamer.settings, "favorite", False) is True else 1
                )
                # FAVORITE should only split favorite vs non-favorite groups.
                # Do not inject ORDER here; later priorities must still sort within each group.
                key_parts.append(favorite_rank)
            elif prior == Priority.STREAK:
                session = self._ensure_watch_streak_session(streamer, now)
                eligible = self._session_is_eligible(session, streamer)
                attempts = session.attempts if session is not None else float("inf")
                stream_created_at = (
                    streamer.stream.created_at
                    if getattr(streamer.stream, "created_at", None) is not None
                    else now
                )
                key_parts.append((0 if eligible else 1, attempts, stream_created_at))
            else:
                key_parts.append(0)
        return tuple(key_parts)

    def _priority_candidates(self, streamers, streamers_index, prior, now):
        if prior == Priority.ORDER:
            # Keep the provided configuration order unless ORDER is explicitly requested
            return list(streamers_index)

        if prior in [Priority.POINTS_ASCENDING, Priority.POINTS_DESCENDING]:
            return sorted(
                streamers_index,
                key=lambda x: streamers[x].channel_points,
                reverse=(prior == Priority.POINTS_DESCENDING),
            )

        if prior == Priority.FAVORITE:
            order_map = {idx: pos for pos, idx in enumerate(streamers_index)}
            favorites = [
                index
                for index in streamers_index
                if getattr(streamers[index].settings, "favorite", False) is True
            ]
            return sorted(favorites, key=lambda idx: order_map.get(idx, idx))

        if prior == Priority.STREAK:
            candidates = []
            for index in streamers_index:
                streamer = streamers[index]
                if streamer.settings.watch_streak is not True:
                    continue
                session = self._ensure_watch_streak_session(streamer, now)
                if not self._session_is_eligible(session, streamer):
                    continue
                candidates.append(index)
            return candidates

        if prior == Priority.DROPS:
            candidates = [
                index for index in streamers_index if streamers[index].drops_condition()
            ]
            order_map = {idx: pos for pos, idx in enumerate(streamers_index)}

            return sorted(
                candidates,
                key=lambda idx: (self._drop_progress_value(streamers[idx]), order_map.get(idx, idx)),
            )  # DROPS: prefer streams with lowest drop progress

        if prior == Priority.SUBSCRIBED:
            streamers_with_multiplier = [
                index
                for index in streamers_index
                if streamers[index].viewer_has_points_multiplier()
            ]
            order_map = {idx: pos for pos, idx in enumerate(streamers_index)}
            return sorted(
                streamers_with_multiplier,
                key=lambda idx: (
                    streamers[idx].channel_points
                    if streamers[idx].channel_points is not None
                    else float("inf"),
                    order_map.get(idx, idx),
                ),
            )  # SUBSCRIBED: prefer channels with lowest channel points

        return []

    def _select_streamers_to_watch(self, streamers, streamers_index, priority):
        now = time.time()
        eligible_streamers_index = [
            idx
            for idx in streamers_index
            if getattr(streamers[idx], "channel_points_enabled", True)
            and not getattr(streamers[idx], "chat_banned", False)
        ]
        if not eligible_streamers_index:
            return []

        forced_streak_selection = []
        if not priority or priority[0] != Priority.STREAK:
            forced_streak_selection = self._select_capped_streak_streamers(
                streamers, eligible_streamers_index, now
            )

        streamers_index = [
            idx
            for idx in eligible_streamers_index
            if idx not in forced_streak_selection
            and not self._should_skip_streamer_for_points_limit(streamers[idx], now)
        ]

        if not streamers_index and not forced_streak_selection:
            return []

        if priority and priority[0] != Priority.STREAK and (
            self._last_selection_was_streak or self._last_streak_selection
        ):
            self._last_selection_was_streak = False
            self._last_streak_selection = set()

        # If STREAK is the top priority, dedicate up to two streak sessions for short qualifying windows.
        if priority and priority[0] == Priority.STREAK:
            streak_selection = self._select_streak_streamers(streamers, streamers_index, priority, now)
            selection_names = {streamers[i].username for i in streak_selection}
            if selection_names != self._last_streak_selection:
                self._last_streak_selection = selection_names
            if streak_selection:
                self._last_selection_was_streak = True
                return streak_selection[: self.max_watch_amount]
            self._last_selection_was_streak = False
            start_index = 1
        else:
            start_index = 0

        remaining_priorities = priority[start_index:] if priority else []
        if not remaining_priorities:
            remaining_priorities = [Priority.ORDER]

        order_map = {idx: pos for pos, idx in enumerate(streamers_index)}
        sorted_candidates = sorted(
            streamers_index,
            key=lambda idx: self._priority_sort_key(
                streamers, idx, remaining_priorities, order_map, now
            ),
        )

        available_slots = max(0, self.max_watch_amount - len(forced_streak_selection))
        return forced_streak_selection + sorted_candidates[:available_slots]

    def _offline_gap_seconds(self, streamer) -> Optional[float]:
        if streamer.offline_at and streamer.online_at and streamer.online_at > streamer.offline_at:
            return streamer.online_at - streamer.offline_at
        return None

    def _resolve_broadcast_identity(self, streamer, now: float) -> tuple[str, float, bool]:
        broadcast_id = streamer.stream.broadcast_id
        started_at = streamer.online_at or now
        synthetic = False
        if broadcast_id is None:
            synthetic = True
            started_at = streamer.online_at or now
            started_iso = datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat()
            broadcast_id = f"{streamer.username}:{started_iso}"
        return broadcast_id, started_at, synthetic

    def _ensure_watch_streak_session(self, streamer, now: float) -> Optional[WatchStreakSession]:
        if self.watch_streak_cache is None:
            return None
        min_offline_for_new_streak = self._effective_streak_min_offline_seconds()
        broadcast_id, started_at, synthetic = self._resolve_broadcast_identity(streamer, now)
        offline_gap = self._offline_gap_seconds(streamer)
        latest_session = self.watch_streak_cache.latest_session_for_streamer(
            streamer.username, account_name=self.account_username
        )

        if (
            synthetic
            and offline_gap is not None
            and offline_gap < min_offline_for_new_streak
        ):
            if latest_session:
                broadcast_id = latest_session.broadcast_id
                started_at = latest_session.started_at

        if broadcast_id:
            self.watch_streak_cache.record_online(
                streamer.username,
                broadcast_id,
                streamer.online_at or now,
                account_name=self.account_username,
            )

        session = self.watch_streak_cache.get_session(
            streamer.username, broadcast_id, account_name=self.account_username
        )
        if session:
            return session

        if (
            latest_session
            and latest_session.broadcast_id == broadcast_id
            and offline_gap is not None
            and offline_gap < min_offline_for_new_streak
        ):
            return latest_session

        if not self.watch_streak_cache.should_create_session(
            streamer.username, account_name=self.account_username
        ):
            return None

        return self.watch_streak_cache.ensure_session(
            streamer.username,
            broadcast_id,
            started_at,
            account_name=self.account_username,
        )

    def _session_is_eligible(self, session: WatchStreakSession, streamer) -> bool:
        if session is None:
            return False
        if session.claimed or session.ended_at is not None:
            return False
        if session.attempts >= self.max_streak_attempts:
            return False
        if streamer.stream.watch_streak_missing is False:
            return False
        return True

    def _watch_reward_counter(self, streamer) -> int:
        watch_history = streamer.history.get("WATCH", {})
        if isinstance(watch_history, dict):
            return int(watch_history.get("counter", 0) or 0)
        return 0

    def _log_streak_start(self, session: WatchStreakSession):
        # Keep attempt-level streak flow quiet to avoid noisy logs on large accounts.
        return

    def _log_streak_claimed(self, session: WatchStreakSession, streamer=None):
        session_key = session.key()
        if session_key in self._streak_outcomes_logged:
            return
        self._streak_outcomes_logged.add(session_key)
        display_target = streamer if streamer is not None else session.streamer_login

        if self.watch_streak_cache is not None:
            streamer_login = session.streamer_login
            is_online = True
            broadcast_id = session.broadcast_id
            last_stream_started_at = None
            if streamer is not None:
                streamer_login = getattr(streamer, "username", streamer_login)
                is_online = bool(getattr(streamer, "is_online", True))
                streamer_stream = getattr(streamer, "stream", None)
                if streamer_stream is not None:
                    broadcast_id = getattr(streamer_stream, "broadcast_id", broadcast_id)
                    last_stream_started_at = getattr(
                        streamer_stream, "created_at", None
                    )
            self.watch_streak_cache.set_streamer_status(
                streamer_login,
                watch_streak_detected=True,
                is_online=is_online,
                last_stream_started_at=last_stream_started_at,
                broadcast_id=broadcast_id,
                checked_at=time.time(),
                account_name=self.account_username,
            )

        logger.info(
            "Detected WATCH_STREAK for %s",
            display_target,
            extra={"emoji": ":rocket:", "event": Events.GAIN_FOR_WATCH_STREAK},
        )

    def _log_streak_failed(self, session: WatchStreakSession):
        session_key = session.key()
        if session_key in self._streak_outcomes_logged:
            return
        self._streak_outcomes_logged.add(session_key)
        if self.watch_streak_cache is not None:
            self.watch_streak_cache.set_streamer_status(
                session.streamer_login,
                watch_streak_detected=False,
                is_online=True,
                broadcast_id=session.broadcast_id,
                checked_at=time.time(),
                account_name=self.account_username,
            )
        logger.info(
            "[STREAK] Exhausted for %s after %d attempts",
            session.streamer_login,
            session.attempts,
        )

    def _cleanup_streak_attempts(self, streamers, now: float):
        if self.watch_streak_cache is None:
            self._active_streak_attempts = {}
            return

        remaining: dict[str, ActiveWatchStreakAttempt] = {}
        for session_key, attempt in list(self._active_streak_attempts.items()):
            session = self.watch_streak_cache.get_session(
                attempt.streamer, attempt.broadcast_id, account_name=self.account_username
            )
            streamer_obj = next((s for s in streamers if s.username == attempt.streamer), None)

            if session is None or streamer_obj is None or streamer_obj.is_online is False:
                self.watch_streak_cache.mark_ended(
                    attempt.streamer,
                    attempt.broadcast_id,
                    ended_at=now,
                    account_name=self.account_username,
                )
                continue

            current_broadcast_id, _, _ = self._resolve_broadcast_identity(streamer_obj, now)
            if current_broadcast_id != attempt.broadcast_id:
                self.watch_streak_cache.mark_ended(
                    attempt.streamer,
                    attempt.broadcast_id,
                    ended_at=now,
                    account_name=self.account_username,
                )
                continue

            if session.claimed or streamer_obj.stream.watch_streak_missing is False:
                session = self.watch_streak_cache.mark_claimed(
                    attempt.streamer,
                    broadcast_id=attempt.broadcast_id,
                    now=now,
                    account_name=self.account_username,
                )
                self._log_streak_claimed(session, streamer_obj)
                continue

            watch_rewards_gained = (
                self._watch_reward_counter(streamer_obj) - attempt.watch_counter_at_start
            )
            if watch_rewards_gained >= self.streak_watch_events_target:
                # 2 WATCH rewards is a more reliable indicator than local watch-time estimates.
                streamer_obj.stream.watch_streak_missing = False
                self.watch_streak_cache.mark_ended(
                    attempt.streamer,
                    attempt.broadcast_id,
                    ended_at=now,
                    account_name=self.account_username,
                )
                logger.debug(
                    "[streak] %s inferred as completed after %d WATCH events for broadcast %s",
                    attempt.streamer,
                    watch_rewards_gained,
                    attempt.broadcast_id,
                )
                continue

            elapsed = now - attempt.started_at
            if elapsed < self.streak_attempt_timeout_seconds:
                remaining[session_key] = attempt
                continue

            session = self.watch_streak_cache.mark_attempt(
                attempt.streamer,
                attempt.broadcast_id,
                now,
                account_name=self.account_username,
                max_attempts=self.max_streak_attempts,
            )

            if session.attempts >= self.max_streak_attempts:
                self.watch_streak_cache.mark_ended(
                    attempt.streamer,
                    attempt.broadcast_id,
                    ended_at=now,
                    account_name=self.account_username,
                )
                self._log_streak_failed(session)
                continue

            # Attempt completed but session is still eligible; release the slot for another round later.
        self._active_streak_attempts = remaining

    def _select_streak_streamers(self, streamers, streamers_index, priority, now: float):
        self._cleanup_streak_attempts(streamers, now)

        active_selection: list[int] = []
        active_streamers = set()
        for attempt in self._active_streak_attempts.values():
            try:
                idx = next(i for i in streamers_index if streamers[i].username == attempt.streamer)
            except StopIteration:
                continue
            active_selection.append(idx)
            active_streamers.add(attempt.streamer)

        if len(active_selection) < self.max_streak_sessions:
            order_map = {idx: pos for pos, idx in enumerate(streamers_index)}
            streak_priorities = priority or [Priority.STREAK]
            candidates = []
            for idx in streamers_index:
                streamer = streamers[idx]
                session = self._ensure_watch_streak_session(streamer, now)
                if session is None or not self._session_is_eligible(session, streamer):
                    continue
                candidates.append(idx)

            sorted_candidates = sorted(
                candidates,
                key=lambda idx: self._priority_sort_key(
                    streamers, idx, streak_priorities, order_map, now
                ),
            )
            available_candidates = [
                idx
                for idx in sorted_candidates
                if streamers[idx].username not in active_streamers
            ]
            if available_candidates:
                offset = self._streak_rotation_cursor % len(available_candidates)
                rotated_candidates = (
                    available_candidates[offset:] + available_candidates[:offset]
                )
            else:
                rotated_candidates = []

            added_count = 0
            for idx in rotated_candidates:
                if len(active_selection) >= self.max_streak_sessions:
                    break
                streamer = streamers[idx]
                session = self._ensure_watch_streak_session(streamer, now)
                if session is None or not self._session_is_eligible(session, streamer):
                    continue
                attempt = ActiveWatchStreakAttempt(
                    session_key=session.key(),
                    streamer=streamer.username,
                    broadcast_id=session.broadcast_id,
                    started_at=now,
                    watch_counter_at_start=self._watch_reward_counter(streamer),
                )
                self._active_streak_attempts[session.key()] = attempt
                active_streamers.add(streamer.username)
                active_selection.append(idx)
                added_count += 1
                self._log_streak_start(session)

            if available_candidates:
                self._streak_rotation_cursor = (
                    self._streak_rotation_cursor + max(1, added_count)
                ) % len(available_candidates)

        return active_selection[: self.max_streak_sessions]

    def send_minute_watched_events(self, streamers, priority, chunk_size=3):
        while self.running:
            try:
                streamers_index = [
                    i
                    for i in range(0, len(streamers))
                    if streamers[i].is_online is True
                    and (
                        streamers[i].online_at == 0
                        or (time.time() - streamers[i].online_at) > 30
                    )
                ]

                for index in streamers_index:
                    if (streamers[index].stream.update_elapsed() / 60) > 10:
                        # Why this user It's currently online but the last updated was more than 10minutes ago?
                        # Please perform a manually update and check if the user it's online
                        self.check_streamer_online(streamers[index])

                """
                Normally we respect the 2-stream limit, but if any watch-streaks are pending
                we temporarily fan out (optionally capped by watch_streak_max_parallel)
                so each live streamer gets a shot.
                """
                self._refresh_selection_context(streamers, streamers_index, priority)
                streamers_watching = self._select_streamers_to_watch(
                    streamers, streamers_index, priority
                )

                drops_logging_enabled = Priority.DROPS in priority

                for index in streamers_watching:
                    # next_iteration = time.time() + 60 / len(streamers_watching)
                    next_iteration = time.time() + 20 / len(streamers_watching)

                    try:
                        ####################################
                        # Start of fix for 2024/5 API Change
                        # Create the JSON data for the GraphQL request
                        json_data = copy.deepcopy(
                            GQLOperations.PlaybackAccessToken)
                        json_data["variables"] = {
                            "login": streamers[index].username,
                            "isLive": True,
                            "isVod": False,
                            "vodID": "",
                            "playerType": "site"
                            # "playerType": "picture-by-picture",
                        }

                        # Get signature and value using the post_gql_request method
                        try:
                            responsePlaybackAccessToken = self.post_gql_request(
                                json_data)
                            logger.debug(
                                f"Sent PlaybackAccessToken request for {streamers[index]}")

                            if 'data' not in responsePlaybackAccessToken:
                                self._log_watch_issue(
                                    streamers[index].username,
                                    "invalid_playback_access_token",
                                    "Invalid PlaybackAccessToken response for %s: %s",
                                    streamers[index].username,
                                    responsePlaybackAccessToken,
                                )
                                continue

                            streamPlaybackAccessToken = responsePlaybackAccessToken["data"].get(
                                'streamPlaybackAccessToken', {})
                            signature = streamPlaybackAccessToken.get(
                                "signature")
                            value = streamPlaybackAccessToken.get("value")

                            if not signature or not value:
                                self._log_watch_issue(
                                    streamers[index].username,
                                    "missing_playback_signature_or_value",
                                    "Missing signature/value in PlaybackAccessToken response for %s",
                                    streamers[index].username,
                                )
                                continue

                        except Exception as e:
                            self._log_watch_issue(
                                streamers[index].username,
                                "playback_access_token_exception",
                                "Error fetching PlaybackAccessToken for %s: %s",
                                streamers[index],
                                str(e),
                            )
                            continue

                        # encoded_value = quote(json.dumps(value))

                        # Construct the URL for the broadcast qualities
                        RequestBroadcastQualitiesURL = f"https://usher.ttvnw.net/api/channel/hls/{streamers[index].username}.m3u8?sig={signature}&token={value}"

                        # Get list of video qualities
                        responseBroadcastQualities = self._request_with_retry(
                            "GET",
                            RequestBroadcastQualitiesURL,
                            request_name=f"broadcast_qualities:{streamers[index].username}",
                            headers={"User-Agent": self.user_agent},
                            timeout=20,
                        )  # timeout=60
                        logger.debug(
                            f"Send RequestBroadcastQualitiesURL request for {streamers[index]} - Status code: {responseBroadcastQualities.status_code}"
                        )
                        if responseBroadcastQualities.status_code != 200:
                            continue
                        BroadcastQualities = responseBroadcastQualities.text

                        # Just takes the last line, which should be the URL for the lowest quality
                        BroadcastLowestQualityURL = BroadcastQualities.split(
                            "\n")[-1]
                        if not validators.url(BroadcastLowestQualityURL):
                            continue

                        # Get list of video URLs
                        responseStreamURLList = self._request_with_retry(
                            "GET",
                            BroadcastLowestQualityURL,
                            request_name=f"stream_url_list:{streamers[index].username}",
                            headers={"User-Agent": self.user_agent},
                            timeout=20,
                        )  # timeout=60
                        logger.debug(
                            f"Send BroadcastLowestQualityURL request for {streamers[index]} - Status code: {responseStreamURLList.status_code}"
                        )
                        if responseStreamURLList.status_code != 200:
                            continue
                        StreamURLList = responseStreamURLList.text

                        # Just takes the last line, which should be the URL for the lowest quality
                        StreamLowestQualityURL = StreamURLList.split("\n")[-2]
                        if not validators.url(StreamLowestQualityURL):
                            continue

                        # Perform a HEAD request to simulate watching the stream
                        responseStreamLowestQualityURL = self._request_with_retry(
                            "HEAD",
                            StreamLowestQualityURL,
                            request_name=f"stream_lowest_quality_head:{streamers[index].username}",
                            headers={"User-Agent": self.user_agent},
                            timeout=20,
                        )  # timeout=60
                        logger.debug(
                            f"Send StreamLowestQualityURL request for {streamers[index]} - Status code: {responseStreamLowestQualityURL.status_code}"
                        )
                        if responseStreamLowestQualityURL.status_code != 200:
                            continue
                        # End of fix for 2024/5 API Change
                        ##################################
                        response = self._request_with_retry(
                            "POST",
                            streamers[index].stream.spade_url,
                            request_name=f"minute_watched:{streamers[index].username}",
                            data=streamers[index].stream.encode_payload(),
                            headers={"User-Agent": self.user_agent},
                            # timeout=60,
                            timeout=20,
                        )
                        logger.debug(
                            f"Send minute watched request for {streamers[index]} - Status code: {response.status_code}"
                        )
                        if response.status_code == 204:
                            streamers[index].stream.update_minute_watched()

                            """
                            Remember, you can only earn progress towards a time-based Drop on one participating channel at a time.  [ ! ! ! ]
                            You can also check your progress towards Drops within a campaign anytime by viewing the Drops Inventory.
                            For time-based Drops, if you are unable to claim the Drop in time, you will be able to claim it from the inventory page until the Drops campaign ends.
                            """

                            for campaign in streamers[index].stream.campaigns:
                                for drop in campaign.drops:
                                    self._log_drop_progress(streamers[index], drop, drops_logging_enabled)

                    except requests.exceptions.ConnectionError as e:
                        self._log_watch_issue(
                            streamers[index].username,
                            "send_minute_watched_connection_error",
                            "Error while trying to send minute watched for %s: %s",
                            streamers[index].username,
                            e,
                        )
                        self.__check_connection_handler(chunk_size)
                    except requests.exceptions.Timeout as e:
                        self._log_watch_issue(
                            streamers[index].username,
                            "send_minute_watched_timeout",
                            "Timeout while trying to send minute watched for %s: %s",
                            streamers[index].username,
                            e,
                        )

                    self.__chuncked_sleep(
                        next_iteration - time.time(), chunk_size=chunk_size
                    )

                if streamers_watching == []:
                    # self.__chuncked_sleep(60, chunk_size=chunk_size)
                    self.__chuncked_sleep(20, chunk_size=chunk_size)
            except Exception:
                logger.error(
                    "Exception raised in send minute watched", exc_info=True)

    # === CHANNEL POINTS / PREDICTION === #
    def _refresh_selection_context(self, streamers, streamers_index, priority):
        if Priority.SUBSCRIBED not in (priority or []):
            return

        now = time.time()
        for index in streamers_index:
            streamer = streamers[index]
            last_refresh = getattr(streamer, "channel_points_context_at", 0.0) or 0.0
            if last_refresh and (now - last_refresh) < SUBSCRIPTION_CONTEXT_REFRESH_SECONDS:
                continue
            try:
                self.load_channel_points_context(streamer)
            except Exception:
                logger.debug(
                    "Failed to refresh subscription context for %s during selection",
                    streamer.username,
                    exc_info=True,
                )

    # Load the amount of current points for a channel, check if a bonus is available
    def load_channel_points_context(self, streamer):
        json_data = copy.deepcopy(GQLOperations.ChannelPointsContext)
        json_data["variables"] = {"channelLogin": streamer.username}

        response = self.post_gql_request(json_data)
        if not response or self._log_gql_errors(json_data.get("operationName"), response):
            return
        try:
            channel = response["data"]["community"]["channel"]
        except (KeyError, TypeError):
            raise StreamerDoesNotExistException

        if channel is None:
            raise StreamerDoesNotExistException

        streamer.channel_points_context_at = time.time()

        community_points = (
            channel.get("self", {}).get("communityPoints")
            if isinstance(channel, dict)
            else None
        )
        community_points_settings = (
            channel.get("communityPointsSettings")
            if isinstance(channel, dict)
            else None
        )
        if isinstance(community_points_settings, dict):
            is_enabled = community_points_settings.get("isEnabled")
            if isinstance(is_enabled, bool):
                streamer.channel_points_enabled = is_enabled
        if community_points is None:
            return

        streamer.channel_points = community_points.get("balance", streamer.channel_points)
        streamer.activeMultipliers = community_points.get("activeMultipliers")
        streamer.subscription_tier = None
        try:
            self_info = channel.get("self", {}) if isinstance(channel, dict) else {}
            sub_benefit = (
                self_info.get("subscriptionBenefit")
                if isinstance(self_info, dict)
                else None
            )
            if isinstance(sub_benefit, dict):
                tier = sub_benefit.get("tier")
                if tier is not None:
                    streamer.subscription_tier = tier
            if streamer.subscription_tier is None and streamer.viewer_has_points_multiplier():
                streamer.subscription_tier = 1
        except Exception:
            pass

        if streamer.settings.community_goals is True:
            goals = channel.get("communityPointsSettings", {}).get("goals", [])
            streamer.community_goals = {
                goal["id"]: CommunityGoal.from_gql(goal)
                for goal in goals
                if isinstance(goal, dict) and "id" in goal
            }

        available_claim = community_points.get("availableClaim")
        if available_claim is not None and isinstance(available_claim, dict):
            self.claim_bonus(streamer, available_claim.get("id"))

        if streamer.settings.community_goals is True:
            self.contribute_to_community_goals(streamer)

    def initialize_streamers_context(self, streamers, max_workers=10):
        if not streamers:
            return set()

        failed_streamers = set()

        def _load_streamer_context(streamer):
            time.sleep(random.uniform(0.15, 0.35))
            self.load_channel_points_context(streamer)
            self.check_streamer_online(streamer)

        # Initialize channel context in parallel so large streamer lists do not block startup
        workers = max(1, min(max_workers, len(streamers)))
        timeout_seconds = STREAMER_INIT_TIMEOUT_PER_STREAMER * len(streamers)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_load_streamer_context, streamer): streamer
                for streamer in streamers
            }
            try:
                for future in as_completed(futures, timeout=timeout_seconds):
                    streamer = futures[future]
                    try:
                        future.result()
                    except StreamerDoesNotExistException:
                        failed_streamers.add(streamer.username)
                        logger.info(
                            f"Streamer {streamer.username} does not exist",
                            extra={"emoji": ":cry:"},
                        )
                    except Exception:
                        failed_streamers.add(streamer.username)
                        logger.error(
                            f"Failed to initialize streamer {streamer.username}",
                            exc_info=True,
                        )
            except TimeoutError:
                logger.error(
                    "Timed out while initializing streamers after %s seconds.",
                    timeout_seconds,
                )
                for future, streamer in futures.items():
                    if not future.done():
                        failed_streamers.add(streamer.username)
        return failed_streamers

    def make_predictions(self, event):
        decision = event.bet.calculate(event.streamer.channel_points)
        # selector_index = 0 if decision["choice"] == "A" else 1

        logger.info(
            f"Going to complete bet for {event}",
            extra={
                "emoji": ":four_leaf_clover:",
                "event": Events.BET_GENERAL,
            },
        )
        if event.status == "ACTIVE":
            skip, compared_value = event.bet.skip()
            if skip is True:
                logger.info(
                    f"Skip betting for the event {event}",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )
                logger.info(
                    f"Skip settings {event.bet.settings.filter_condition}, current value is: {compared_value}",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )
            else:
                if decision["amount"] >= 10:
                    logger.info(
                        # f"Place {_millify(decision['amount'])} channel points on: {event.bet.get_outcome(selector_index)}",
                        f"Place {_millify(decision['amount'])} channel points on: {event.bet.get_outcome(decision['choice'])}",
                        extra={
                            "emoji": ":four_leaf_clover:",
                            "event": Events.BET_GENERAL,
                        },
                    )

                    json_data = copy.deepcopy(GQLOperations.MakePrediction)
                    json_data["variables"] = {
                        "input": {
                            "eventID": event.event_id,
                            "outcomeID": decision["id"],
                            "points": decision["amount"],
                            "transactionID": token_hex(16),
                        }
                    }
                    response = self.post_gql_request(json_data)
                    if (
                        "data" in response
                        and "makePrediction" in response["data"]
                        and "error" in response["data"]["makePrediction"]
                        and response["data"]["makePrediction"]["error"] is not None
                    ):
                        error_code = response["data"]["makePrediction"]["error"]["code"]
                        logger.error(
                            f"Failed to place bet, error: {error_code}",
                            extra={
                                "emoji": ":four_leaf_clover:",
                                "event": Events.BET_FAILED,
                            },
                        )
                else:
                    logger.info(
                        f"Bet won't be placed as the amount {_millify(decision['amount'])} is less than the minimum required 10",
                        extra={
                            "emoji": ":four_leaf_clover:",
                            "event": Events.BET_GENERAL,
                        },
                    )
        else:
            logger.info(
                f"Oh no! The event is not active anymore! Current status: {event.status}",
                extra={
                    "emoji": ":disappointed_relieved:",
                    "event": Events.BET_FAILED,
                },
            )

    def claim_bonus(self, streamer, claim_id):
        if Settings.logger.less is False:
            logger.info(
                f"Claiming the bonus for {streamer}!",
                extra={"emoji": ":gift:", "event": Events.BONUS_CLAIM},
            )

        json_data = copy.deepcopy(GQLOperations.ClaimCommunityPoints)
        json_data["variables"] = {
            "input": {"channelID": streamer.channel_id, "claimID": claim_id}
        }
        self.post_gql_request(json_data)

    # === MOMENTS === #
    def claim_moment(self, streamer, moment_id):
        if Settings.logger.less is False:
            logger.info(
                f"Claiming the moment for {streamer}!",
                extra={"emoji": ":video_camera:",
                       "event": Events.MOMENT_CLAIM},
            )

        json_data = copy.deepcopy(GQLOperations.CommunityMomentCallout_Claim)
        json_data["variables"] = {"input": {"momentID": moment_id}}
        self.post_gql_request(json_data)

    # === CAMPAIGNS / DROPS / INVENTORY === #
    def __get_campaign_ids_from_streamer(self, streamer):
        json_data = copy.deepcopy(
            GQLOperations.DropsHighlightService_AvailableDrops)
        json_data["variables"] = {"channelID": streamer.channel_id}
        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            return []
        channel = (
            response.get("data", {}).get("channel", {})
            if isinstance(response, dict)
            else {}
        )
        campaigns = (
            channel.get("viewerDropCampaigns") if isinstance(channel, dict) else None
        )
        if not campaigns:
            return []
        ids = []
        for item in campaigns:
            if isinstance(item, dict) and "id" in item:
                ids.append(item["id"])
        return ids

    def __get_inventory(self):
        json_data = GQLOperations.Inventory
        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            return {}
        if not isinstance(response, dict):
            return {}
        return (
            response.get("data", {})
            .get("currentUser", {})
            .get("inventory", {})
            or {}
        )

    def __get_drops_dashboard(self, status=None):
        json_data = GQLOperations.ViewerDropsDashboard
        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            return []
        campaigns = (
            response.get("data", {})
            .get("currentUser", {})
            .get("dropCampaigns", [])
            if isinstance(response, dict)
            else []
        ) or []

        if status is not None:
            campaigns = (
                list(filter(lambda x: x["status"] == status.upper(), campaigns)) or []
            )

        return campaigns

    def __get_campaigns_details(self, campaigns):
        result = []
        chunks = create_chunks(campaigns, 20)
        for chunk in chunks:
            json_data = []
            for campaign in chunk:
                json_data.append(copy.deepcopy(
                    GQLOperations.DropCampaignDetails))
                json_data[-1]["variables"] = {
                    "dropID": campaign["id"],
                    "channelLogin": f"{self.twitch_login.get_user_id()}",
                }

            response = self.post_gql_request(json_data)
            if not isinstance(response, list):
                logger.debug("Unexpected campaigns response format, skipping chunk")
                continue
            operation_name = (
                json_data[0].get("operationName") if json_data else "DropCampaignDetails"
            )
            for r in response:
                if self._log_gql_errors(operation_name, r):
                    continue
                drop_campaign = (
                    r.get("data", {}).get("user", {}).get("dropCampaign", None)
                    if isinstance(r, dict)
                    else None
                )
                if drop_campaign is not None:
                    result.append(drop_campaign)
        return result

    def __sync_campaigns(self, campaigns):
        # We need the inventory only for get the real updated value/progress
        logger.debug("Fetching drop inventory for sync")
        inventory = self.__get_inventory()
        if not isinstance(inventory, dict):
            return campaigns
        campaigns_in_progress = inventory.get("dropCampaignsInProgress") or []
        if not campaigns_in_progress:
            return campaigns

        for i in range(len(campaigns)):
            for progress in campaigns_in_progress:
                if progress.get("id") != campaigns[i].id:
                    continue
                campaigns[i].in_inventory = True
                time_based = progress.get("timeBasedDrops") or []
                campaigns[i].sync_drops(time_based, self.claim_drop)
                logger.debug(
                    "Updated drop progress for campaign %s with %d timeBasedDrops",
                    campaigns[i].id,
                    len(time_based),
                )
                campaigns[i].clear_drops()  # Clean up claimed/expired after sync
                break
        return campaigns

    def claim_drop(self, drop):
        logger.info(
            f"Claim {drop}", extra={"emoji": ":package:", "event": Events.DROP_CLAIM}
        )

        json_data = copy.deepcopy(GQLOperations.DropsPage_ClaimDropRewards)
        json_data["variables"] = {
            "input": {"dropInstanceID": drop.drop_instance_id}}
        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            return False
        data = response.get("data", {}) if isinstance(response, dict) else {}
        claim_result = data.get("claimDropRewards") if isinstance(data, dict) else None
        if claim_result is None:
            return False
        status = claim_result.get("status") if isinstance(claim_result, dict) else None
        return status in ["ELIGIBLE_FOR_ALL", "DROP_INSTANCE_ALREADY_CLAIMED"]

    def claim_all_drops_from_inventory(self):
        inventory = self.__get_inventory()
        if inventory not in [None, {}]:
            if inventory["dropCampaignsInProgress"] not in [None, {}]:
                for campaign in inventory["dropCampaignsInProgress"]:
                    for drop_dict in campaign["timeBasedDrops"]:
                        drop = Drop(drop_dict)
                        drop.update(drop_dict["self"])
                        if drop.is_claimable is True:
                            drop.is_claimed = self.claim_drop(drop)
                            time.sleep(random.uniform(5, 10))

    def __streamers_require_campaign_sync(self, streamers):
        # Run drop sync whenever at least one online streamer has drops enabled,
        # even if campaign details are not yet loaded (avoid chicken-and-egg).
        return any(
            streamer.settings.claim_drops is True and streamer.is_online is True
            for streamer in streamers
        )

    def sync_campaigns(self, streamers, chunk_size=3):
        campaigns_update = 0
        campaigns = []
        while self.running:
            try:
                # Skip the expensive dashboard sync loop when no streamer can currently farm drops
                if not self.__streamers_require_campaign_sync(streamers):
                    campaigns = []
                    self.__chuncked_sleep(60, chunk_size=chunk_size)
                    continue
                # Get update from dashboard each 60minutes
                if (
                    campaigns_update == 0
                    # or ((time.time() - campaigns_update) / 60) > 60
                    # TEMPORARY AUTO DROP CLAIMING FIX
                    # 30 minutes instead of 60 minutes
                    or ((time.time() - campaigns_update) / 30) > 30
                    #####################################
                ):
                    campaigns_update = time.time()

                    # TEMPORARY AUTO DROP CLAIMING FIX
                    self.claim_all_drops_from_inventory()
                    #####################################

                    # Get full details from current ACTIVE campaigns
                    # Use dashboard so we can explore new drops not currently active in our Inventory
                    campaigns_details = self.__get_campaigns_details(
                        self.__get_drops_dashboard(status="ACTIVE")
                    )
                    campaigns = []

                    # Going to clear array and structure. Remove all the timeBasedDrops expired or not started yet
                    for index in range(0, len(campaigns_details)):
                        if campaigns_details[index] is not None:
                            campaign = Campaign(campaigns_details[index])
                            if campaign.dt_match is True:
                                # Remove all the drops already claimed or with dt not matching
                                campaign.clear_drops()
                                if campaign.drops != []:
                                    campaigns.append(campaign)
                        else:
                            continue

                # Divide et impera :)
                campaigns = self.__sync_campaigns(campaigns)

                # Check if user It's currently streaming the same game present in campaigns_details
                for i in range(0, len(streamers)):
                    if streamers[i].drops_condition() is True:
                        # yes! The streamer[i] have the drops_tags enabled and we It's currently stream a game with campaign active!
                        # With 'campaigns_ids' we are also sure that this streamer have the campaign active.
                        # yes! The streamer[index] have the drops_tags enabled and we It's currently stream a game with campaign active!
                        streamers[i].stream.campaigns = list(
                            filter(
                                lambda x: x.drops != []
                                and x.game == streamers[i].stream.game
                                and x.id in streamers[i].stream.campaigns_ids,
                                campaigns,
                            )
                        )

            except (ValueError, KeyError, requests.exceptions.ConnectionError) as e:
                logger.error(f"Error while syncing inventory: {e}")
                campaigns = []
                self.__check_connection_handler(chunk_size)

            self.__chuncked_sleep(60, chunk_size=chunk_size)

    def contribute_to_community_goals(self, streamer):
        # Don't bother doing the request if no goal is currently started or in stock
        if any(
            goal.status == "STARTED" and goal.is_in_stock
            for goal in streamer.community_goals.values()
        ):
            json_data = copy.deepcopy(GQLOperations.UserPointsContribution)
            json_data["variables"] = {"channelLogin": streamer.username}
            response = self.post_gql_request(json_data)
            if self._log_gql_errors(json_data.get("operationName"), response):
                return
            data = response.get("data", {}) if isinstance(response, dict) else {}
            user_goal_contributions = (
                data.get("user", {})
                .get("channel", {})
                .get("self", {})
                .get("communityPoints", {})
                .get("goalContributions", [])
            )
            if not user_goal_contributions:
                return

            logger.debug(
                f"Found {len(user_goal_contributions)} community goals for the current stream"
            )

            for goal_contribution in user_goal_contributions:
                goal_id = goal_contribution["goal"]["id"]
                goal = streamer.community_goals[goal_id]
                if goal is None:
                    # TODO should this trigger a new load context request
                    logger.error(
                        f"Unable to find context data for community goal {goal_id}"
                    )
                else:
                    user_stream_contribution = goal_contribution[
                        "userPointsContributedThisStream"
                    ]
                    user_left_to_contribute = (
                        goal.per_stream_user_maximum_contribution
                        - user_stream_contribution
                    )
                    amount = min(
                        goal.amount_left(),
                        user_left_to_contribute,
                        streamer.channel_points,
                    )
                    if amount > 0:
                        self.contribute_to_community_goal(
                            streamer, goal_id, goal.title, amount
                        )
                    else:
                        logger.debug(
                            f"Not contributing to community goal {goal.title}, user channel points {streamer.channel_points}, user stream contribution {user_stream_contribution}, all users total contribution {goal.points_contributed}"
                        )

    def contribute_to_community_goal(self, streamer, goal_id, title, amount):
        json_data = copy.deepcopy(
            GQLOperations.ContributeCommunityPointsCommunityGoal)
        json_data["variables"] = {
            "input": {
                "amount": amount,
                "channelID": streamer.channel_id,
                "goalID": goal_id,
                "transactionID": token_hex(16),
            }
        }

        response = self.post_gql_request(json_data)
        if self._log_gql_errors(json_data.get("operationName"), response):
            return

        contribution = (
            response.get("data", {}).get("contributeCommunityPointsCommunityGoal", {})
            if isinstance(response, dict)
            else {}
        )
        error = contribution.get("error") if isinstance(contribution, dict) else None
        if error:
            logger.error(
                f"Unable to contribute channel points to community goal '{title}', reason '{error}'"
            )
            return

        logger.info(f"Contributed {amount} channel points to community goal '{title}'")
        streamer.channel_points -= amount
