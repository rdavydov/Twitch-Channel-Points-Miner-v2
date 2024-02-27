from TwitchChannelPointsMiner.classes.entities.Strategy import OutcomeKeys, Strategy


class Percentage(Strategy):
    def calculate_middle(self):
        self.decision["choice"] = self.return_choice(OutcomeKeys.ODDS_PERCENTAGE)
