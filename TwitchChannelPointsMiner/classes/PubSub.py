import abc
import logging
import time
from threading import Timer

from dateutil import parser

from TwitchChannelPointsMiner.classes.Settings import Settings, Events
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.CommunityGoal import CommunityGoal
from TwitchChannelPointsMiner.classes.entities.EventPrediction import EventPrediction
from TwitchChannelPointsMiner.classes.entities.Message import Message
from TwitchChannelPointsMiner.classes.entities.Raid import Raid
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer

logger = logging.getLogger(__name__)


class MessageListener(abc.ABC):
    def on_message(self, message: Message):
        """
        Called when a PubSub Message is received.
        :param message: The message received.
        """
        pass


class PubSubHandler(MessageListener):
    """
    Listener for PubSub format Messages that handles them in a client agnostic way, i.e. this works with messages from
    both the legacy PubSub and Hermes WebSocket APIs.
    """

    def __init__(self, twitch: Twitch, streamers: list[Streamer], events_predictions: dict):
        self.twitch = twitch
        self.streamers = streamers
        self.events_predictions = events_predictions

    def on_message(self, message: Message):
        try:
            streamer = next(
                (streamer for streamer in self.streamers if streamer.channel_id == message.channel_id), None
            )
            if streamer is None:
                return
            if message.topic == "community-points-user-v1":
                if message.type in ["points-earned", "points-spent"]:
                    balance = message.data["balance"]["balance"]
                    streamer.channel_points = balance
                    # Analytics switch
                    if Settings.enable_analytics is True:
                        streamer.persistent_series(
                            event_type=message.data["point_gain"]["reason_code"]
                            if message.type == "points-earned"
                            else "Spent"
                        )

                if message.type == "points-earned":
                    earned = message.data["point_gain"]["total_points"]
                    reason_code = message.data["point_gain"]["reason_code"]

                    logger.info(
                        f"+{earned} → {streamer} - Reason: {reason_code}.",
                        extra={
                            "emoji": ":rocket:",
                            "event": Events.get(f"GAIN_FOR_{reason_code}"),
                        },
                    )
                    streamer.update_history(
                        reason_code, earned
                    )
                    # Analytics switch
                    if Settings.enable_analytics is True:
                        streamer.persistent_annotations(
                            reason_code, f"+{earned} - {reason_code}"
                        )
                elif message.type == "claim-available":
                    self.twitch.claim_bonus(
                        streamer,
                        message.data["claim"]["id"],
                    )

            elif message.topic == "video-playback-by-id":
                # There is stream-up message type, but it's sent earlier than the API updates
                if message.type == "stream-up":
                    streamer.stream_up = time.time()
                elif message.type == "stream-down":
                    if streamer.is_online is True:
                        streamer.set_offline()
                elif message.type == "viewcount":
                    if streamer.stream_up_elapsed():
                        self.twitch.check_streamer_online(
                            streamer
                        )

            elif message.topic == "raid":
                if message.type == "raid_update_v2":
                    raid = Raid(
                        message.message["raid"]["id"],
                        message.message["raid"]["target_login"],
                    )
                    self.twitch.update_raid(streamer, raid)

            elif message.topic == "community-moments-channel-v1":
                if message.type == "active":
                    self.twitch.claim_moment(
                        streamer, message.data["moment_id"]
                    )

            elif message.topic == "predictions-channel-v1":

                event_dict = message.data["event"]
                event_id = event_dict["id"]
                event_status = event_dict["status"]

                current_tmsp = parser.parse(message.timestamp)

                if (
                        message.type == "event-created"
                        and event_id not in self.events_predictions
                ):
                    if event_status == "ACTIVE":
                        prediction_window_seconds = float(
                            event_dict["prediction_window_seconds"]
                        )
                        # Reduce prediction window by 3/6s - Collect more accurate data for decision
                        prediction_window_seconds = streamer.get_prediction_window(prediction_window_seconds)
                        event = EventPrediction(
                            streamer,
                            event_id,
                            event_dict["title"],
                            parser.parse(event_dict["created_at"]),
                            prediction_window_seconds,
                            event_status,
                            event_dict["outcomes"],
                        )
                        if (
                                streamer.is_online
                                and event.closing_bet_after(current_tmsp) > 0
                        ):
                            bet_settings = streamer.settings.bet
                            if (
                                    bet_settings.minimum_points is None
                                    or streamer.channel_points
                                    > bet_settings.minimum_points
                            ):
                                self.events_predictions[event_id] = event
                                start_after = event.closing_bet_after(
                                    current_tmsp
                                )

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
                    # Game over we can't update anymore the values... The bet was placed!
                    if (
                            self.events_predictions[event_id].bet_placed is False
                            and self.events_predictions[event_id].bet.decision == {}
                    ):
                        self.events_predictions[event_id].bet.update_outcomes(
                            event_dict["outcomes"]
                        )

            elif message.topic == "predictions-user-v1":
                event_id = message.data["prediction"]["event_id"]
                if event_id in self.events_predictions:
                    event_prediction = self.events_predictions[event_id]
                    if (
                            message.type == "prediction-result"
                            and event_prediction.bet_confirmed
                    ):
                        points = event_prediction.parse_result(
                            message.data["prediction"]["result"]
                        )

                        decision = event_prediction.bet.get_decision()
                        choice = event_prediction.bet.decision["choice"]

                        logger.info(
                            (
                                f"{event_prediction} - Decision: {choice}: {decision['title']} "
                                f"({decision['color']}) - Result: {event_prediction.result['string']}"
                            ),
                            extra={
                                "emoji": ":bar_chart:",
                                "event": Events.get(
                                    f"BET_{event_prediction.result['type']}"
                                ),
                            },
                        )

                        streamer.update_history(
                            "PREDICTION", points["gained"]
                        )

                        # Remove duplicate history records from previous message sent in community-points-user-v1
                        if event_prediction.result["type"] == "REFUND":
                            streamer.update_history(
                                "REFUND",
                                -points["placed"],
                                counter=-1,
                            )
                        elif event_prediction.result["type"] == "WIN":
                            streamer.update_history(
                                "PREDICTION",
                                -points["won"],
                                counter=-1,
                            )

                        if event_prediction.result["type"]:
                            # Analytics switch
                            if Settings.enable_analytics is True:
                                streamer.persistent_annotations(
                                    event_prediction.result["type"],
                                    f"{self.events_predictions[event_id].title}",
                                )
                    elif message.type == "prediction-made":
                        event_prediction.bet_confirmed = True
                        # Analytics switch
                        if Settings.enable_analytics is True:
                            streamer.persistent_annotations(
                                "PREDICTION_MADE",
                                f"Decision: {event_prediction.bet.decision['choice']} - {event_prediction.title}",
                            )
            elif message.topic == "community-points-channel-v1":
                if message.type == "community-goal-created":
                    # TODO Untested, hard to find this happening live
                    streamer.update_community_goal(
                        CommunityGoal.from_pubsub(message.data["community_goal"])
                    )
                elif message.type == "community-goal-updated":
                    streamer.update_community_goal(
                        CommunityGoal.from_pubsub(message.data["community_goal"])
                    )
                elif message.type == "community-goal-deleted":
                    # TODO Untested, not sure what the message format for this is,
                    #      https://github.com/sammwyy/twitch-ps/blob/master/main.js#L417
                    #      suggests that it should be just the entire, now deleted, goal model
                    streamer.delete_community_goal(message.data["community_goal"]["id"])

                if message.type in ["community-goal-updated", "community-goal-created"]:
                    self.twitch.contribute_to_community_goals(streamer)

        except Exception:
            logger.error(
                f"Exception raised for topic: {message.topic} and message: {message}",
                exc_info=True,
            )
