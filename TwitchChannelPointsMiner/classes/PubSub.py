import abc
import json
import logging
import time
from threading import Timer

from dateutil import parser

from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.classes.PredictionTracker import PredictionTracker
from TwitchChannelPointsMiner.classes.entities.CommunityGoal import CommunityGoal
from TwitchChannelPointsMiner.classes.entities.EventPrediction import EventPrediction
from TwitchChannelPointsMiner.classes.entities.Message import Message
from TwitchChannelPointsMiner.classes.entities.Raid import Raid
from TwitchChannelPointsMiner.utils import get_streamer_index

logger = logging.getLogger(__name__)
USER_NOTIFICATION_TOPICS = {"user-subscribe-events-v1", "onsite-notifications", "predictions-user-v1"}


class MessageListener(abc.ABC):
    @abc.abstractmethod
    def on_message(self, message: Message):
        raise NotImplementedError()


class PubSubHandler(MessageListener):
    """
    Handle PubSub-formatted messages independently from the underlying socket
    transport. Both the legacy PubSub websocket and Hermes normalize into the
    same Message model before they reach this handler.
    """

    def __init__(self, twitch, streamers, events_predictions, prediction_tracker=None):
        self.twitch = twitch
        self.streamers = streamers
        self.events_predictions = events_predictions
        self.prediction_tracker = prediction_tracker or PredictionTracker(
            twitch, "in-memory", events=events_predictions, streamers=streamers
        )

    @staticmethod
    def _decode_pubsub_payload(payload):
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            try:
                decoded = json.loads(payload)
            except (TypeError, ValueError):
                return None
            return decoded if isinstance(decoded, dict) else None
        return None

    def on_message(self, message: Message):
        streamer_index = get_streamer_index(self.streamers, message.channel_id)
        if streamer_index == -1 and message.topic not in USER_NOTIFICATION_TOPICS:
            return

        try:
            dashboard = getattr(self.twitch, "dashboard_service", None)
            if dashboard is not None:
                try:
                    dashboard.live_message(message, self.streamers[streamer_index] if streamer_index >= 0 else None)
                except Exception:
                    logger.debug("Dashboard live observation deferred", exc_info=True)
            if message.topic == "user-subscribe-events-v1":
                notification = message.message.get("notification", {})
                pubsub = self._decode_pubsub_payload(
                    notification.get("pubsub")
                    if isinstance(notification, dict)
                    else None
                )
                channel_id = (
                    pubsub.get("channel_id") if isinstance(pubsub, dict) else None
                )
                if channel_id:
                    self.twitch.notify_gift_sub_from_channel_id(
                        channel_id,
                        self.streamers,
                    )

            elif message.topic == "onsite-notifications":
                if message.type == "create-notification" and isinstance(
                    message.data,
                    dict,
                ):
                    notification = message.data.get("notification")
                    self.twitch.notify_gift_sub_from_onsite_notification(
                        notification,
                        self.streamers,
                    )

            elif message.topic == "community-points-user-v1":
                if message.type in ["points-earned", "points-spent"]:
                    balance = message.data["balance"]["balance"]
                    self.streamers[streamer_index].channel_points = balance
                    if Settings.enable_analytics is True:
                        self.streamers[streamer_index].persistent_series(
                            event_type=message.data["point_gain"]["reason_code"]
                            if message.type == "points-earned"
                            else "Spent"
                        )

                if message.type == "points-earned":
                    earned = message.data["point_gain"]["total_points"]
                    reason_code = message.data["point_gain"]["reason_code"]

                    logger.info(
                        f"+{earned} → {self.streamers[streamer_index]} - Reason: {reason_code}.",
                        extra={
                            "emoji": ":rocket:",
                            "event": Events.get(f"GAIN_FOR_{reason_code}"),
                        },
                    )
                    # Prediction profits are accounted from the authoritative result once,
                    # not again from the separate payout/refund balance notification.
                    if reason_code not in {"PREDICTION", "REFUND"}:
                        self.streamers[streamer_index].update_history(reason_code, earned)
                    if reason_code is not None and "WATCH_STREAK" in str(reason_code):
                        self.twitch.record_watch_streak_evidence(
                            self.streamers[streamer_index],
                            evidence_source="pubsub_watch_streak",
                        )
                    if Settings.enable_analytics is True:
                        self.streamers[streamer_index].persistent_annotations(
                            reason_code, f"+{earned} - {reason_code}"
                        )
                elif message.type == "claim-available":
                    self.twitch.claim_bonus(
                        self.streamers[streamer_index],
                        message.data["claim"]["id"],
                    )

            elif message.topic == "video-playback-by-id":
                if message.type == "stream-up":
                    self.streamers[streamer_index].stream_up = time.time()
                elif message.type == "stream-down":
                    if self.streamers[streamer_index].is_online is True:
                        self.streamers[streamer_index].set_offline()
                elif message.type == "viewcount":
                    if self.streamers[streamer_index].stream_up_elapsed():
                        self.twitch.check_streamer_online(
                            self.streamers[streamer_index]
                        )

            elif message.topic == "raid":
                if message.type == "raid_update_v2":
                    raid = Raid(
                        message.message["raid"]["id"],
                        message.message["raid"]["target_login"],
                    )
                    self.twitch.update_raid(self.streamers[streamer_index], raid)

            elif message.topic == "community-moments-channel-v1":
                if message.type == "active":
                    self.twitch.claim_moment(
                        self.streamers[streamer_index], message.data["moment_id"]
                    )

            elif message.topic == "predictions-channel-v1":
                event_dict = message.data["event"]
                event_id = event_dict["id"]
                event_status = event_dict["status"]
                self.prediction_tracker.remember_event(
                    event_id, event_dict, self.streamers[streamer_index]
                )

                current_tmsp = parser.parse(message.timestamp)

                if (
                    message.type == "event-created"
                    and event_id not in self.events_predictions
                ):
                    if event_status == "ACTIVE":
                        prediction_window_seconds = float(
                            event_dict["prediction_window_seconds"]
                        )
                        prediction_window_seconds = self.streamers[
                            streamer_index
                        ].get_prediction_window(prediction_window_seconds)
                        event = EventPrediction(
                            self.streamers[streamer_index],
                            event_id,
                            event_dict["title"],
                            parser.parse(event_dict["created_at"]),
                            prediction_window_seconds,
                            event_status,
                            event_dict["outcomes"],
                        )
                        if (
                            self.streamers[streamer_index].is_online
                            and event.closing_bet_after(current_tmsp) > 0
                        ):
                            streamer = self.streamers[streamer_index]
                            bet_settings = streamer.settings.bet
                            if streamer.settings.make_predictions is False:
                                return
                            if (
                                bet_settings.minimum_points is None
                                or streamer.channel_points
                                >= bet_settings.minimum_points
                            ):
                                self.events_predictions[event_id] = event
                                start_after = event.closing_bet_after(current_tmsp)

                                place_bet_thread = Timer(
                                    start_after,
                                    self.twitch.make_predictions,
                                    (self.events_predictions[event_id],),
                                )
                                place_bet_thread.daemon = True
                                place_bet_thread.start()

                                logger.info(
                                    f"Place the bet after: {start_after}s for: {self.events_predictions[event_id]}",
                                    extra={
                                        "emoji": ":alarm_clock:",
                                        "event": Events.BET_START,
                                    },
                                )
                            else:
                                logger.info(
                                    f"{streamer} have only {streamer.channel_points} channel points and the minimum for bet is: {bet_settings.minimum_points}",
                                    extra={
                                        "emoji": ":pushpin:",
                                        "event": Events.BET_FILTERS,
                                    },
                                )

                elif (
                    message.type == "event-updated"
                    and event_id in self.events_predictions
                ):
                    self.events_predictions[event_id].status = event_status
                    if (
                        self.events_predictions[event_id].bet_placed is False
                        and self.events_predictions[event_id].bet.decision == {}
                    ):
                        self.events_predictions[event_id].bet.update_outcomes(
                            event_dict["outcomes"]
                        )

            elif message.topic == "predictions-user-v1":
                self.prediction_tracker.handle_user(
                    message.data.get("prediction") if isinstance(message.data, dict) else None,
                    message.type,
                )

            elif message.topic == "community-points-channel-v1":
                if message.type == "community-goal-created":
                    self.streamers[streamer_index].add_community_goal(
                        CommunityGoal.from_pubsub(message.data["community_goal"])
                    )
                elif message.type == "community-goal-updated":
                    self.streamers[streamer_index].update_community_goal(
                        CommunityGoal.from_pubsub(message.data["community_goal"])
                    )
                elif message.type == "community-goal-deleted":
                    self.streamers[streamer_index].delete_community_goal(
                        message.data["community_goal"]["id"]
                    )

                if message.type in [
                    "community-goal-updated",
                    "community-goal-created",
                ]:
                    self.twitch.contribute_to_community_goals(
                        self.streamers[streamer_index]
                    )

        except Exception:
            logger.error(
                f"Exception raised for topic: {message.topic} and message: {message}",
                exc_info=True,
            )
