import logging

from TwitchChannelPointsMiner.classes.entities.Strategy import OutcomeKeys, Strategy
from TwitchChannelPointsMiner.classes.Settings import Settings


logger = logging.getLogger(__name__)


class SmartHighOdds(Strategy):
    def both_odds_too_low(self) -> bool:
        return (
            self.outcomes[0][OutcomeKeys.ODDS]
            <= self.settings.strategy_settings.target_odd
            and self.outcomes[1][OutcomeKeys.ODDS]
            <= self.settings.strategy_settings.target_odd
        )

    def is_only_doubt(self) -> bool:
        return (
            self.outcomes[1][OutcomeKeys.ODDS]
            <= self.settings.strategy_settings.target_odd
            and self.settings.only_doubt
        )

    def log_skip(self, string) -> str:
        logger.info(
            string,
            extra={
                "emoji": ":pushpin:",
                "color": Settings.logger.color_palette.BET_GENERAL,
            },
        )

    def skip_middle(self):
        if self.settings.strategy_settings.always_bet:
            self.log_skip("always_bet activated")
            return False, 0

        if (
            self.outcomes[0][OutcomeKeys.TOTAL_POINTS] > 0
            and self.outcomes[1][OutcomeKeys.TOTAL_POINTS] == 0
        ):
            self.log_skip("No bet on B")
            return False, 0
        if (
            self.outcomes[0][OutcomeKeys.TOTAL_POINTS] == 0
            and self.outcomes[1][OutcomeKeys.TOTAL_POINTS] > 0
        ):
            if not self.settings.only_doubt:
                self.log_skip("No bet on A")
                return False, 0

        if self.both_odds_too_low() or self.is_only_doubt():
            if self.both_odds_too_low():
                self.log_skip("Odd is too low")
            elif self.is_only_doubt():
                self.log_skip("Odd is too low and only_doubt activated")
            self.log_skip(f"Target odd: {self.settings.strategy_settings.target_odd}")
            return True, 0  # Skip

    def calculate_sho_bet(self, index):
        low_odd_points = self.outcomes[1 - index][OutcomeKeys.TOTAL_POINTS]
        high_odd_points = self.outcomes[index][OutcomeKeys.TOTAL_POINTS]
        if self.both_odds_too_low() or self.is_only_doubt():
            return 10
        elif high_odd_points <= 50:  # in case no one bet
            return 50
        else:
            target_odd = self.settings.strategy_settings.target_odd
            if self.outcomes[index][OutcomeKeys.ODDS] > (target_odd * 2):
                # don't bet too much if odds is too high
                target_odd = self.outcomes[index][OutcomeKeys.ODDS] / 2
            return int((low_odd_points / (target_odd - 1)) - high_odd_points)

    def calculate_middle(self):
        self.decision["choice"] = self.return_choice(OutcomeKeys.ODDS)
        if self.decision["choice"] is not None:
            index = self.decision["choice"]
            self.decision["amount"] = int(self.calculate_sho_bet(index))


class SmartHighOddsSettings(object):
    __slots__ = [
        "target_odd",
        "always_bet",
    ]

    def __init__(
        self,
        target_odd: float = None,
        always_bet: bool = None,
    ):
        self.target_odd = target_odd
        self.always_bet = always_bet

    def default(self):
        self.target_odd = self.target_odd if self.target_odd is not None else 3
        self.always_bet = self.always_bet if self.always_bet is not None else False
