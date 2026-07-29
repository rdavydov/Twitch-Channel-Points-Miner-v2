import uuid
from datetime import datetime
from typing import Any

from dateutil import parser
from dateutil.parser import ParserError

from TwitchChannelPointsMiner.classes.entities.EventPrediction import (
    EventPrediction,
    Outcome,
    Prediction,
    Result,
    ResultType,
)
from TwitchChannelPointsMiner.JSONDictDecoder import (
    InvalidValueError,
    JSONDictDecoder,
    WrongTypeError,
    expect_type_and_map,
    str_validator,
)

type UUID = str


def __parse_uuid(string: str) -> UUID:
    try:
        uuid.UUID(string)
        return string
    except ValueError:
        raise WrongTypeError([], UUID, string)


def uuid_decoder(context: JSONDictDecoder, data: Any) -> UUID:
    """
    Parses a UUID object from a string into a datetime object.

    :param context: The decoder that can be used to
    :param data: The data to decode.
    :return: The decoded UUID.
    """
    return expect_type_and_map(context, data, str, __parse_uuid)


def __parse_datetime(data: str) -> datetime:
    try:
        return parser.parse(data)
    except ParserError:
        raise InvalidValueError([], data)


def iso8601_datetime_decoder(context: JSONDictDecoder, data: Any) -> datetime:
    """
    Parses a datetime object from a string into a datetime object.

    :param context: The decoder that can be used to parse the data as a string.
    :param data: The data to parse
    :return: The result datetime object.
    """
    return expect_type_and_map(context, data, str, __parse_datetime)


def result_type_validator(data: str) -> ResultType:
    """
    Validates that a string represents a valid ResultType.

    :param data: The string to validate.
    :return: The validated ResultType.
    :raises WrongTypeError: If the string is not a valid ResultType.
    """
    try:
        return ResultType(data)
    except ValueError:
        raise WrongTypeError([], ResultType, data)


def result_type_decoder(context: JSONDictDecoder, data: Any) -> ResultType:
    """
    Decodes an ResultType from a Twitch PubSub message.

    :param context: The decoder that can be used to decode child properties.
    :param data: The data to decode.
    :return: The decoded ResultType.
    """
    return expect_type_and_map(context, data, str, result_type_validator)


def result_decoder(context: JSONDictDecoder, data: dict[str, Any]) -> Result:
    """
    Decodes a Result from a Twitch PubSub message.

    Examples:
    {
        "type": "LOSE",
        "points_won": null,
        "is_acknowledged": false
    }

    {
        "type": "REFUND",
        "points_won": null,
        "is_acknowledged": false
    }

    {
        "type": "WIN",
        "points_won": 5000,
        "is_acknowledged": false
    }

    :param context: The decoder that can be used to decode child properties.
    :param data: The data that represents a Result.
    :return: The decoded Result.
    """
    result_type = context.decode_property(data, "type", ResultType)
    points_won = context.decode_property(data, "points_won", int | None)
    return Result(result_type, points_won)


def prediction_decoder(context: JSONDictDecoder, data: Any) -> Prediction:
    """
    Parses a Prediction from a Twitch PubSub message.

    Format:
    {
        "id": SHA256,
        "event_id": UUID,
        "outcome_id": UUID,
        "channel_id": str,
        "points": int,
        "predicted_at": ISO8601,
        "updated_at": ISO8601,
        "user_id": str,
        "result": Result | None,
        "user_display_name": str,
    }

    Examples:
    From a prediction-made event:
    {
        "timestamp": "2025-01-25T16:57:55.175990754Z",
        "prediction": {
            "id": "c2c9c9defd40d072942ab3515a769972a49c43e2673c8023fb4e6150893b03eb",
            "event_id": "2f862332-a33f-4636-8623-32a33fd63677",
            "outcome_id": "28fca425-8c27-4b7d-bca4-258c273b7d96",
            "channel_id": "112358126",
            "points": 1000,
            "predicted_at": "2025-01-25T16:57:55.129766307Z",
            "updated_at": "2025-01-25T16:57:55.129766307Z",
            "user_id": "85647234",
            "result": null,
            "user_display_name": null
        }
    }

    From a prediction-updated event:
    {
        "timestamp": "2025-01-25T16:58:49.311849985Z",
        "prediction": {
            "id": "c2c9c9defd40d072942ab3515a769972a49c43e2673c8023fb4e6150893b03eb",
            "event_id": "2f862332-a33f-4636-8623-32a33fd63677",
            "outcome_id": "28fca425-8c27-4b7d-bca4-258c273b7d96",
            "channel_id": "112358126",
            "points": 2000,
            "predicted_at": "2025-01-25T16:57:55.129766307Z",
            "updated_at": "2025-01-25T16:58:49.265743919Z",
            "user_id": "85647234",
            "result": null,
            "user_display_name": null
        }
    }

    From a prediction-result event:
    {
        "timestamp": "2025-01-25T17:06:12.608913257Z",
        "prediction": {
            "id": "c2c9c9defd40d072942ab3515a769972a49c43e2673c8023fb4e6150893b03eb",
            "event_id": "2f862332-a33f-4636-8623-32a33fd63677",
            "outcome_id": "28fca425-8c27-4b7d-bca4-258c273b7d96",
            "channel_id": "112358126",
            "points": 2000,
            "predicted_at": "2025-01-25T16:57:55.129766307Z",
            "updated_at": "2025-01-25T17:06:12.605388424Z",
            "user_id": "85647234",
            "result": {
                "type": "LOSE",
                "points_won": null,
                "is_acknowledged": false
            },
            "user_display_name": null
        }
    }

    :param context: The decoder that can be used to decode child properties.
    :param data: The data that represents a Prediction.
    :return: The decoded Prediction.
    """
    outcome_id = context.decode_property(data, "outcome_id", UUID)
    points = context.decode_property(data, "points", int)
    result = context.decode_property(data, "result", Result | None)
    return Prediction(outcome_id, points, result)


def outcome_decoder(context: JSONDictDecoder, data: dict[str, Any]) -> Outcome:
    """
    Decodes an Outcome from a Twitch PubSub message.

    Format:
    {
        "id": UUID,
        "color": str,
        "title": str,
        "total_points": int,
        "total_users": int,
        "top_predictors": list[Prediction],
        "badge": {
            "version": str,
            "set_id": str,
        }
    }

    Example:
    {
        "id": "01948aa2-3d35-7b74-a9be-09f05a25f6ca",
        "color": "BLUE",
        "title": "Option Value",
        "total_points": 0,
        "total_users": 0,
        "top_predictors": [],
        "badge": {
            "version": "blue-1",
            "set_id": "predictions"
        }
    }

    :param context: The decoder that can be used to decode child properties.
    :param data: The data that represents an Outcome.
    :return: The decoded Outcome.
    """
    identity = context.decode_property(data, "id", UUID)
    color = context.decode_property(data, "color", str)
    title = context.decode_property(data, "title", str)
    total_points = context.decode_property(data, "total_points", int)
    total_users = context.decode_property(data, "total_users", int)
    top_predictors = context.decode_property(data, "top_predictors", list[Prediction])

    return Outcome(identity, color, title, total_points, total_users, top_predictors)


def event_prediction_decoder(
    context: JSONDictDecoder, data: dict[str, Any]
) -> EventPrediction:
    """
    Decodes an EventPrediction from a Twitch PubSub message.
    Calls event.update() to calculate missing values.

    :param context: The decoder that can be used to decode child properties.
    :param data: The data that represents  an EventPrediction.
    :return: The decoded EventPrediction.
    """
    identity = context.decode_property(data, "id", UUID)
    title = context.decode_property(data, "title", str)
    created_at = context.decode_property(data, "created_at", datetime)
    prediction_window_seconds = context.decode_property(
        data, "prediction_window_seconds", int
    )
    status = context.decode_property(data, "status", str)
    outcomes = context.decode_property(data, "outcomes", list[Outcome])
    event = EventPrediction(
        identity, title, created_at, prediction_window_seconds, status, outcomes
    )
    event.update()
    return event


# Decoders for PubSub datatype
additional_decoders = {
    datetime: iso8601_datetime_decoder,
    UUID: str_validator,
    ResultType: result_type_decoder,
    Result: result_decoder,
    Prediction: prediction_decoder,
    Outcome: outcome_decoder,
    EventPrediction: event_prediction_decoder,
}
