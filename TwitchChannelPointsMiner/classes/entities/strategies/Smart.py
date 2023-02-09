from TwitchChannelPointsMiner.classes.entities.Strategy import OutcomeKeys, Strategy


class Smart(Strategy):
    def calculate_middle(self):
        difference = abs(
            self.outcomes[0][OutcomeKeys.PERCENTAGE_USERS]
            - self.outcomes[1][OutcomeKeys.PERCENTAGE_USERS]
        )
        self.decision["choice"] = (
            self.return_choice(OutcomeKeys.ODDS)
            if difference < self.settings.strategy_settings.percentage_gap
            else self.return_choice(OutcomeKeys.TOTAL_USERS)
        )


class SmartSettings(object):
    __slots__ = [
        "percentage_gap",
    ]

    def __init__(
        self,
        percentage_gap: float = None,
    ):
        self.percentage_gap = percentage_gap

    def default(self):
        self.percentage_gap = (
            self.percentage_gap if self.percentage_gap is not None else 20
        )
