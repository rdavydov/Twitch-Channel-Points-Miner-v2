from datetime import datetime
from unittest import mock
from unittest.mock import MagicMock, call

import pytest

from TwitchChannelPointsMiner.classes.entities.Bet import BetSettings
from TwitchChannelPointsMiner.classes.entities.Streamer import StreamerSettings
from TwitchChannelPointsMiner.classes.event_prediction.Manager import (
    EventPredictionTracker,
    EventPredictionManager,
)


class TestEventPredictionTracker:
    @pytest.fixture
    def manager(self):
        return EventPredictionTracker()

    def test_new_event_already_exists(self, manager):
        # Tests that the same event cannot be added twice
        streamer = MagicMock()
        event_predictions = MagicMock()
        event_predictions.__contains__.return_value = True
        streamer.event_predictions = event_predictions
        event_prediction = MagicMock()
        event_prediction.event_id = "a809192f-22a0-4499-8919-2f22a0b499b5"
        current_timestamp = MagicMock()

        manager.new(streamer, event_prediction, current_timestamp)

        event_predictions.__setitem__.assert_not_called()

    test_update_outcomes_data = [
        (False),
        (True),
    ]

    @pytest.mark.parametrize("event_already_exists", test_update_outcomes_data)
    def test_update(self, manager, event_already_exists):
        # Tests that update:
        # 1. Ignores events that don't already exist
        # 2. Sets the new event data in the case that it does
        event_id = "fc775443-72fb-4473-b754-4372fb1473ad"
        streamer = MagicMock()
        event_predictions = MagicMock()
        streamer.event_predictions = event_predictions
        event_predictions.__contains__.return_value = event_already_exists
        if event_already_exists:
            old_event = MagicMock()
            old_event.id = event_id
            old_prediction = MagicMock()
            old_event.prediction = old_prediction
        else:
            old_event = None
            old_prediction = None
        event_predictions.__getitem__.return_value = old_event
        current_timestamp = MagicMock()

        new_event = MagicMock()
        new_event.event_id = event_id

        manager.update(streamer, new_event, current_timestamp)

        if event_already_exists:
            streamer.event_predictions.__setitem__.assert_called_once()
        else:
            streamer.event_predictions.__setitem__.assert_not_called()

    def test_update_keeps_prediction(self, manager):
        streamer = MagicMock()
        original_event = MagicMock()
        original_event.event_id = "024f17bf-9890-434e-8f17-bf9890734ec3"
        prediction = MagicMock()
        original_event.prediction = prediction
        streamer.event_predictions = {original_event.event_id: original_event}
        current_timestamp = MagicMock()
        new_event = MagicMock()
        new_event.event_id = original_event.event_id
        with mock.patch.object(manager, "new") as new_method:
            manager.update(streamer, new_event, current_timestamp)
            new_method.assert_not_called()
            assert streamer.event_predictions[original_event.event_id] == new_event
            assert new_event.prediction == prediction

    def test_prediction_updated(self, manager):
        streamer = MagicMock()
        event = MagicMock()
        event.event_id = "216783ce-c7aa-4538-a783-cec7aa453835"
        streamer.event_predictions = {event.event_id: event}
        prediction = MagicMock()

        manager.prediction_updated(streamer, event.event_id, prediction)

        assert event.prediction == prediction

    test_result_data = [("WIN", 2), ("LOSE", 1), ("REFUND", 2)]

    @pytest.mark.parametrize("result_type,calls", test_result_data)
    def test_result(self, manager, result_type, calls):
        streamer = MagicMock()
        event = MagicMock()
        event.event_id = "147bf1d7-d1ac-4573-bbf1-d7d1ace57371"
        event.prediction = MagicMock()
        event.prediction.outcome_id = "4ca0f0ca-ac57-4487-a0f0-caac57a487ae"
        outcome = MagicMock()
        event.outcomes_by_id = {event.prediction.outcome_id: outcome}
        streamer.event_predictions = {event.event_id: event}

        result = MagicMock()
        manager.result(streamer, event.event_id, result)

        assert event.prediction.result == result

        streamer.update_history.call_count = calls


class TestEventPredictionManager:
    @pytest.fixture
    def sub_manager_1(self):
        return MagicMock()

    @pytest.fixture
    def sub_manager_2(self):
        return MagicMock()

    @pytest.fixture
    def sub_manager_3(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, sub_manager_1, sub_manager_2, sub_manager_3):
        return EventPredictionManager(sub_manager_1, sub_manager_2, sub_manager_3)

    def test_new(self, sub_manager_1, sub_manager_2, sub_manager_3, manager):
        parent_mock = MagicMock()
        parent_mock.attach_mock(sub_manager_1, "sub_manager_1")
        parent_mock.attach_mock(sub_manager_2, "sub_manager_2")
        parent_mock.attach_mock(sub_manager_3, "sub_manager_3")
        streamer = MagicMock()
        event = MagicMock()
        current_timestamp = MagicMock()
        manager.new(streamer, event, current_timestamp)
        parent_mock.assert_has_calls(
            [
                call.sub_manager_1.new(streamer, event, current_timestamp),
                call.sub_manager_2.new(streamer, event, current_timestamp),
                call.sub_manager_3.new(streamer, event, current_timestamp),
            ],
            any_order=False,
        )

    def test_update(self, sub_manager_1, sub_manager_2, sub_manager_3, manager):
        parent_mock = MagicMock()
        parent_mock.attach_mock(sub_manager_1, "sub_manager_1")
        parent_mock.attach_mock(sub_manager_2, "sub_manager_2")
        parent_mock.attach_mock(sub_manager_3, "sub_manager_3")
        streamer = MagicMock()
        event = MagicMock()
        current_timestamp = MagicMock()
        manager.update(streamer, event, current_timestamp)
        parent_mock.assert_has_calls(
            [
                call.sub_manager_1.update(streamer, event, current_timestamp),
                call.sub_manager_2.update(streamer, event, current_timestamp),
                call.sub_manager_3.update(streamer, event, current_timestamp),
            ],
            any_order=False,
        )

    def test_prediction_updated(self, sub_manager_1, sub_manager_2, sub_manager_3, manager):
        parent_mock = MagicMock()
        parent_mock.attach_mock(sub_manager_1, "sub_manager_1")
        parent_mock.attach_mock(sub_manager_2, "sub_manager_2")
        parent_mock.attach_mock(sub_manager_3, "sub_manager_3")
        streamer = MagicMock()
        event_id = MagicMock()
        prediction = MagicMock()
        manager.prediction_updated(streamer, event_id, prediction)
        parent_mock.assert_has_calls(
            [
                call.sub_manager_1.prediction_updated(streamer, event_id, prediction),
                call.sub_manager_2.prediction_updated(streamer, event_id, prediction),
                call.sub_manager_3.prediction_updated(streamer, event_id, prediction),
            ],
            any_order=False,
        )

    def test_result(self, sub_manager_1, sub_manager_2, sub_manager_3, manager):
        parent_mock = MagicMock()
        parent_mock.attach_mock(sub_manager_1, "sub_manager_1")
        parent_mock.attach_mock(sub_manager_2, "sub_manager_2")
        parent_mock.attach_mock(sub_manager_3, "sub_manager_3")
        streamer = MagicMock()
        event_id = MagicMock()
        result = MagicMock()
        manager.result(streamer, event_id, result)
        parent_mock.assert_has_calls(
            [
                call.sub_manager_1.result(streamer, event_id, result),
                call.sub_manager_2.result(streamer, event_id, result),
                call.sub_manager_3.result(streamer, event_id, result),
            ],
            any_order=False,
        )
