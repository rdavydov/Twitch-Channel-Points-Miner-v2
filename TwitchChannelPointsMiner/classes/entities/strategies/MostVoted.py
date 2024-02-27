from TwitchChannelPointsMiner.classes.entities.Strategy import OutcomeKeys, Strategy


class MostVoted(Strategy):
    def calculate_middle(self):
        self.decision["choice"] = self.return_choice(OutcomeKeys.TOTAL_USERS)
