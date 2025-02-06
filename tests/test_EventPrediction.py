from datetime import datetime
from unittest.mock import MagicMock

import pytest

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.classes.entities.Bet import OutcomeKeys
from TwitchChannelPointsMiner.classes.entities.EventPrediction import (
    Result, ResultType, Prediction, Outcome,
    EventPrediction
)
from TwitchChannelPointsMiner.logger import LoggerSettings


class TestResult:
    test_action_data = [
        (Result(ResultType.LOSE, None), "Lost"),
        (Result(ResultType.WIN, None), "Gained"),
        (Result(ResultType.REFUND, None), "Refunded"),
    ]

    @pytest.mark.parametrize("result,expected", test_action_data)
    def test_action(self, result, expected):
        assert result.action() == expected


class TestPrediction:
    test_describe_result_data = [
        (Prediction("4b5d3eb8-95b7-4a47-9d3e-b895b70a4760", 1234, None), ""),
        (Prediction("a836d01a-da58-4060-b6d0-1ada58e0606f", 1234, Result(ResultType.LOSE, None)), "LOSE, Lost: -1.23k"),
        (Prediction("0d7599fb-7dca-4288-b599-fb7dca428833", 432, Result(ResultType.REFUND, None)),
         "REFUND, Refunded: +0"),
        (Prediction("5dac57d0-9dab-42b4-ac57-d09dab82b489", 54321, Result(ResultType.WIN, 98765)),
         "WIN, Gained: +44.44k")
    ]

    @pytest.mark.parametrize("prediction,expected", test_describe_result_data)
    def test_describe_result(self, prediction, expected):
        assert prediction.describe_result() == expected

    test_points_gained_data = [
        (Prediction("4b5d3eb8-95b7-4a47-9d3e-b895b70a4760", 1234, None), 0),
        (Prediction("a836d01a-da58-4060-b6d0-1ada58e0606f", 1234, Result(ResultType.LOSE, None)), -1234),
        (Prediction("0d7599fb-7dca-4288-b599-fb7dca428833", 432, Result(ResultType.REFUND, None)), 0),
        (Prediction("5dac57d0-9dab-42b4-ac57-d09dab82b489", 54321, Result(ResultType.WIN, 98765)), 44444)
    ]

    @pytest.mark.parametrize("prediction,expected", test_points_gained_data)
    def test_points_gained(self, prediction, expected):
        assert prediction.points_gained() == expected


class TestOutcome:
    @pytest.fixture
    def outcome(self):
        return Outcome(
            "94e5fc17-8948-48f4-a5fc-17894848f4bd",
            "Blue",
            "Test outcome",
            5000,
            5,
            [
                Prediction(
                    "94e5fc17-8948-48f4-a5fc-17894848f4bd",
                    3000,
                ),
                Prediction(
                    "94e5fc17-8948-48f4-a5fc-17894848f4bd",
                    1000
                ),
                Prediction(
                    "94e5fc17-8948-48f4-a5fc-17894848f4bd",
                    500,
                ),
                Prediction(
                    "94e5fc17-8948-48f4-a5fc-17894848f4bd",
                    250
                ),
                Prediction(
                    "94e5fc17-8948-48f4-a5fc-17894848f4bd",
                    250
                )
            ],
            50,
            3,
            33.33,
            3000
        )

    test_update_data = [
        (
            20,
            25000,
            25,
            5,
            20,
            3000
        )
    ]

    @pytest.mark.parametrize(
        "total_users,total_points,expected_percentage_users, expected_odds, expected_odds_percentage,expected_top_points",
        test_update_data
    )
    def test_update(
        self, outcome, total_users, total_points, expected_percentage_users, expected_odds, expected_odds_percentage,
        expected_top_points
    ):
        outcome.update(total_users, total_points)
        assert outcome.percentage_users == expected_percentage_users
        assert outcome.odds == expected_odds
        assert outcome.odds_percentage == expected_odds_percentage
        assert outcome.top_points == expected_top_points

    def test_get_value(self, outcome):
        assert outcome.get_value(OutcomeKeys.PERCENTAGE_USERS) == 50
        assert outcome.get_value(OutcomeKeys.ODDS_PERCENTAGE) == 33.33
        assert outcome.get_value(OutcomeKeys.ODDS) == 3
        assert outcome.get_value(OutcomeKeys.TOP_POINTS) == 3000
        assert outcome.get_value(OutcomeKeys.TOTAL_USERS) == 5
        assert outcome.get_value(OutcomeKeys.TOTAL_POINTS) == 5000
        assert outcome.get_value(OutcomeKeys.DECISION_USERS) == 5
        assert outcome.get_value(OutcomeKeys.DECISION_POINTS) == 5000


class TestEventPrediction:
    test_update_data = [
        ([], 0, 0),
        ([(100, 5), (50, 2), (300, 8), (150, 10)], 600, 25)
    ]

    @pytest.mark.parametrize("outcomes,expected_total_points,expected_total_users", test_update_data)
    def test_update(self, outcomes, expected_total_points, expected_total_users):
        mocked_outcomes = []
        for i in range(len(outcomes)):
            points, users = outcomes[i]
            mocked_outcome = MagicMock()
            mocked_outcome.total_points = points
            mocked_outcome.total_users = users
            mocked_outcomes.append(mocked_outcome)
        event = EventPrediction(
            "e818dbe8-eeed-4e46-98db-e8eeed2e464b",
            "Test Event Prediction",
            datetime(2020, 1, 1),
            120,
            "ACTIVE",
            [],
            {},
            0,
            0
        )
        event.update(mocked_outcomes)
        assert event.total_points == expected_total_points
        assert event.total_users == expected_total_users

        for outcome in mocked_outcomes:
            outcome.update.assert_called_once()

    def test_recap(self):
        Settings.logger = LoggerSettings()
        prediction = MagicMock()
        prediction.describe_result.return_value = "result description"
        event = EventPrediction(
            "5d8daf39-e79d-46a8-8daf-39e79d76a8b7",
            "Test Event",
            datetime(2020, 1, 1),
            120,
            "ACTIVE",
            [],
            total_points=0,
            total_users=0,
            prediction=prediction,
        )
        event.recap()
        prediction.describe_result.assert_called_once()

    test_largest_matching_choice_id_data = [
        (
            [
                Outcome(
                    "d8dbbcfa-2cde-42ba-9bbc-fa2cdec2ba48",
                    "",
                    "",
                    0,
                    0,
                    [],
                    0,
                    0,
                    0,
                    0
                ),
                Outcome(
                    "d46cad25-d695-4403-acad-25d695940354",
                    "",
                    "",
                    100,
                    1,
                    [],
                    10,
                    11.5,
                    8.69,
                    100
                ),
                Outcome(
                    "32374e2d-a7be-4d7c-b74e-2da7bedd7cc7",
                    "",
                    "",
                    50,
                    5,
                    [],
                    50,
                    23,
                    4.34,
                    40
                ),
                Outcome(
                    "f47e38b1-60d8-465f-be38-b160d8065f9d",
                    "",
                    "",
                    1000,
                    4,
                    [],
                    40,
                    1.15,
                    86.95,
                    900
                ),
            ],
            {
                OutcomeKeys.PERCENTAGE_USERS: "32374e2d-a7be-4d7c-b74e-2da7bedd7cc7",
                OutcomeKeys.ODDS_PERCENTAGE: "f47e38b1-60d8-465f-be38-b160d8065f9d",
                OutcomeKeys.ODDS: "32374e2d-a7be-4d7c-b74e-2da7bedd7cc7",
                OutcomeKeys.TOP_POINTS: "f47e38b1-60d8-465f-be38-b160d8065f9d",
                OutcomeKeys.TOTAL_USERS: "32374e2d-a7be-4d7c-b74e-2da7bedd7cc7",
                OutcomeKeys.TOTAL_POINTS: "f47e38b1-60d8-465f-be38-b160d8065f9d",
                OutcomeKeys.DECISION_USERS: "32374e2d-a7be-4d7c-b74e-2da7bedd7cc7",
                OutcomeKeys.DECISION_POINTS: "f47e38b1-60d8-465f-be38-b160d8065f9d"
            }
        )
    ]

    @pytest.mark.parametrize("outcomes,expected", test_largest_matching_choice_id_data)
    def test_largest_matching_choice_id(self, outcomes, expected):
        event = EventPrediction(
            "bb7d1452-3cb4-45da-bd14-523cb445da88",
            "Test Event",
            datetime(2020, 1, 1),
            120,
            "ACTIVE",
            outcomes
        )
        for key, expected_value in expected.items():
            assert event.largest_matching_choice_id(key) == expected_value

    def test_outcome_safe(self):
        outcome_ids = ["a", "b", "c", "d", "e", "f", "g", "h"]
        event = EventPrediction(
            "",
            "",
            datetime(2020, 1, 1),
            120,
            "ACTIVE",
            list(
                map(
                    lambda identity: Outcome(
                        identity,
                        "",
                        "",
                        0,
                        0,
                        []
                    ), outcome_ids
                )
            )
        )
        assert event.outcome_safe(0) == "a"
        assert event.outcome_safe(1) == "b"
        assert event.outcome_safe(2) == "c"
        assert event.outcome_safe(3) == "d"
        assert event.outcome_safe(4) == "e"
        assert event.outcome_safe(5) == "f"
        assert event.outcome_safe(6) == "g"
        assert event.outcome_safe(7) == "h"
        assert event.outcome_safe(8) == "a"
        assert event.outcome_safe(100) == "a"
        assert event.outcome_safe(-10) == "a"
