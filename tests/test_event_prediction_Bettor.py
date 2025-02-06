from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from dateutil.tz import tzutc

from TwitchChannelPointsMiner.classes.entities.Bet import (
    Bet,
    FilterCondition,
    OutcomeKeys,
    Condition,
    BetSettings,
    Strategy,
)
from TwitchChannelPointsMiner.classes.entities.EventPrediction import (
    EventPrediction,
    Outcome,
    Result,
    Prediction,
)
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.classes.event_prediction.Bettor import (
    TimerEventPredictionBettor,
    EventPredictionBettor,
)

test_event = EventPrediction(
    "ae93da2f-1825-416a-93da-2f1825f16aaa",
    "title",
    datetime(2025, 1, 28, 15, 8, 34, 172168, tzinfo=tzutc()),
    60,
    "ACTIVE",
    [
        Outcome(
            "0c84407f-dc4e-4438-8440-7fdc4ea438f5",
            "Red",
            "Test Outcome 1",
            100,
            3,
            [],
            37.5,
            1.5,
            66.66,
            50,
        ),
        Outcome(
            "228ae041-bb0f-4de4-8ae0-41bb0f6de47c",
            "Blue",
            "Test Outcome 2",
            50,
            5,
            [],
            62.5,
            3,
            33.33,
            10,
        ),
    ],
    total_points=150,
    total_users=8,
)

test_bet = Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 500)


class EventPredictionBetterImpl(EventPredictionBettor):
    """Test implementation that does nothing for abstract members."""

    def new(
        self, streamer: Streamer, event: EventPrediction, current_timestamp: datetime
    ):
        pass

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


class TestEventPredictionBettor:
    @pytest.fixture
    def place_bet(self):
        return MagicMock()

    @pytest.fixture
    def bettor(self, place_bet):
        return EventPredictionBetterImpl(place_bet)

    test_skip_data = [
        (test_event, None, Bet("", 0), (False, 0)),
        (
            test_event,
            FilterCondition(OutcomeKeys.PERCENTAGE_USERS, Condition.GT, 10),
            test_bet,
            (False, 62.5),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.ODDS_PERCENTAGE, Condition.LT, 10),
            test_bet,
            (True, 33.33),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.ODDS, Condition.GTE, 3),
            test_bet,
            (False, 3),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.TOP_POINTS, Condition.LTE, 9),
            test_bet,
            (True, 10),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.DECISION_USERS, Condition.LTE, 5),
            test_bet,
            (False, 5),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.DECISION_POINTS, Condition.GT, 100),
            test_bet,
            (True, 50),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.TOTAL_USERS, Condition.LT, 20),
            test_bet,
            (False, 8),
        ),
        (
            test_event,
            FilterCondition(OutcomeKeys.TOTAL_POINTS, Condition.GTE, 200),
            test_bet,
            (True, 150),
        ),
    ]

    @pytest.mark.parametrize(
        "event_prediction,filter_condition,bet,expected", test_skip_data
    )
    def test_skip(self, bettor, event_prediction, filter_condition, bet, expected):
        streamer = Streamer("twitch")
        streamer.settings = StreamerSettings(
            bet=BetSettings(filter_condition=filter_condition)
        )
        streamer.event_predictions = {event_prediction.event_id: event_prediction}

        assert bettor.skip(streamer, event_prediction.event_id, bet) == expected

    test_create_bet_data = [
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.MOST_VOTED,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
            ),
            Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.HIGH_ODDS,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
            ),
            Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.PERCENTAGE,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
            ),
            Bet("0c84407f-dc4e-4438-8440-7fdc4ea438f5", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.SMART_MONEY,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
            ),
            Bet("0c84407f-dc4e-4438-8440-7fdc4ea438f5", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.SMART,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
                percentage_gap=5,
            ),
            Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.SMART,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
                percentage_gap=30,
            ),
            Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.NUMBER_1,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
            ),
            Bet("0c84407f-dc4e-4438-8440-7fdc4ea438f5", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.NUMBER_2,
                percentage=100,
                max_points=1000,
                stealth_mode=False,
            ),
            Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 1000),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.NUMBER_1,
                percentage=10,
                max_points=500,
                stealth_mode=False,
            ),
            Bet("0c84407f-dc4e-4438-8440-7fdc4ea438f5", 100),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.NUMBER_1,
                percentage=50,
                max_points=100,
                stealth_mode=False,
            ),
            Bet("0c84407f-dc4e-4438-8440-7fdc4ea438f5", 100),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.NUMBER_1,
                percentage=100,
                max_points=1000,
                stealth_mode=True,
            ),
            Bet("0c84407f-dc4e-4438-8440-7fdc4ea438f5", 50),
        ),
        (
            test_event,
            1000,
            BetSettings(
                strategy=Strategy.NUMBER_2,
                percentage=100,
                max_points=1000,
                stealth_mode=True,
            ),
            Bet("228ae041-bb0f-4de4-8ae0-41bb0f6de47c", 10),
        ),
    ]

    @pytest.mark.parametrize(
        "event_prediction,channel_points,bet_settings,expected", test_create_bet_data
    )
    def test_create_bet(
        self, bettor, event_prediction, channel_points, bet_settings, expected
    ):
        streamer = Streamer("twitch")
        streamer.channel_points = channel_points
        streamer.settings = StreamerSettings(bet=bet_settings)
        streamer.event_predictions = {event_prediction.event_id: event_prediction}

        assert bettor.create_bet(streamer, event_prediction.event_id) == expected

    test_create_and_place_bet_data = [
        (Bet("8c984695-2db8-47da-9846-952db837da8a", 1000), True, False),
        (Bet("67242f73-568f-49a4-a42f-73568f29a452", 1234), False, True),
        (None, False, False),
        (None, True, False),
    ]

    @pytest.mark.parametrize(
        "bet,should_skip,expect_place_bet_called", test_create_and_place_bet_data
    )
    def test_create_and_place_bet(
        self, place_bet, bettor, bet, should_skip, expect_place_bet_called
    ):
        # Tests that when the given bet and should_skip values are produced, place_bet either does or doesn't get called
        streamer = MagicMock()
        event_id = MagicMock()

        with patch.object(bettor, "create_bet") as mock_create_bet:
            mock_create_bet.return_value = bet
            with patch.object(bettor, "skip") as mock_skip:
                mock_skip.return_value = (should_skip, MagicMock())
                bettor.create_and_place_bet(streamer, event_id)
                if expect_place_bet_called:
                    place_bet.assert_called_once()
                else:
                    place_bet.assert_not_called()


class TestTimerEventPredictionBettor:

    @pytest.fixture
    def place_bet(self):
        return MagicMock()

    @pytest.fixture
    def timer_factory(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, place_bet, timer_factory):
        return TimerEventPredictionBettor(place_bet, timer_factory)

    test_new_event_close_time_data = [
        (-500, False),
        (-1, False),
        (0, False),
        (1, True),
        (500, True),
    ]

    @pytest.mark.parametrize("seconds,added", test_new_event_close_time_data)
    def test_new(self, manager, timer_factory, seconds, added):
        streamer = MagicMock()
        streamer.get_time_until_place_bet.return_value = seconds
        event_predictions = MagicMock()
        event_predictions.__contains__.return_value = True
        streamer.event_predictions = event_predictions
        event_prediction = MagicMock()
        event_prediction.created_at = datetime(2020, 1, 1, 0, 0, 0)
        current_timestamp = datetime(2020, 1, 1, 0, 0, 0)

        streamer.settings = StreamerSettings(bet=BetSettings())
        streamer.channel_points = 100

        manager.new(streamer, event_prediction, current_timestamp)

        streamer.get_time_until_place_bet.assert_called_once()
        if added:
            timer_factory.assert_called_once()
        else:
            timer_factory.assert_not_called()
