import json
import logging
import os
import time
from datetime import datetime
from threading import Lock

from TwitchChannelPointsMiner.classes.Chat import ChatPresence, ThreadChat
from TwitchChannelPointsMiner.classes.entities.Bet import BetSettings, DelayMode
from TwitchChannelPointsMiner.classes.entities.Stream import Stream
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.constants import URL
from TwitchChannelPointsMiner.utils import _millify

logger = logging.getLogger(__name__)


class StreamerSettings(object):
    __slots__ = [
        "make_predictions",
        "follow_raid",
        "claim_drops",
        "claim_moments",
        "watch_streak",
        "favorite",
        "points_limit",
        "community_goals",
        "bet",
        "chat",
    ]

    def __init__(
        self,
        make_predictions: bool = None,
        follow_raid: bool = None,
        claim_drops: bool = None,
        claim_moments: bool = None,
        watch_streak: bool = None,
        favorite: bool = None,
        points_limit: int | None = None,
        community_goals: bool = None,
        bet: BetSettings = None,
        chat: ChatPresence = None,
    ):
        self.make_predictions = make_predictions
        self.follow_raid = follow_raid
        self.claim_drops = claim_drops
        self.claim_moments = claim_moments
        self.watch_streak = watch_streak
        self.favorite = favorite
        self.points_limit = points_limit
        self.community_goals = community_goals
        self.bet = bet
        self.chat = chat

    def default(self):
        for name in [
            "make_predictions",
            "follow_raid",
            "claim_drops",
            "claim_moments",
            "watch_streak",
        ]:
            if getattr(self, name) is None:
                setattr(self, name, True)
        if self.favorite is None:
            self.favorite = False
        if self.community_goals is None:
            self.community_goals = False
        if self.bet is None:
            self.bet = BetSettings()
        if self.chat is None:
            self.chat = ChatPresence.ONLINE

    def __repr__(self):
        return f"BetSettings(make_predictions={self.make_predictions}, follow_raid={self.follow_raid}, claim_drops={self.claim_drops}, claim_moments={self.claim_moments}, watch_streak={self.watch_streak}, favorite={self.favorite}, points_limit={self.points_limit}, community_goals={self.community_goals}, bet={self.bet}, chat={self.chat})"


class Streamer(object):
    __slots__ = [
        "username",
        "channel_id",
        "settings",
        "is_online",
        "stream_up",
        "online_at",
        "offline_at",
        "channel_points_enabled",
        "chat_banned",
        "channel_points",
        "community_goals",
        "minute_watched_requests",
        "viewer_is_mod",
        "activeMultipliers",
        "subscription_tier",
        "channel_points_context_at",
        "irc_chat",
        "stream",
        "raid",
        "history",
        "streamer_url",
        "mutex",
        "watch_streak_cache",
        "watch_streak_cache_path",
        "watch_streak_account",
    ]

    def __init__(self, username, settings=None):
        self.username: str = username.lower().strip()
        self.channel_id: str = ""
        self.settings = settings
        self.is_online = False
        self.stream_up = 0
        self.online_at = 0
        self.offline_at = 0
        self.channel_points_enabled = True
        self.chat_banned = False
        self.channel_points = 0
        self.community_goals = {}
        self.minute_watched_requests = None
        self.viewer_is_mod = False
        self.activeMultipliers = None
        self.subscription_tier = None
        self.channel_points_context_at = 0.0
        self.irc_chat = None

        self.stream = Stream()

        self.raid = None
        self.history = {}

        self.streamer_url = f"{URL}/{self.username}"

        self.mutex = Lock()
        self.watch_streak_cache = None
        self.watch_streak_cache_path = ""
        self.watch_streak_account = None

    def __repr__(self):
        return f"Streamer(username={self.username}, channel_id={self.channel_id}, channel_points={_millify(self.channel_points)})"

    def __str__(self):
        return (
            f"{self.username} ({_millify(self.channel_points)} points)"
            if Settings.logger.less
            else self.__repr__()
        )

    def set_offline(self):
        now = time.time()
        state_changed = False
        if self.is_online is True:
            self.offline_at = now
            self.is_online = False
            state_changed = True
        elif self.offline_at == 0:
            self.offline_at = now
            state_changed = True

        if self.watch_streak_cache is not None and self.watch_streak_account:
            if self.offline_at:
                self.watch_streak_cache.record_offline(
                    self.username,
                    self.offline_at,
                    account_name=self.watch_streak_account,
                )
            for session in self.watch_streak_cache.pending_sessions(
                account_name=self.watch_streak_account
            ):
                if session.streamer_login == self.username:
                    self.watch_streak_cache.mark_ended(
                        self.username,
                        session.broadcast_id,
                        ended_at=self.offline_at,
                        account_name=self.watch_streak_account,
                    )
            self.watch_streak_cache.set_streamer_status(
                self.username,
                watch_streak_detected=False,
                is_online=False,
                last_stream_started_at=getattr(self.stream, "created_at", None),
                broadcast_id=None,
                checked_at=self.offline_at,
                account_name=self.watch_streak_account,
            )

        self.toggle_chat()

        if state_changed:
            logger.info(
                f"{self} is Offline!",
                extra={
                    "emoji": ":sleeping:",
                    "event": Events.STREAMER_OFFLINE,
                },
            )

    def set_online(self):
        state_changed = False
        if self.is_online is False:
            self.online_at = time.time()
            self.is_online = True
            state_changed = True
            if self.stream.broadcast_id in [None, ""]:
                self.stream.init_watch_streak()
            if (
                self.watch_streak_cache is not None
                and self.watch_streak_account
                and self.stream.broadcast_id
            ):
                self.watch_streak_cache.record_online(
                    self.username,
                    self.stream.broadcast_id,
                    self.online_at,
                    account_name=self.watch_streak_account,
                )
                self.watch_streak_cache.set_streamer_status(
                    self.username,
                    watch_streak_detected=(
                        self.settings.watch_streak is True
                        and self.stream.watch_streak_missing is False
                    ),
                    is_online=True,
                    last_stream_started_at=getattr(self.stream, "created_at", None),
                    broadcast_id=self.stream.broadcast_id,
                    checked_at=self.online_at,
                    account_name=self.watch_streak_account,
                )

        self.toggle_chat()

        if state_changed:
            logger.info(
                f"{self} is Online!",
                extra={
                    "emoji": ":partying_face:",
                    "event": Events.STREAMER_ONLINE,
                },
            )

    def print_history(self):
        return "; ".join(
            [
                f"{key} ({self.history[key]['counter']} times, {_millify(self.history[key]['amount'])} gained)"
                for key in sorted(self.history)
                if self.history[key]["counter"] != 0
            ]
        )

    def update_history(self, reason_code, earned, counter=1):
        if reason_code not in self.history:
            self.history[reason_code] = {"counter": 0, "amount": 0}
        self.history[reason_code]["counter"] += counter
        self.history[reason_code]["amount"] += earned

        if reason_code == "WATCH":
            self.stream.watch_count = max(
                0, int(getattr(self.stream, "watch_count", 0)) + int(counter or 0)
            )

        if reason_code is not None and "WATCH_STREAK" in str(reason_code):
            self.stream.watch_streak_missing = False
            if self.watch_streak_cache is not None:
                self.watch_streak_cache.mark_claimed(
                    self.username,
                    broadcast_id=self.stream.broadcast_id,
                    now=time.time(),
                    account_name=self.watch_streak_account,
                )
                self.watch_streak_cache.set_streamer_status(
                    self.username,
                    watch_streak_detected=True,
                    is_online=bool(self.is_online),
                    last_stream_started_at=getattr(self.stream, "created_at", None),
                    broadcast_id=self.stream.broadcast_id,
                    checked_at=time.time(),
                    account_name=self.watch_streak_account,
                )
                if self.watch_streak_cache_path:
                    self.watch_streak_cache.save_to_disk_if_dirty(
                        self.watch_streak_cache_path
                    )
        elif self.stream.watch_streak_missing and self.stream.watch_count >= 2:
            # In practice, two WATCH rewards is a reliable proxy that streak
            # progress for the current stream has already been counted.
            self.stream.watch_streak_missing = False

    def stream_up_elapsed(self):
        return self.stream_up == 0 or ((time.time() - self.stream_up) > 120)

    def drops_condition(self):
        return (
            self.settings.claim_drops is True
            and self.is_online is True
            and self.stream.campaigns_ids != []
            and self.has_farmable_drops()
        )

    def viewer_has_points_multiplier(self):
        return self.activeMultipliers is not None and len(self.activeMultipliers) > 0

    def total_points_multiplier(self):
        return (
            sum(
                map(
                    lambda x: x["factor"],
                    self.activeMultipliers,
                ),
            )
            if self.activeMultipliers is not None
            else 0
        )

    def has_farmable_drops(self):
        campaigns = getattr(self.stream, "campaigns", []) or []
        # If we have campaign ids but haven't synced details yet, assume there may be farmable drops.
        if not campaigns and self.stream.campaigns_ids:
            return True
        if not campaigns:
            return False
        is_subscribed = self.subscription_tier is not None
        for campaign in campaigns:
            for drop in getattr(campaign, "drops", []) or []:
                if drop.is_claimed or drop.dt_match is False:
                    continue
                if drop.requires_subscription and not is_subscribed:
                    continue
                return True
        return False

    def get_prediction_window(self, prediction_window_seconds):
        delay_mode = self.settings.bet.delay_mode
        delay = self.settings.bet.delay
        if delay_mode == DelayMode.FROM_START:
            return min(delay, prediction_window_seconds)
        elif delay_mode == DelayMode.FROM_END:
            return max(prediction_window_seconds - delay, 0)
        elif delay_mode == DelayMode.PERCENTAGE:
            return prediction_window_seconds * delay
        else:
            return prediction_window_seconds

    # === ANALYTICS === #
    def persistent_annotations(self, event_type, event_text):
        event_type = event_type.upper()
        if event_type in ["WATCH_STREAK", "WIN", "PREDICTION_MADE", "LOSE"]:
            primary_color = (
                "#45c1ff"  # blue #45c1ff yellow #ffe045 green #36b535 red #ff4545
                if event_type == "WATCH_STREAK"
                else (
                    "#ffe045"
                    if event_type == "PREDICTION_MADE"
                    else ("#36b535" if event_type == "WIN" else "#ff4545")
                )
            )
            data = {
                "borderColor": primary_color,
                "label": {
                    "style": {"color": "#000", "background": primary_color},
                    "text": event_text,
                },
            }
            self.__save_json("annotations", data)

    def persistent_series(self, event_type="Watch"):
        self.__save_json("series", event_type=event_type)

    def __save_json(self, key, data={}, event_type="Watch"):
        # https://stackoverflow.com/questions/4676195/why-do-i-need-to-multiply-unix-timestamps-by-1000-in-javascript
        now = datetime.now().replace(microsecond=0)
        data.update({"x": round(datetime.timestamp(now) * 1000)})

        if key == "series":
            data.update({"y": self.channel_points})
            if event_type is not None:
                data.update({"z": event_type.replace("_", " ").title()})

        fname = os.path.join(Settings.analytics_path, f"{self.username}.json")
        temp_fname = fname + ".temp"  # Temporary file name

        with self.mutex:
            # Create and write to the temporary file
            with open(temp_fname, "w") as temp_file:
                json_data = json.load(open(fname, "r")) if os.path.isfile(fname) else {}
                if key not in json_data:
                    json_data[key] = []
                json_data[key].append(data)
                json.dump(json_data, temp_file, indent=4)

            # Replace the original file with the temporary file
            os.replace(temp_fname, fname)

    def leave_chat(self):
        if self.irc_chat is not None:
            self.irc_chat.stop()

            # Recreate a new thread to start again
            # raise RuntimeError("threads can only be started once")
            self.irc_chat = ThreadChat(
                self.irc_chat.username,
                self.irc_chat.token,
                self,
            )

    def __join_chat(self):
        if self.irc_chat is not None:
            if self.irc_chat.is_alive() is False:
                self.irc_chat.start()

    def toggle_chat(self):
        if self.settings.chat == ChatPresence.ALWAYS:
            self.__join_chat()
        elif self.settings.chat != ChatPresence.NEVER:
            if self.is_online is True:
                if self.settings.chat == ChatPresence.ONLINE:
                    self.__join_chat()
                elif self.settings.chat == ChatPresence.OFFLINE:
                    self.leave_chat()
            else:
                if self.settings.chat == ChatPresence.ONLINE:
                    self.leave_chat()
                elif self.settings.chat == ChatPresence.OFFLINE:
                    self.__join_chat()

    def update_community_goal(self, community_goal):
        self.community_goals[community_goal.goal_id] = community_goal

    def delete_community_goal(self, goal_id):
        self.community_goals.pop(goal_id)
