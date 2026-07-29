from enum import Enum, auto


class Strategy(Enum):
    """Enum representing a Strategy for placing Bets on EventPredictions."""

    MOST_VOTED = auto()
    """
    Selects the Outcome with the most number of users. For example:
        If Outcome A has 10 users and Outcome B has 20 users then Outcome B will be selected since 20 > 10.
    """
    HIGH_ODDS = auto()
    """
    Selects the Outcome with the highest odds. For example:
        If the odds of Outcome A are 3.1 and B are 1.2 then Outcome A would be selected since 3.1 > 1.2.
    """
    PERCENTAGE = auto()
    """
    Selects the Outcome with the greatest percentage of channel points. Similar to SMART_MONEY. For example:
        if Outcome A has a total of 150 channel points wagered and B has 50 then Outcome A would be selected since 150 > 50.
        (as a percentage that's 150 + 50 = 200 total points on the event, A has 150/200 = 75%, B has 50/200 = 25% and 75% > 25%)
    """
    SMART_MONEY = auto()
    """
    Selects the Outcome with the highest number of total channel points wagered. Similar to PERCENTAGE. For example:
        If outcome A has a total of 150 channel points wagered and B has 50 then outcome A would be selected since 150 > 50.
    """
    SMART = auto()
    """
    Works with events with 2 outcomes.
    Calculates the difference between the percentage of users on both outcomes.
    If the difference is less than the 'percentage_gap' in the streamer's BetSettings then the option with the highest odds will be selected.
    Otherwise the option with the highest total users will be selected.
    """
    NUMBER_1 = auto()
    """Selects the first outcome."""
    NUMBER_2 = auto()
    """Selects the second outcome."""
    NUMBER_3 = auto()
    """Selects the third outcome."""
    NUMBER_4 = auto()
    """Selects the fourth outcome."""
    NUMBER_5 = auto()
    """Selects the fifth outcome."""
    NUMBER_6 = auto()
    """Selects the sixth outcome."""
    NUMBER_7 = auto()
    """Selects the seventh outcome."""
    NUMBER_8 = auto()
    """Selects the eighth outcome."""
    NUMBER_9 = auto()
    """Selects the ninth outcome."""
    NUMBER_10 = auto()
    """Selects the tenth outcome."""

    def __str__(self):
        return self.name


class Condition(Enum):
    """Enum representing numeric comparisons."""

    GT = auto()
    """Greater than."""
    LT = auto()
    """Less than."""
    GTE = auto()
    """Greater than or equal than."""
    LTE = auto()
    """Less than or equal than."""

    def __str__(self):
        return self.name


class OutcomeKeys(str, Enum):
    """Enum representing EventPrediction and Outcome values that can be used in betting strategies."""

    PERCENTAGE_USERS = "percentage_users"
    """The percentage of users on a given outcome relative to the whole event."""
    ODDS_PERCENTAGE = "odds_percentage"
    """The estimated probability of a given outcome, calculated from the outcome's odds (probability = 1 / odds)."""
    ODDS = "odds"
    """The odds of a given outcome, calculated as the outcome's total points over the event's total points."""
    TOP_POINTS = "top_points"
    """The greatest number of points for an outcome."""
    TOTAL_USERS = "total_users"
    """The total number of users for an event/outcome."""
    TOTAL_POINTS = "total_points"
    """The total number of points for an event/outcome."""
    DECISION_USERS = "decision_users"
    """The total number of users for the decided outcome. Used to decide whether a bet should be skipped."""
    DECISION_POINTS = "decision_points"
    """The total number of points for the decided outcome. Used to decide whether a bet should be skipped."""

    def __str__(self):
        return self.name


class DelayMode(Enum):
    """
    Represents an anchor point in time from which to measure.
    This is used to decide when to place a bet relative to times in the lifecycle of a EventPrediction.
    """

    FROM_START = auto()
    """Measure time relative to the start of the event."""
    FROM_END = auto()
    """Measure time relative to the end of the event."""
    PERCENTAGE = auto()
    """
    Measure time relative to the start of the event as a percentage of the length of the event.
    e.g. If the event if 120 seconds long and the delay is 0.2 then the bet will be attempted at 0.2 * 120 = 24 seconds from the start of the event.
    """

    def __str__(self):
        return self.name


class FilterCondition(object):
    """
    An object representing a filter to use when deciding to skip bets.
    e.g.
        FilterCondition(OutcomeKeys.TOTAL_POINTS, Condition.GT, 5000)
        would mean that the given outcome needs more than 5000 total points wagered to be acceptable.
    """

    __slots__ = [
        "by",
        "where",
        "value",
    ]

    def __init__(self, by: OutcomeKeys, where: Condition, value: int | float):
        self.by = by
        """The property of the outcome to check. Should be one of the OutcomeKeys static members."""
        self.where = where
        """The type of comparison to make."""
        self.value = value
        """The value against which to compare the property."""

    def __repr__(self):
        return f"FilterCondition(by={self.by.upper()}, where={self.where}, value={self.value})"


class BetSettings(object):
    """Settings for placing bets on EventPredictions."""

    __slots__ = [
        "strategy",
        "percentage",
        "percentage_gap",
        "max_points",
        "minimum_points",
        "stealth_mode",
        "filter_condition",
        "delay",
        "delay_mode",
    ]

    def __init__(
        self,
        strategy: Strategy = None,
        percentage: int = None,
        percentage_gap: int = None,
        max_points: int = None,
        minimum_points: int = None,
        stealth_mode: bool = None,
        filter_condition: FilterCondition = None,
        delay: float = None,
        delay_mode: DelayMode = None,
    ):
        self.strategy = strategy
        """The Strategy to employ when selecting an event outcome."""
        self.percentage = percentage
        """The maximum percentage of points to wager."""
        self.percentage_gap = percentage_gap
        """The value to use when selecting an outcome for Strategy.SMART."""
        self.max_points = max_points
        """The maximum absolute number of points to wager."""
        self.minimum_points = minimum_points
        """The minimum absolute number of points the user needs to have in order to a bet."""
        self.stealth_mode = stealth_mode
        """Whether to limit the bet amount to the maximum number of points already wagered on the selected outcome."""
        self.filter_condition = filter_condition
        """The filter to use when deciding whether to skip a selected bet."""
        self.delay = delay
        """The delay amount to use when deciding the amount of time to wait before placing a bet."""
        self.delay_mode = delay_mode
        """The anchor point to use when calculating the bet time."""

    def default(self):
        """Sets any missing values to their defaults."""
        self.strategy = self.strategy if self.strategy is not None else Strategy.SMART
        self.percentage = self.percentage if self.percentage is not None else 5
        self.percentage_gap = (
            self.percentage_gap if self.percentage_gap is not None else 20
        )
        self.max_points = self.max_points if self.max_points is not None else 50000
        self.minimum_points = (
            self.minimum_points if self.minimum_points is not None else 0
        )
        self.stealth_mode = (
            self.stealth_mode if self.stealth_mode is not None else False
        )
        self.delay = self.delay if self.delay is not None else 6
        self.delay_mode = (
            self.delay_mode if self.delay_mode is not None else DelayMode.FROM_END
        )

    def __repr__(self):
        return f"BetSettings(strategy={self.strategy}, percentage={self.percentage}, percentage_gap={self.percentage_gap}, max_points={self.max_points}, minimum_points={self.minimum_points}, stealth_mode={self.stealth_mode})"


class Bet(object):
    """Represents a Bet made for an EventPrediction Outcome. It can create a new Prediction or update an existing one."""

    __slots__ = ["outcome_id", "points"]

    def __init__(self, outcome_id: str, points: int):
        self.outcome_id = outcome_id
        """The id of the Outcome on which the bet should be placed."""
        self.points = points
        """The amount of channel points to wager."""

    def __repr__(self):
        return f"Bet(outcome_id='{self.outcome_id}', points={self.points})"

    def __eq__(self, other):
        return (
            isinstance(other, Bet)
            and self.outcome_id == other.outcome_id
            and self.points == other.points
        )
