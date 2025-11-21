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
from typing import Dict, Any
# from urllib.parse import quote
# from base64 import urlsafe_b64decode
# from datetime import datetime

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
from TwitchChannelPointsMiner.watch_streak_cache import WATCH_STREAK_CACHE_TTL_SECONDS
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


class Twitch(object):
    __slots__ = [
        "cookies_file",
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
    ]

    def __init__(self, username, user_agent, password=None):
        cookies_path = os.path.join(Path().absolute(), "cookies")
        Path(cookies_path).mkdir(parents=True, exist_ok=True)
        self.cookies_file = os.path.join(cookies_path, f"{username}.pkl")
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
            )
        except (KeyError, TypeError):
            logger.debug("Invalid stream info for %s", streamer.username)
            return False

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

            main_page_request = requests.get(
                streamer.streamer_url, headers=headers)
            response = main_page_request.text
            # logger.info(response)
            regex_settings = "(https://static.twitchcdn.net/config/settings.*?js|https://assets.twitch.tv/config/settings.*?.js)"
            settings_url = re.search(regex_settings, response).group(1)

            settings_request = requests.get(settings_url, headers=headers)
            response = settings_request.text
            regex_spade = '"spade_url":"(.*?)"'
            streamer.stream.spade_url = re.search(
                regex_spade, response).group(1)
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

    def get_followers(
        self, limit: int = 100, order: FollowersOrder = FollowersOrder.ASC
    ):
        json_data = copy.deepcopy(GQLOperations.ChannelFollows)
        json_data["variables"] = {"limit": limit, "order": str(order)}
        has_next = True
        last_cursor = ""
        follows = []
        while has_next is True:
            json_data["variables"]["cursor"] = last_cursor
            json_response = self.post_gql_request(json_data)
            if self._log_gql_errors(json_data.get("operationName"), json_response):
                return follows
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

    def _log_gql_errors(self, operation_name, response):
        if not isinstance(response, dict):
            return False
        errors = response.get("errors") or []
        if errors in [[], None]:
            return False
        messages = []
        for error in errors:
            if isinstance(error, dict):
                messages.append(error.get("message", str(error)))
            else:
                messages.append(str(error))
        message = "; ".join(messages) if messages else "Unknown GQL error"
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

    def _get_cached_stream_info(self, cache_key, now):
        cached_entry = self._stream_info_cache.get(cache_key)
        if cached_entry and (now - cached_entry["timestamp"]) <= STREAM_INFO_CACHE_TTL:
            return cached_entry["data"]
        return None

    def _invalidate_stream_info_cache(self, cache_key):
        self._stream_info_cache.pop(cache_key, None)

    def post_gql_request(self, json_data):
        try:
            response = requests.post(
                GQLOperations.url,
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
            )
            logger.debug(
                f"Data: {json_data}, Status code: {response.status_code}, Content: {response.text}"
            )
            try:
                return response.json()
            except ValueError:
                operation_name = (
                    json_data.get("operationName")
                    if isinstance(json_data, dict)
                    else "UnknownOperation"
                )
                logger.warning(
                    "Invalid JSON response for %s (status %s)", operation_name, response.status_code
                )
                return {}
        except requests.exceptions.RequestException as e:
            operation_name = (
                json_data.get("operationName")
                if isinstance(json_data, dict)
                else "UnknownOperation"
            )
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
        try:
            response = requests.get(URL)
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
            logger.error(f"Error with update_client_version: {e}")
            return self.client_version

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

        if prior == Priority.STREAK:
            candidates = []
            for index in streamers_index:
                streamer = streamers[index]
                if (
                    streamer.settings.watch_streak is True
                    and streamer.stream.watch_streak_missing is True
                    and (
                        streamer.offline_at == 0
                        or ((now - streamer.offline_at) // 60) > 30
                    )
                    and streamer.stream.minute_watched < 7
                ):
                    if self.watch_streak_cache is not None and self.watch_streak_cache.was_streak_claimed_recently(
                        streamer.username, now, WATCH_STREAK_CACHE_TTL_SECONDS
                    ):
                        continue
                    candidates.append(index)
            return candidates

        if prior == Priority.DROPS:
            return [
                index for index in streamers_index if streamers[index].drops_condition()
            ]

        if prior == Priority.SUBSCRIBED:
            streamers_with_multiplier = [
                index
                for index in streamers_index
                if streamers[index].viewer_has_points_multiplier()
            ]
            return sorted(
                streamers_with_multiplier,
                key=lambda x: streamers[x].total_points_multiplier(),
                reverse=True,
            )

        return []

    def _select_streamers_to_watch(self, streamers, streamers_index, priority):
        max_watch_amount = 2
        streamers_watching = []
        now = time.time()

        for prior in priority:
            if len(streamers_watching) >= max_watch_amount:
                break
            candidates = self._priority_candidates(streamers, streamers_index, prior, now)
            for index in candidates:
                if index in streamers_watching:
                    continue
                streamers_watching.append(index)
                if len(streamers_watching) >= max_watch_amount:
                    break

        return streamers_watching[:max_watch_amount]

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
                Twitch has a limit - you can't watch more than 2 channels at one time.
                We'll take the first two streamers from the final list as they have the highest priority.
                """
                streamers_watching = self._select_streamers_to_watch(
                    streamers, streamers_index, priority
                )

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
                                logger.error(
                                    f"Invalid response from Twitch: {responsePlaybackAccessToken}")
                                continue

                            streamPlaybackAccessToken = responsePlaybackAccessToken["data"].get(
                                'streamPlaybackAccessToken', {})
                            signature = streamPlaybackAccessToken.get(
                                "signature")
                            value = streamPlaybackAccessToken.get("value")

                            if not signature or not value:
                                logger.error(
                                    f"Missing signature or value in Twitch response: {responsePlaybackAccessToken}")
                                continue

                        except Exception as e:
                            logger.error(
                                f"Error fetching PlaybackAccessToken for {streamers[index]}: {str(e)}")
                            continue

                        # encoded_value = quote(json.dumps(value))

                        # Construct the URL for the broadcast qualities
                        RequestBroadcastQualitiesURL = f"https://usher.ttvnw.net/api/channel/hls/{streamers[index].username}.m3u8?sig={signature}&token={value}"

                        # Get list of video qualities
                        responseBroadcastQualities = requests.get(
                            RequestBroadcastQualitiesURL,
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
                        responseStreamURLList = requests.get(
                            BroadcastLowestQualityURL,
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
                        responseStreamLowestQualityURL = requests.head(
                            StreamLowestQualityURL,
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
                        response = requests.post(
                            streamers[index].stream.spade_url,
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
                                    # We could add .has_preconditions_met condition inside is_printable
                                    if (
                                        drop.has_preconditions_met is not False
                                        and drop.is_printable is True
                                    ):
                                        drop_messages = [
                                            f"{streamers[index]} is streaming {streamers[index].stream}",
                                            f"Campaign: {campaign}",
                                            f"Drop: {drop}",
                                            f"{drop.progress_bar()}",
                                        ]
                                        for single_line in drop_messages:
                                            logger.info(
                                                single_line,
                                                extra={
                                                    "event": Events.DROP_STATUS,
                                                    "skip_telegram": True,
                                                    "skip_discord": True,
                                                    "skip_webhook": True,
                                                    "skip_matrix": True,
                                                    "skip_gotify": True
                                                },
                                            )

                                        if Settings.logger.telegram is not None:
                                            Settings.logger.telegram.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )

                                        if Settings.logger.discord is not None:
                                            Settings.logger.discord.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )
                                        if Settings.logger.webhook is not None:
                                            Settings.logger.webhook.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )
                                        if Settings.logger.gotify is not None:
                                            Settings.logger.gotify.send(
                                                "\n".join(drop_messages),
                                                Events.DROP_STATUS,
                                            )

                    except requests.exceptions.ConnectionError as e:
                        logger.error(
                            f"Error while trying to send minute watched: {e}")
                        self.__check_connection_handler(chunk_size)
                    except requests.exceptions.Timeout as e:
                        logger.error(
                            f"Error while trying to send minute watched: {e}")

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

        community_points = (
            channel.get("self", {}).get("communityPoints")
            if isinstance(channel, dict)
            else None
        )
        if community_points is None:
            return

        streamer.channel_points = community_points.get("balance", streamer.channel_points)
        streamer.activeMultipliers = community_points.get("activeMultipliers")

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
        # Get data from inventory and sync current status with streamers.campaigns
        inventory = self.__get_inventory()
        if inventory not in [None, {}] and inventory["dropCampaignsInProgress"] not in [
            None,
            {},
        ]:
            # Iterate all campaigns from dashboard (only active, with working drops)
            # In this array we have also the campaigns never started from us (not in nventory)
            for i in range(len(campaigns)):
                campaigns[i].clear_drops()  # Remove all the claimed drops
                # Iterate all campaigns currently in progress from out inventory
                for progress in inventory["dropCampaignsInProgress"]:
                    if progress["id"] == campaigns[i].id:
                        campaigns[i].in_inventory = True
                        campaigns[i].sync_drops(
                            progress["timeBasedDrops"], self.claim_drop
                        )
                        # Remove all the claimed drops
                        campaigns[i].clear_drops()
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
        return any(streamer.drops_condition() for streamer in streamers)

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


def _self_check_priority_selection():
    from TwitchChannelPointsMiner.classes.entities.Streamer import (
        Streamer,
        StreamerSettings,
    )
    from TwitchChannelPointsMiner.watch_streak_cache import WatchStreakCache

    twitch = Twitch("self-check", "ua")
    twitch.watch_streak_cache = WatchStreakCache()
    priorities = [Priority.STREAK, Priority.SUBSCRIBED, Priority.POINTS_ASCENDING]

    def make_streamer(name, points, subscribed=False, watch_streak=True):
        settings = StreamerSettings(
            watch_streak=watch_streak,
            claim_drops=False,
            claim_moments=False,
            make_predictions=False,
            follow_raid=False,
            community_goals=False,
        )
        streamer = Streamer(name, settings=settings)
        streamer.channel_points = points
        streamer.activeMultipliers = [{"factor": 2.0}] if subscribed else None
        streamer.stream.watch_streak_missing = watch_streak
        return streamer

    streamers = [
        make_streamer("subscribed_low", 10, subscribed=True, watch_streak=True),
        make_streamer("other_low", 100, watch_streak=False),
        make_streamer("other_high", 200, watch_streak=False),
    ]
    streamers_index = list(range(len(streamers)))
    selection = twitch._select_streamers_to_watch(
        streamers, streamers_index, priorities
    )
    assert len(selection) == 2, "Expected two watch slots to be filled"
    assert (
        streamers[selection[0]].username == "subscribed_low"
    ), "Subscribed lowest-points streamer should take slot 1"
    assert (
        streamers[selection[1]].username == "other_low"
    ), "Next best by points should take slot 2"
    print("Priority selection self-check passed.")


if __name__ == "__main__":
    _self_check_priority_selection()
