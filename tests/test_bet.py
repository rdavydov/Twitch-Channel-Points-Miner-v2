from TwitchChannelPointsMiner.classes.entities.Bet import (
    Bet,
    BetSettings,
    FilterCondition,
    DelayMode
)
from TwitchChannelPointsMiner.classes.entities.Strategy import (
    Strategy,
    StrategySettings,
    Condition,
    OutcomeKeys
)
import pytest
from TwitchChannelPointsMiner.logger import LoggerSettings
from TwitchChannelPointsMiner.classes.Settings import Settings

@pytest.fixture
def bet_settings():
    settings = BetSettings(
        strategy=Strategy.SMART_HIGH_ODDS,
        percentage=50,
        only_doubt=False,
        max_points=50000,
        stealth_mode=False,
        delay_mode=DelayMode.FROM_END,
        delay=6,
        strategy_settings={
            "target_odd": 2.1
        }
    )
    return settings


@pytest.fixture
def outcomes():
    outcomes = [
        {
            "percentage_users": 50,
            "odds_percentage": 60,
            "odds": 1.67,
            "top_points": 600,
            "total_users": 1,
            "total_points": 600,
            "decision_users": 1,
            "decision_points": 1,
            "id": 1
        },
        {
            "percentage_users": 50,
            "odds_percentage": 40,
            "odds": 2.5,
            "top_points": 400,
            "total_users": 1,
            "total_points": 400,
            "decision_users": 1,
            "decision_points": 1,
            "id": 2
        }
    ]
    return outcomes


def test_settings(bet_settings, outcomes):
    bet = Bet(outcomes, bet_settings)
    calc = bet.calculate(1000)
    assert calc["choice"] == 1
    assert calc["amount"] == 145
    assert bet.decision == {"amount": 145, "choice": 1, "id": 2}  # important


def test_settings2(bet_settings, outcomes):
    outcomes[1]["odds"] = 12
    outcomes[0]["odds"] = 1.09
    outcomes[0]["top_points"] = 4400
    outcomes[0]["total_points"] = 4400
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["amount"] == 480


def test_settings3(bet_settings, outcomes):
    outcomes[1]["odds"] = 13
    outcomes[0]["odds"] = 1.08
    outcomes[1]["top_points"] = 50
    outcomes[1]["total_points"] = 50
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["amount"] == 50


def test_settings4(bet_settings, outcomes):
    outcomes[1]["odds"] = 2
    outcomes[0]["odds"] = 2
    outcomes[1]["top_points"] = 600
    outcomes[1]["total_points"] = 600
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["amount"] == 10


def test_settings5(bet_settings, outcomes):
    outcomes = [outcomes[1], outcomes[0]]
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0
    assert bet["amount"] == 145


def test_update_outcomes(bet_settings, outcomes):
    bet = Bet(outcomes, bet_settings)
    outcomes[0]["top_points"] = 0
    outcomes[0]["top_predictors"] = [{"points": 100}, {"points": 200}]
    outcomes[1]["top_predictors"] = [{"points": 100}, {"points": 300}]
    outcomes[0]["total_users"] = 1
    outcomes[1]["total_users"] = 3
    outcomes[0]["total_points"] = 800
    outcomes[1]["total_points"] = 200
    bet.update_outcomes(outcomes)
    assert bet.outcomes[0]["top_points"] == 200
    assert bet.outcomes[1]["top_points"] == 300
    assert bet.outcomes[0]["percentage_users"] == 25
    assert bet.outcomes[1]["percentage_users"] == 75
    assert bet.outcomes[0]["odds"] == 1.25
    assert bet.outcomes[1]["odds"] == 5
    assert bet.outcomes[0]["odds_percentage"] == 80
    assert bet.outcomes[1]["odds_percentage"] == 20


def test_stealth_mode(bet_settings, outcomes):
    bet_settings.stealth_mode = True
    outcomes[1]["top_points"] = 80
    for x in range(10):
        bet = Bet(outcomes, bet_settings).calculate(1000)
        assert bet["amount"] >= 75
        assert bet["amount"] <= 79


def test_always_bet(bet_settings, outcomes):
    Settings.logger = LoggerSettings()
    outcomes[1]["odds"] = 2
    outcomes[0]["odds"] = 2
    bet = Bet(outcomes, bet_settings)
    bet.calculate(1000)
    skip = bet.skip()
    assert skip == (True, 0)
    bet_settings.strategy_settings.always_bet = True
    bet = Bet(outcomes, bet_settings)
    bet.calculate(1000)
    skip = bet.skip()
    assert skip == (False, 0)


def test_most_voted(bet_settings, outcomes):
    bet_settings.strategy = Strategy.MOST_VOTED
    bet_settings.percentage = 20
    outcomes[0]["total_users"] = 1
    outcomes[1]["total_users"] = 2
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 200
    outcomes[0]["total_users"] = 2
    outcomes[1]["total_users"] = 1
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0


def test_high_odds(bet_settings, outcomes):
    bet_settings.strategy = Strategy.HIGH_ODDS
    bet_settings.percentage = 20
    outcomes[0]["odds"] = 2
    outcomes[1]["odds"] = 3
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 200
    outcomes[0]["odds"] = 3
    outcomes[1]["odds"] = 2
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0


def test_percentage(bet_settings, outcomes):
    bet_settings.strategy = Strategy.PERCENTAGE
    bet_settings.percentage = 20
    outcomes[0]["odds_percentage"] = 2
    outcomes[1]["odds_percentage"] = 3
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 200
    outcomes[0]["odds_percentage"] = 3
    outcomes[1]["odds_percentage"] = 2
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0


def test_smart(bet_settings, outcomes):
    bet_settings = BetSettings(
        strategy=Strategy.SMART,
        strategy_settings={
            "percentage_gap": 1
        }
    )
    bet_settings.default()
    outcomes[0]["percentage_users"] = 30
    outcomes[1]["percentage_users"] = 70
    outcomes[0]["total_users"] = 30
    outcomes[1]["total_users"] = 70
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 50
    outcomes[0]["percentage_users"] = 60
    outcomes[1]["percentage_users"] = 40
    outcomes[0]["total_users"] = 60
    outcomes[1]["total_users"] = 40
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0


def test_smart2(bet_settings, outcomes):
    bet_settings = BetSettings(
        strategy=Strategy.SMART,
        strategy_settings={
            "percentage_gap": 99
        }
    )
    bet_settings.default()
    outcomes[0]["percentage_users"] = 30
    outcomes[1]["percentage_users"] = 70
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 50
    outcomes[0]["percentage_users"] = 60
    outcomes[1]["percentage_users"] = 40
    outcomes[0]["odds"] = 2
    outcomes[1]["odds"] = 1
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0


def test_only_doubt(bet_settings, outcomes):
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 145
    outcomes[1]["odds"] = 1.5
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 0
    assert bet["amount"] == 10
    bet_settings.only_doubt = True
    bet = Bet(outcomes, bet_settings).calculate(1000)
    assert bet["choice"] == 1
    assert bet["amount"] == 10


def test_skip(bet_settings, outcomes):
    bet_settings.filter_condition = FilterCondition(
        by=OutcomeKeys.ODDS,
        where=Condition.GT,
        value=2.4
    )
    bet = Bet(outcomes, bet_settings)
    bet.calculate(1000)
    skip = bet.skip()
    assert skip == (False, 2.5)


def test_skip2(bet_settings, outcomes):
    bet_settings.filter_condition = FilterCondition(
        by=OutcomeKeys.ODDS,
        where=Condition.GT,
        value=2.6
    )
    bet = Bet(outcomes, bet_settings)
    bet.calculate(1000)
    skip = bet.skip()
    assert skip == (True, 2.5)


def test_skip3(bet_settings, outcomes):
    Settings.logger = LoggerSettings()
    bet_settings.strategy_settings.target_odd = 2.5
    bet = Bet(outcomes, bet_settings)
    bet.calculate(1000)
    skip = bet.skip()
    assert skip == (True, 0)
