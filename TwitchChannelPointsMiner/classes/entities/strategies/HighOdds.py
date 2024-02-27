from TwitchChannelPointsMiner.classes.entities.Strategy import OutcomeKeys, Strategy


class HighOdds(Strategy):
    def calculate_middle(self):
        self.decision["choice"] = self.return_choice(OutcomeKeys.ODDS)
