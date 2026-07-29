from datetime import datetime, timezone
from typing import Any

import pytest

from TwitchChannelPointsMiner.JSONDictDecoder import WrongTypeError, JSONDictDecoder, DecoderError
from TwitchChannelPointsMiner.classes.PubSub import (
    uuid_decoder, iso8601_datetime_decoder, prediction_decoder,
    additional_decoders, outcome_decoder, event_prediction_decoder, result_decoder
)
from TwitchChannelPointsMiner.classes.entities.EventPrediction import (
    Prediction, Result, ResultType, Outcome,
    EventPrediction
)


def identity(d, x: Any):
    return x


@pytest.fixture
def context():
    return JSONDictDecoder().with_decoders(additional_decoders)


test_uuid_decoder_data = [
    "690f702f-df58-4158-8f70-2fdf58a1587a",
    "6378fe53-320f-4158-b8fe-53320fa158ab",
    "00539e51-35e2-4833-939e-5135e288337b",
    "b4645580-e7fb-40d4-a455-80e7fba0d418",
    "04bc8dce-fce5-44ee-bc8d-cefce514ee0f",
    "21f0427a-652b-4407-b042-7a652b2407d4",
    "14ccedf1-043b-4f20-8ced-f1043b7f20f6"
]


@pytest.mark.parametrize("data", test_uuid_decoder_data)
def test_uuid_decoder(context, data):
    assert uuid_decoder(context, data) == data


test_uuid_decoder_error_data = [
    "",
    "invalid uuid string",
    "oasuhdashdklha-sdfkjahsdkhj-sdhjasdjh-asdkljashdl-asdhkgasdkhj",
    None,
    0,
    1,
    1234,
    -1234,
    True,
    False,
    {"some key": "3c940db4-aefc-4231-940d-b4aefcb231bc"},
    {"f04254f5-bbf3-49fd-8254-f5bbf3c9fdac": "some value"},
    123.4312
]


@pytest.mark.parametrize("data", test_uuid_decoder_error_data)
def test_uuid_decoder_error(context, data):
    with pytest.raises(WrongTypeError):
        uuid_decoder(context, data)


# Twitch gives us timestamps with nanosecond precision but when we parse them we only get microseconds
# the underlying library just truncates the nanosecond to the leftmost 6 numbers so that's what we're checking here
test_iso8601_datatime_decoder_data = [
    ("2025-01-25T16:57:55.129766307Z", datetime(2025, 1, 25, 16, 57, 55, 129766, tzinfo=timezone.utc)),
    ("2025-01-25T16:58:49.265743919Z", datetime(2025, 1, 25, 16, 58, 49, 265743, tzinfo=timezone.utc)),
    ("2025-01-25T17:06:12.605388424Z", datetime(2025, 1, 25, 17, 6, 12, 605388, tzinfo=timezone.utc)),
    ("2025-01-28T11:12:04.054347319Z", datetime(2025, 1, 28, 11, 12, 4, 54347, tzinfo=timezone.utc))
]


@pytest.mark.parametrize("data,expected", test_iso8601_datatime_decoder_data)
def test_iso8601_datatime_decoder(context, data, expected):
    assert iso8601_datetime_decoder(context, data) == expected


test_iso8601_datetime_decoder_error_data = [
    None,
    "",
    "invalid string",
    "asdf-fd-psTdj:ds:aq:xd.duhenztbvZ",
    datetime(2025, 1, 25, 16, 57, 55, 129766, tzinfo=timezone.utc),
    True,
    0
]


@pytest.mark.parametrize("data", test_iso8601_datetime_decoder_error_data)
def test_iso8601_datatime_decoder_error(context, data):
    with pytest.raises(DecoderError):
        iso8601_datetime_decoder(context, data)


test_prediction_decoder_data = [
    (
        {
            "id": "7bd2142758a778996985f5a681777bb910d3c5cc3767cd80679a1007ea87fbd1",
            "event_id": "4ce707e4-71f6-4ef8-a707-e471f6eef888",
            "outcome_id": "49d554a5-e5e8-43d6-9554-a5e5e873d636",
            "points": 1234,
            "predicted_at": "2025-01-25T16:57:55.129766307Z",
            "result": None,
        },
        Prediction(
            "49d554a5-e5e8-43d6-9554-a5e5e873d636",
            1234,
            None
        )
    ),
    (
        {
            "outcome_id": "e703761d-b642-44c8-8376-1db642e4c860",
            "points": 5000,
            "result": {
                "type": "LOSE",
                "points_won": None
            }
        },
        Prediction(
            "e703761d-b642-44c8-8376-1db642e4c860",
            5000,
            Result(
                ResultType.LOSE,
                None
            )
        )
    )
]


@pytest.mark.parametrize("data,expected", test_prediction_decoder_data)
def test_prediction_decoder(context, data, expected):
    assert prediction_decoder(context, data) == expected


test_prediction_decoder_error_data = [
    None,
    "Prediction",
    True,
    False,
    0,
    1,
    1234,
    {},
    {
        "outcome_id": 1234,
        "points": 5000.1234,
    },
    {
        "outcome_id": "1c29d446-bd9c-46ec-a9d4-46bd9c96ecf9",
        "points": 5000,
        "result": {}
    }
]


@pytest.mark.parametrize("data", test_prediction_decoder_error_data)
def test_prediction_decoder_error(context, data):
    with pytest.raises(DecoderError):
        prediction_decoder(context, data)


test_outcome_decoder_data = [
    (
        {
            "id": "3cefff44-1f1e-4b8e-afff-441f1e5b8e81",
            "color": "Red",
            "title": "Test Outcome Title",
            "total_points": 0,
            "total_users": 0,
            "top_predictors": []
        },
        Outcome(
            "3cefff44-1f1e-4b8e-afff-441f1e5b8e81",
            "Red",
            "Test Outcome Title",
            0,
            0,
            []
        )
    ),
    (
        {
            "id": "8701244c-91ca-4dbe-8124-4c91ca0dbe04",
            "color": "Blue",
            "title": "Another Outcome Title",
            "total_points": 1234,
            "total_users": 1,
            "top_predictors": [
                {
                    "outcome_id": "8701244c-91ca-4dbe-8124-4c91ca0dbe04",
                    "points": 1234,
                    "result": None
                }
            ]
        },
        Outcome(
            "8701244c-91ca-4dbe-8124-4c91ca0dbe04",
            "Blue",
            "Another Outcome Title",
            1234,
            1,
            [
                Prediction(
                    "8701244c-91ca-4dbe-8124-4c91ca0dbe04",
                    1234,
                    None
                )
            ]
        )
    )
]


@pytest.mark.parametrize("data,expected", test_outcome_decoder_data)
def test_outcome_decoder(context, data, expected):
    assert outcome_decoder(context, data) == expected


test_outcome_decoder_error_data = [
    {
        "outcome_id": "764dc2f5-fa4d-47e0-8dc2-f5fa4d07e06e",
        "color": None,
        "title": 1000,
        "points": "1234",
        "users": True,
        "predictors": []
    }
]


@pytest.mark.parametrize("data", test_outcome_decoder_error_data)
def test_outcome_decoder_error(context, data):
    with pytest.raises(DecoderError):
        outcome_decoder(context, data)


test_event_prediction_decoder_data = [
    (
        {
            "id": "2fad7077-db86-4196-ad70-77db86b19622",
            "title": "Test Event Title",
            "created_at": "2025-01-28T14:26:44.782764781Z",
            "prediction_window_seconds": 120,
            "status": "ACTIVE",
            "outcomes": []
        },
        EventPrediction(
            "2fad7077-db86-4196-ad70-77db86b19622",
            "Test Event Title",
            datetime(2025, 1, 28, 14, 26, 44, 782764, tzinfo=timezone.utc),
            120,
            "ACTIVE",
            []
        )
    )
]


@pytest.mark.parametrize("data,expected", test_event_prediction_decoder_data)
def test_event_prediction_decoder(context, data, expected):
    assert event_prediction_decoder(context, data) == expected


test_event_prediction_decoder_error_data = [
    None,
    True,
    False,
    0,
    1,
    1234,
    {},
    {
        "id": 1234,
        "title": None,
        "prediction_window_seconds": 120.58,
        "status": "active",
        "outcomes": [
            {}
        ]
    }
]


@pytest.mark.parametrize("data", test_event_prediction_decoder_error_data)
def test_event_prediction_decoder_error(context, data):
    with pytest.raises(DecoderError):
        event_prediction_decoder(context, data)


test_result_decoder_data = [
    (
        {
            "type": "LOSE",
            "points_won": None,
            "is_acknowledged": False
        },
        Result(ResultType.LOSE, None)
    ),
    (
        {
            "type": "REFUND",
            "points_won": None,
            "is_acknowledged": False
        },
        Result(ResultType.REFUND, None)
    ),
    (
        {
            "type": "WIN",
            "points_won": 5000,
            "is_acknowledged": False
        },

        Result(ResultType.WIN, 5000)
    )
]


@pytest.mark.parametrize("data,expected", test_result_decoder_data)
def test_result_decoder(context, data, expected):
    assert result_decoder(context, data) == expected


test_result_decoder_error_data = [
    None,
    True,
    False,
    0,
    1,
    1234,
    {},
    {
        "result_type": "WIN",
        "points_won": None,
    },
    {
        "type": "win",
        "points_won": 5000,
    },
    {
        "type": "LOSE",
        "points_won": 1234.4321,
    }
]


@pytest.mark.parametrize("data", test_result_decoder_error_data)
def test_result_decoder_error(context, data):
    with pytest.raises(DecoderError):
        result_decoder(context, data)
