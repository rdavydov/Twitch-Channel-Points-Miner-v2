import logging
from abc import ABCMeta, abstractmethod
from datetime import datetime
from threading import Timer
from typing import Any, Callable, Protocol, Tuple

from TwitchChannelPointsMiner.classes.entities.Bet import (
    Bet,
    Condition,
    OutcomeKeys,
    Strategy,
)
from TwitchChannelPointsMiner.classes.entities.EventPrediction import (
    EventPrediction,
    Prediction,
    Result,
)
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
from TwitchChannelPointsMiner.classes.event_prediction.Manager import (
    EventPredictionManagerBase,
)
from TwitchChannelPointsMiner.classes.Settings import Events

logger = logging.getLogger(__name__)


class EventPredictionBettorBase(EventPredictionManagerBase, metaclass=ABCMeta):
    """Abstract base class for objects that can place bets on EventPredictions."""

    @abstractmethod
    def skip(self, streamer: Streamer, event_id: str, bet: Bet) -> Tuple[bool, Any]:
        """
        Analyzes the given Bet and event with the given id and returns whether the Bet should be skipped.

        Returns a Tuple[bool, Any] where:
        The bool is True if the event with the given id should be skipped.
        The Any represents the "compared value" used to decide whether to skip, generally this is a number.

        :param streamer: The Streamer for the event.
        :param event_id: The identity of the event.
        :param bet: The bet that might get skipped.
        :return: The decided skip bool and compared value.
        """
        pass

    @abstractmethod
    def create_bet(self, streamer: Streamer, event_id: str) -> Bet | None:
        """
        Analyses the event with the given id and creates a Bet.
        The result will be None if no Bet is/can be created.

        :param streamer: The Streamer for the event.
        :param event_id: The identity of the event.
        :return: The Bet created.
        """
        pass

    @abstractmethod
    def create_and_place_bet(self, streamer: Streamer, event_id: str):
        """
        Creates a Bet and attempts to place it.

        :param streamer: The Streamer for the event.
        :param event_id: The identity of the event.
        """


def skip(streamer: Streamer, event_id: str, bet: Bet) -> Tuple[bool, float]:
    """
    Skip implementation that abides by the Streamer's BetSettings.

    :param streamer: The Streamer for the event.
    :param event_id: The identity of the event.
    :param bet: The bet that might get skipped.
    :return: Whether the bet should be skipped.
    """
    event = streamer.event_predictions[event_id]
    settings = streamer.settings.bet
    if settings.filter_condition is not None:
        # key == by , condition == where
        key = settings.filter_condition.by
        condition = settings.filter_condition.where
        value = settings.filter_condition.value

        if key is OutcomeKeys.TOTAL_USERS:
            compared_value = event.total_users
        elif key is OutcomeKeys.TOTAL_POINTS:
            compared_value = event.total_points
        else:
            # Other keys refer to values on outcomes
            compared_value = event.outcomes_by_id[bet.outcome_id].get_value(key)

        # Check if condition is satisfied
        if condition == Condition.GT:
            if compared_value > value:
                return False, compared_value
        elif condition == Condition.LT:
            if compared_value < value:
                return False, compared_value
        elif condition == Condition.GTE:
            if compared_value >= value:
                return False, compared_value
        elif condition == Condition.LTE:
            if compared_value <= value:
                return False, compared_value
        return True, compared_value  # Else skip the bet
    else:
        return False, 0  # Default don't skip the bet


def create_bet(streamer: Streamer, event_id: str) -> Bet | None:
    """
    Create bet implementation that complies with the Streamer's settings.

    :param streamer: The Streamer for the event.
    :param event_id: The identity of the event.
    :return: The Bet created.
    """
    event = streamer.event_predictions[event_id]
    if event is None:
        logger.warning(
            f"Attempted to create a Bet for an event {event_id} that doesn't exist."
        )
    elif event.prediction is not None:
        logger.info(
            f"Skipping placing a Bet for event {event_id}, a Bet has already been made."
        )
    else:
        settings = streamer.settings.bet
        outcome_id = None
        if settings.strategy == Strategy.MOST_VOTED:
            outcome_id = event.largest_matching_choice_id(OutcomeKeys.TOTAL_USERS)
        elif settings.strategy == Strategy.HIGH_ODDS:
            outcome_id = event.largest_matching_choice_id(OutcomeKeys.ODDS)
        elif settings.strategy == Strategy.PERCENTAGE:
            outcome_id = event.largest_matching_choice_id(OutcomeKeys.ODDS_PERCENTAGE)
        elif settings.strategy == Strategy.SMART_MONEY:
            outcome_id = event.largest_matching_choice_id(OutcomeKeys.TOP_POINTS)
        elif settings.strategy == Strategy.NUMBER_1:
            outcome_id = event.outcome_safe(0)
        elif settings.strategy == Strategy.NUMBER_2:
            outcome_id = event.outcome_safe(1)
        elif settings.strategy == Strategy.NUMBER_3:
            outcome_id = event.outcome_safe(2)
        elif settings.strategy == Strategy.NUMBER_4:
            outcome_id = event.outcome_safe(3)
        elif settings.strategy == Strategy.NUMBER_5:
            outcome_id = event.outcome_safe(4)
        elif settings.strategy == Strategy.NUMBER_6:
            outcome_id = event.outcome_safe(5)
        elif settings.strategy == Strategy.NUMBER_7:
            outcome_id = event.outcome_safe(6)
        elif settings.strategy == Strategy.NUMBER_8:
            outcome_id = event.outcome_safe(7)
        elif settings.strategy == Strategy.NUMBER_9:
            outcome_id = event.outcome_safe(8)
        elif settings.strategy == Strategy.NUMBER_10:
            outcome_id = event.outcome_safe(9)
        elif settings.strategy == Strategy.SMART:
            # TODO is it an oversight that SMART can only consider the first 2 options
            difference = abs(
                event.outcomes_by_id[event.outcome_safe(0)].percentage_users
                - event.outcomes_by_id[event.outcome_safe(1)].percentage_users
            )
            outcome_id = (
                event.largest_matching_choice_id(OutcomeKeys.ODDS)
                if difference < settings.percentage_gap
                else event.largest_matching_choice_id(OutcomeKeys.TOTAL_USERS)
            )
        if outcome_id is not None:
            balance = streamer.channel_points
            amount = min(
                int(balance * (settings.percentage / 100)),
                settings.max_points,
            )
            if settings.stealth_mode is True:
                # TODO Is there a need to reduce by a random amount, the first user to make a bet that ends up
                #      having an amount equal to top_points is the one who gets listed by the Twitch client so it's
                #      not possible for us to place the top points bet unless the decided outcome has no bettors.
                amount = min(float(amount), event.outcomes_by_id[outcome_id].top_points)

            return Bet(outcome_id, int(amount))
        else:
            logger.info(
                f"Skip betting for event {event_id}, unable to find outcome for {settings.strategy} strategy."
            )
        return None


class TimerFactory(Protocol):
    """A factory function that can create Timer objects."""

    def __call__(
        self,
        interval: float,
        function: Callable,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> Timer: ...


class EventPredictionBettor(EventPredictionBettorBase, metaclass=ABCMeta):
    """An EventPredictionBettorBase that places bets in accordance with the Streamer's settings."""

    __slots__ = ["__place_bet"]

    def __init__(
        self,
        place_bet: Callable[[Streamer, str, Bet], None],
    ):
        self.__place_bet = place_bet
        """A function that can be called to place a bet."""

    def skip(self, streamer: Streamer, event_id: str, bet: Bet) -> Tuple[bool, float]:
        return skip(streamer, event_id, bet)

    def create_bet(self, streamer: Streamer, event_id: str) -> Bet | None:
        return create_bet(streamer, event_id)

    def create_and_place_bet(self, streamer: Streamer, event_id: str):
        event = streamer.event_predictions[event_id]
        bet = self.create_bet(streamer, event_id)
        if bet is not None:
            should_skip, compared_value = self.skip(streamer, event_id, bet)
            if should_skip is True:
                logger.info(
                    f"Skip betting for the event {event}",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )
                logger.info(
                    f"Skip settings {streamer.settings.bet.filter_condition}, current value is: {compared_value}",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )
            else:
                self.__place_bet(streamer, event_id, bet)


class TimerEventPredictionBettor(EventPredictionBettor):
    """Event Prediction Bettor that reacts to new events by creating a Timer that will eventually place a bet."""

    __slots__ = ["__timer_factory"]

    def __init__(
        self,
        place_bet: Callable[[Streamer, str, Bet], None],
        timer_factory: TimerFactory,
    ):
        super().__init__(place_bet)
        self.__timer_factory = timer_factory

    def new(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        if event.event_id in streamer.event_predictions:
            # Ignore events that aren't being tracked
            seconds_until_place_bet = streamer.get_time_until_place_bet(
                event, current_timestamp
            )
            if seconds_until_place_bet > 0:
                # Ignore events that have passed the calculated betting time
                bet_settings = streamer.settings.bet
                if (
                    bet_settings.minimum_points is None
                    or streamer.channel_points > bet_settings.minimum_points
                ):
                    # Ignore events that start when we don't have enough points
                    place_bet_thread = self.__timer_factory(
                        seconds_until_place_bet,
                        self.create_and_place_bet,
                        [streamer, event.event_id],
                    )
                    place_bet_thread.daemon = True
                    place_bet_thread.start()

                    logger.info(
                        f"Place the bet after: {seconds_until_place_bet}s for Streamer {streamer} for: {event}",
                        extra={
                            "emoji": ":alarm_clock:",
                            "event": Events.BET_START,
                        },
                    )
                else:
                    logger.info(
                        f"{streamer} has only {streamer.channel_points} channel points and the minimum for betting is: {bet_settings.minimum_points}",
                        extra={
                            "emoji": ":pushpin:",
                            "event": Events.BET_FILTERS,
                        },
                    )
            else:
                logger.info(
                    f"New EventPrediction {event.event_id} cannot be bet on, there is not enough time to place a bet: created_at={event.created_at}, prediction_window_seconds={event.prediction_window_seconds}, current_timestamp={current_timestamp}.",
                    extra={
                        "emoji": ":pushpin:",
                        "event": Events.BET_FILTERS,
                    },
                )

    # This Bettor implementation only reacts by starting a Timer during `new` so these can be left empty
    def update(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        pass

    def prediction_updated(
        self, streamer: Streamer, event_id: str, prediction: Prediction
    ):
        pass

    def result(self, streamer: Streamer, event_id: str, result: Result):
        pass
