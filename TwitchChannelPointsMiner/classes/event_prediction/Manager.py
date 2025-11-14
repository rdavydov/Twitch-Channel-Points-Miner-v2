import logging
from abc import ABCMeta, abstractmethod
from datetime import datetime

from TwitchChannelPointsMiner.classes.entities.EventPrediction import (
    EventPrediction,
    Prediction,
    Result,
)
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
from TwitchChannelPointsMiner.classes.Settings import Events, Settings

logger = logging.getLogger(__name__)


class EventPredictionManagerBase(object, metaclass=ABCMeta):
    """Abstract base class for objects that manage the lifecycle of EventPredictions."""

    @abstractmethod
    def new(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        """
        Adds the given EventPrediction to the given streamer's 'event_predictions' member.
        This should only happen when an event is first created.

        :param streamer: The Streamer for the event.
        :param event: The new EventPrediction.
        :param current_timestamp: The current timestamp.
        """
        pass

    @abstractmethod
    def update(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        """
        Updates the matching event for the given streamer.
        This happens periodically while the event is active and bets are being made.
        It also happens when the event status changes, i.e. the event gets locked or resulted.
        If no matching event is found, it should be treated as if it were new.

        :param streamer: The Streamer for the event.
        :param event: The updated event data.
        :param current_timestamp: The timestamp of the update.
        """
        pass

    @abstractmethod
    def prediction_updated(
        self, streamer: Streamer, event_id: str, prediction: Prediction
    ):
        """
        Updates the Prediction for the event with the given id.
        This can happen if this bot places a bet or if the user does it manually.
        This will happen once each time a bet is placed.

        :param streamer: The Streamer for the event.
        :param event_id: The identity of the event.
        :param prediction: The updated prediction data.
        """
        pass

    @abstractmethod
    def result(self, streamer: Streamer, event_id: str, result: Result):
        """
        Updates the event with the given id to reflect the given result.
        This should happen once when the event gets resulted and the user has a Prediction for the event.

        :param streamer: The Streamer for the event.
        :param event_id: The identity of the event.
        :param result: The result of the event's prediction.
        """
        pass


class EventPredictionTracker(EventPredictionManagerBase):
    """A PredictionTrackerBase that just tracks EventPredictions."""

    def new(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        if event.event_id in streamer.event_predictions:
            logger.warning(f"EventPrediction {event.event_id} already added, ignoring.")
        else:
            streamer.event_predictions[event.event_id] = event

    def update(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        if event.event_id not in streamer.event_predictions:
            # This can happen if a prediction was already running before the app was started
            logger.debug(
                f"Ignoring EventPrediction {event.event_id} because it started before the miner did."
            )
        else:
            # Preserve the prediction and set new event data
            event.prediction = streamer.event_predictions[event.event_id].prediction
            streamer.event_predictions[event.event_id] = event

    def prediction_updated(
        self, streamer: Streamer, event_id: str, prediction: Prediction
    ):
        if event_id in streamer.event_predictions:
            event = streamer.event_predictions[event_id]
            event.prediction = prediction
            # Analytics switch
            if Settings.enable_analytics is True:
                streamer.persistent_annotations(
                    "PREDICTION_MADE",
                    f"Decision: {event.prediction.outcome_id} - {event.title}",
                )
            logger.debug(
                f"Prediction updated: title={event.title}, prediction={event.prediction}"
            )
        else:
            logger.warning(
                f"Prediction made for unknown event {event_id} for streamer {streamer.username}."
            )

    def result(self, streamer: Streamer, event_id: str, result: Result):
        if event_id in streamer.event_predictions:
            event = streamer.event_predictions[event_id]
            if event.prediction is None:
                logger.warning(
                    f"Prediction Resulted for event {event_id} for streamer {streamer.username} but we have no record of making a Prediction."
                )
            else:
                prediction = event.prediction
                prediction.result = result
                outcome_id = event.prediction.outcome_id
                decision = event.outcomes_by_id[outcome_id]

                logger.info(
                    (
                        f"{event} - Decision: {outcome_id}: {decision.title} "
                        f"({decision.color}) - Result: {prediction.describe_result()}"
                    ),
                    extra={
                        "emoji": ":bar_chart:",
                        "event": Events.get(
                            f"BET_{prediction.result.result_type.name}"
                        ),
                    },
                )

                streamer.update_history("PREDICTION", prediction.points_gained())

                # Remove duplicate history records from previous message sent in community-points-user-v1
                if prediction.result.result_type == "REFUND":
                    streamer.update_history(
                        "REFUND",
                        -prediction.points,
                        counter=-1,
                    )
                elif (
                    prediction.result.result_type == "WIN"
                    and prediction.result.points_won is not None
                ):
                    streamer.update_history(
                        "PREDICTION",
                        -prediction.result.points_won,
                        counter=-1,
                    )

                if prediction.result.result_type:
                    # Analytics switch
                    if Settings.enable_analytics is True:
                        streamer.persistent_annotations(
                            prediction.result.result_type,
                            f"{event.title}",
                        )
        else:
            logger.warning(
                f"Prediction Resulted for unknown event {event_id} for streamer {streamer.username}."
            )


class EventPredictionManager(EventPredictionManagerBase):
    """Event Prediction Manager that delegates to 0 or more sub managers."""

    __slots__ = ["sub_managers"]

    def __init__(self, *sub_managers: EventPredictionManagerBase):
        self.sub_managers = sub_managers

    def new(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        for sub_manager in self.sub_managers:
            sub_manager.new(streamer, event, current_timestamp)

    def update(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        for sub_manager in self.sub_managers:
            sub_manager.update(streamer, event, current_timestamp)

    def prediction_updated(
        self, streamer: Streamer, event_id: str, prediction: Prediction
    ):
        for sub_manager in self.sub_managers:
            sub_manager.prediction_updated(streamer, event_id, prediction)

    def result(self, streamer: Streamer, event_id: str, result: Result):
        for sub_manager in self.sub_managers:
            sub_manager.result(streamer, event_id, result)
