from enum import Enum, auto
from importlib import import_module
from random import uniform


class Condition(Enum):
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()

    def __str__(self):
        return self.name


class OutcomeKeys(object):
    # Real key on Bet dict ['']
    PERCENTAGE_USERS = "percentage_users"
    ODDS_PERCENTAGE = "odds_percentage"
    ODDS = "odds"
    TOP_POINTS = "top_points"
    # Real key on Bet dict [''] - Sum()
    TOTAL_USERS = "total_users"
    TOTAL_POINTS = "total_points"
    # This key does not exist
    DECISION_USERS = "decision_users"
    DECISION_POINTS = "decision_points"


class Strategy(object):
    MOST_VOTED = "MostVoted"
    HIGH_ODDS = "HighOdds"
    SMART_HIGH_ODDS = "SmartHighOdds"
    PERCENTAGE = "Percentage"
    SMART = "Smart"

    def __init__(self, outcomes: list, settings: object):
        self.outcomes = outcomes
        self.decision: dict = {}
        self.settings = settings

    def get_instance(self):
        strategy_module = import_module(
            f".{self.settings.strategy}", package=f"{__package__}.strategies"
        )
        subclass = getattr(strategy_module, self.settings.strategy)
        return subclass(self.outcomes, self.settings)

    def return_choice(self, key) -> int:
        largest = 0
        for index in range(0, len(self.outcomes)):
            if self.outcomes[index][key] > self.outcomes[largest][key]:
                largest = index
        return largest

    def calculate_before(self):
        self.decision = {"choice": None, "amount": 0, "id": None}

    def calculate_middle(self):
        pass

    def calculate_after(self, balance: int):
        if self.settings.only_doubt:
            self.decision["choice"] = 1
        if self.decision["choice"] is not None:
            index = self.decision["choice"]
            self.decision["id"] = self.outcomes[index]["id"]
            amounts = [
                self.decision["amount"],
                int(balance * (self.settings.percentage / 100)),
                self.settings.max_points,
            ]
            self.decision["amount"] = min(x for x in amounts if x != 0)
            if (
                self.settings.stealth_mode is True
                and self.decision["amount"]
                >= self.outcomes[index][OutcomeKeys.TOP_POINTS]
            ):
                reduce_amount = uniform(1, 5)
                # check by
                # grep -r --include=*.log "Bet won't be placed as the amount -[0-9] is less than the minimum required 10" .
                self.decision["amount"] = (
                    self.outcomes[index][OutcomeKeys.TOP_POINTS] - reduce_amount
                )
                if self.decision["amount"] < 10: self.decision["amount"] = 10
            self.decision["amount"] = int(self.decision["amount"])

    def calculate(self, balance: int) -> dict:
        self.calculate_before()
        self.calculate_middle()
        self.calculate_after(balance)
        return self.decision

    def skip_before(self):
        pass

    def skip_middle(self):
        pass

    def skip_after(self):
        if self.settings.filter_condition is not None:
            # key == by , condition == where
            key = self.settings.filter_condition.by
            condition = self.settings.filter_condition.where
            value = self.settings.filter_condition.value

            fixed_key = (
                key
                if key not in [OutcomeKeys.DECISION_USERS, OutcomeKeys.DECISION_POINTS]
                else key.replace("decision", "total")
            )
            if key in [OutcomeKeys.TOTAL_USERS, OutcomeKeys.TOTAL_POINTS]:
                compared_value = (
                    self.outcomes[0][fixed_key] + self.outcomes[1][fixed_key]
                )
            else:
                outcome_index = self.decision["choice"]
                compared_value = self.outcomes[outcome_index][fixed_key]

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

    def skip(self) -> bool:
        skip_results = [self.skip_before(), self.skip_middle(), self.skip_after()]
        return next(item for item in skip_results if item is not None)

    def __str__(self):
        return self.name


class StrategySettings(object):
    def __init__(self, strategy: Strategy = None, **kwargs):
        strategy_module = import_module(
            f".{strategy}", package=f"{__package__}.strategies"
        )
        subclass = getattr(strategy_module, f"{strategy}Settings")
        self.instance = subclass(**kwargs)
        self.instance.default()

    def get_instance(self):
        return self.instance
