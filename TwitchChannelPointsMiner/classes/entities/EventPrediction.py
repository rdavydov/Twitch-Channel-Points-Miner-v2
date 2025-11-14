import logging
from datetime import datetime
from enum import Enum
from typing import Callable

from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys
from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.utils import _millify, float_round

logger = logging.getLogger(__name__)


class ResultType(str, Enum):
    """An Enum representing the Type Results can have."""

    WIN = "WIN"
    """The Prediction has won."""
    LOSE = "LOSE"
    """The Prediction has lost."""
    REFUND = "REFUND"
    """The Prediction has been refunded."""


class Result:
    """Represents the Result of a Prediction."""

    def __init__(self, result_type: ResultType, points_won: int | None):
        self.result_type = result_type
        """The Result Type returned by Twitch."""
        self.points_won = points_won
        """The amount of channel points gained by the user."""

    def __repr__(self):
        return f"Result(result_type={self.result_type}, points_won={self.points_won})"

    def __eq__(self, other):
        return (
            isinstance(other, Result)
            and self.result_type == other.result_type
            and self.points_won == other.points_won
        )

    def action(self) -> str:
        """
        Maps this Result's result_type to a different human-readable string.

        :return: Either "Lost", "Refunded", or "Win" depending on the result type.
        """
        return (
            "Lost"
            if self.result_type == "LOSE"
            else ("Refunded" if self.result_type == "REFUND" else "Gained")
        )


class Prediction:
    """
    Object representing a Prediction made on an EventPrediction.

    A Prediction is distinct from a Bet in that a Prediction is created by a single Bet and then, optionally, the
    Prediction's points can be increased by making more Bets.
    """

    def __init__(self, outcome_id: str, points: int, result: Result | None = None):
        self.outcome_id = outcome_id
        """The id of the Outcome on which this Prediction was made."""
        self.points = points
        """The total number of channel points wagered on this Prediction."""
        self.result = result
        """The Result, if any, of this Prediction."""

    def __repr__(self):
        result_repr = f", result={self.result}" if self.result is not None else ""
        return f"Prediction(outcome_id='{self.outcome_id}', points={self.points}{result_repr})"

    def __str__(self):
        return (
            f"Prediction(outcome_id='{self.outcome_id}', points={self.points})"
            if Settings.logger.less
            else self.__repr__()
        )

    def __eq__(self, other):
        return (
            isinstance(other, Prediction)
            and self.outcome_id == other.outcome_id
            and self.points == other.points
        )

    def describe_result(self) -> str:
        """
        Creates a string description of this Prediction.
        It will be empty if the Prediction has yet to be resulted.

        :return: A string description of this Prediction.
        """
        if self.result is None:
            return ""
        else:
            action = self.result.action()
            placed = self.points
            won = self.result.points_won if self.result.points_won is not None else 0
            gained = won - placed if self.result.result_type != ResultType.REFUND else 0
            prefix = "+" if gained >= 0 else ""
            return (
                f"{self.result.result_type.name}, {action}: {prefix}{_millify(gained)}"
            )

    def points_gained(self) -> int:
        """
        Calculates the amount of points gained by the user.
        It will be 0 if this Prediction has yet to be resulted.

        :return: The amount of points gained by the user.
        """
        if self.result is None:
            return 0
        else:
            if self.result.result_type == ResultType.REFUND:
                return 0
            elif self.result.result_type == ResultType.LOSE:
                return -self.points
            else:
                return (
                    self.result.points_won - self.points
                    if self.result.points_won is not None
                    else 0
                )


class Outcome(object):
    """An object representing an Outcome of an EventPrediction."""

    __value_mapping: dict[OutcomeKeys, Callable[["Outcome"], int | float]] = {
        OutcomeKeys.TOTAL_USERS: lambda p: p.total_users,
        OutcomeKeys.TOTAL_POINTS: lambda p: p.total_points,
        OutcomeKeys.ODDS: lambda p: p.odds,
        OutcomeKeys.ODDS_PERCENTAGE: lambda p: p.odds_percentage,
        OutcomeKeys.PERCENTAGE_USERS: lambda p: p.percentage_users,
        OutcomeKeys.TOP_POINTS: lambda p: p.top_points,
        # Decision keys are equivalent at the outcome level
        OutcomeKeys.DECISION_USERS: lambda p: p.total_users,
        OutcomeKeys.DECISION_POINTS: lambda p: p.total_points,
    }

    def __init__(
        self,
        identity: str,
        color: str,
        title: str,
        total_points: int,
        total_users: int,
        top_predictors: list[Prediction],
        percentage_users: float = 0,
        odds: float = 0,
        odds_percentage: float = 0,
        top_points: int = 0,
    ):
        self.identity = identity
        """A UUID representing the identity of the Outcome."""
        self.color = color
        """The color of the Outcome."""
        self.title = title
        """The title of the Outcome."""
        self.total_points = total_points
        """The total number of points wagered by all users on the Outcome."""
        self.total_users = total_users
        """The total number of users with a Prediction on the Outcome."""
        self.top_predictors = top_predictors if top_predictors is not None else []
        """A list of the Predictions with the highest points made on the Outcome."""
        # The following are computed values that are not provided by the Twitch API
        self.percentage_users = percentage_users
        """The percentage of users with a Prediction on the Outcome."""
        self.odds = odds
        """The odds of this Outcome."""
        self.odds_percentage = odds_percentage
        """The estimated probability of the Outcome expressed as a percentage."""
        self.top_points = top_points
        """The highest number of points in a single Prediction for this Outcome."""

    def __repr__(self):
        return f"Outcome(identity='{self.identity}', color='{self.color}', title='{self.title}', total_points={self.total_points}, total_users={self.total_users}, top_predictors={self.top_predictors}, percentage_users={self.percentage_users}, odds={self.odds}, odds_percentage={self.odds_percentage}, top_points={self.top_points})"

    def __str__(self):
        return f"'{self.title}'" if Settings.logger.less else self.__repr__()

    def __eq__(self, other):
        return (
            isinstance(other, Outcome)
            and self.identity == other.identity
            and self.color == other.color
            and self.title == other.title
            and self.total_points == other.total_points
            and self.total_users == other.total_users
            and self.top_predictors == other.top_predictors
            and self.percentage_users == other.percentage_users
            and self.odds == other.odds
            and self.odds_percentage == other.odds_percentage
            and self.top_points == other.top_points
        )

    def update(self, event_total_users: int, event_total_points: int):
        """
        Updates computed values based on the given totals for the event.

        :param event_total_users: The total number of users with a Prediction on the parent event.
        :param event_total_points: The total number of points wagered in Predictions on the parent event.
        """
        self.percentage_users = (
            float_round(100 * (self.total_users / event_total_users))
            if event_total_users != 0
            else 0
        )
        self.odds = (
            float_round(event_total_points / self.total_points)
            if self.total_points != 0
            else 0
        )
        self.odds_percentage = float_round(100 / self.odds) if self.odds != 0 else 0
        self.top_points = max(map(lambda p: p.points, self.top_predictors), default=0)

    def get_value(self, key: OutcomeKeys) -> int | float:
        """
        Returns the value for the given key.

        :param key: The key for which to get the value.
        :return: The value for the given key.
        """
        return Outcome.__value_mapping[key](self)


class EventPrediction(object):
    """An object representing a Twitch Prediction Event."""

    __slots__ = [
        "event_id",
        "title",
        "created_at",
        "prediction_window_seconds",
        "status",
        "outcomes",
        "outcomes_by_id",
        "total_points",
        "total_users",
        "prediction",
    ]

    def __init__(
        self,
        event_id: str,
        title: str,
        created_at: datetime,
        prediction_window_seconds: float,
        status: str,
        outcomes: list[Outcome],
        outcomes_by_id=None,
        total_points: int = 0,
        total_users: int = 0,
        prediction: Prediction | None = None,
    ):
        self.event_id = event_id
        """The identity of the EventPrediction."""
        self.title = title.strip()
        """The title of the EventPrediction"""
        self.created_at = created_at
        """The datetime the EventPrediction was created"""
        self.prediction_window_seconds = prediction_window_seconds
        """The amount of time, in seconds, for which the EventPrediction can be active."""
        self.status = status
        """The current status of the EventPrediction."""
        self.outcomes = outcomes
        """The list of the Outcomes of the EventPrediction."""
        self.outcomes_by_id: dict[str, Outcome] = (
            {outcome.identity: outcome for outcome in self.outcomes}
            if outcomes_by_id is None
            else outcomes_by_id
        )
        """The same list of Outcomes but mapped to their ID for convenience."""
        self.total_points = total_points
        """The total number of points bet on the EventPrediction."""
        self.total_users = total_users
        """The total number of users that have bet on the EventPrediction."""
        self.prediction = prediction
        """The Prediction this user has placed on the EventPrediction."""

    def __repr__(self):
        return f"EventPrediction(event_id='{self.event_id}', title='{self.title}', created_at={self.created_at}, prediction_window_seconds={self.prediction_window_seconds}, status='{self.status}'', outcomes={self.outcomes}, total_points={self.total_points}, total_users={self.total_users}, prediction={self.prediction})"

    def __str__(self):
        return f"'{self.title}'" if Settings.logger.less else self.__repr__()

    def __eq__(self, other):
        return (
            isinstance(other, EventPrediction)
            and self.event_id == other.event_id
            and self.title == other.title
            and self.created_at == other.created_at
            and self.prediction_window_seconds == other.prediction_window_seconds
            and self.status == other.status
            and self.outcomes == other.outcomes
            and self.outcomes_by_id == other.outcomes_by_id
            and self.total_points == other.total_points
            and self.total_users == other.total_users
            and self.prediction == other.prediction
        )

    def update(self, outcomes: list[Outcome] | None = None):
        """
        Updates this object's calculated values by performing the following actions:

        1) Updates the totals for this EventPrediction based on its Outcomes.
        2) Updates the totals for each Outcome for this EventPrediction.
        3) Updates each Outcome.

        If outcomes is provided, they will be set to this object and then used in the totals calculation.

        :param outcomes: The new Outcomes if any.
        """
        if outcomes is not None:
            # Set new outcomes if provided
            self.outcomes = outcomes
            self.outcomes_by_id = {outcome.identity: outcome for outcome in outcomes}

        # Compute totals
        self.total_points = 0
        self.total_users = 0
        for outcome in self.outcomes:
            self.total_points += outcome.total_points
            self.total_users += outcome.total_users

        for outcome in self.outcomes:
            outcome.update(self.total_users, self.total_points)

    def recap(self) -> str:
        """
        Returns a representation of this EventPrediction including the Prediction and Result.

        :return: The representation of this EventPrediction.
        """
        result_description = (
            f"\n\t\tResult: {self.prediction.describe_result()}"
            if self.prediction
            else ""
        )
        return f"{self}\n\t\t{self.prediction}{result_description}"

    def largest_matching_choice_id(self, key) -> str:
        """
        Returns the Outcome with the largest value for the given key.

        :param key: The key for which to get the Outcome.
        :return: The Outcome with the largest value for the given key.
        """
        return max(self.outcomes, key=lambda o: o.get_value(key)).identity

    def outcome_safe(self, index: int) -> str:
        """
        Returns the identity of the Outcome at the given index or the first outcome if the index is out of range.

        :param index: The index for which to get the Outcome.
        :return: The identity of the Outcome at the given index or the first outcome if the index is out of range.
        """
        return self.outcomes[index if 0 <= index < len(self.outcomes) else 0].identity
