import abc
import json

import dateutil.parser

from TwitchChannelPointsMiner.classes.websocket.hermes.data.response import (
    Response, WelcomeResponse, AuthenticateResponse,
    SubscribeResponse, Subscription, KeepaliveResponse, NotificationResponse, ReconnectResponse
)


def decode_timestamp(value: str):
    return dateutil.parser.parse(value)


def decode_int(value: str):
    return int(value)


def decode_welcome_data(data: dict):
    return WelcomeResponse.Data(decode_int(data["keepaliveSec"]), data["recoveryUrl"], data["sessionId"])


def decode_authenticate_response_data(data: dict):
    result = data["result"]
    if result == "ok":
        return AuthenticateResponse.DataOk()
    else:
        return AuthenticateResponse.DataError(result, data["error"], data["errorCode"])


def decode_subscription(data: dict):
    return Subscription(data["id"])


def decode_subscribe_response_data(data: dict):
    return SubscribeResponse.Data(data["result"], decode_subscription(data["subscription"]))


def decode_notification_response_data(data: dict):
    _type = data["type"]
    if _type == "pubsub":
        return NotificationResponse.PubSubData(decode_subscription(data["subscription"]), data["pubsub"])
    else:
        raise ValueError(f"Invalid subscription type {_type} when decoding NotificationResponse.")


def decode_reconnect_response_data(data: dict):
    return ReconnectResponse.Data(data["url"])


def decode_response(data: dict) -> Response:
    """
    Decodes a dict into a Response object. Expects the dict to come from something like `json.loads`.
    :param data: The data to decode.
    :return: The decoded Response.
    :raises ValueError:
        If an invalid type is found or the object contains improperly formatted data. i.e. a string that should be an
        int.
    :raises KeyError:
        If the object does not have an expected attribute.
    :raises ParserError | OverflowError:
        If, while parsing a datetime, it is in the wrong format or a value is too large to be contained in an int.
    """
    _id = data["id"]
    _type = data["type"]
    timestamp = decode_timestamp(data["timestamp"])
    if _type == "welcome":
        return WelcomeResponse(_id, timestamp, decode_welcome_data(data["welcome"]))
    elif _type == "keepalive":
        return KeepaliveResponse(_id, timestamp)
    elif _type == "authenticateResponse":
        return AuthenticateResponse(
            _id, data["parentId"], timestamp, decode_authenticate_response_data(data["authenticateResponse"])
        )
    elif _type == "subscribeResponse":
        return SubscribeResponse(
            _id, data["parentId"], timestamp, decode_subscribe_response_data(data["subscribeResponse"])
        )
    elif _type == "notification":
        return NotificationResponse(_id, timestamp, decode_notification_response_data(data["notification"]))
    elif _type == "reconnect":
        return ReconnectResponse(_id, timestamp, decode_reconnect_response_data(data["reconnect"]))
    else:
        raise ValueError(f"Invalid type {_type} when decoding Response.")


class ResponseDecoder(abc.ABC):
    """Abstract base class for decoding strings into Responses."""

    @abc.abstractmethod
    def decode(self, data: str) -> Response:
        raise NotImplementedError()


class JsonDecoder(ResponseDecoder):
    """Class that decodes response strings that are in JSON format."""

    def decode(self, data: str) -> Response:
        return decode_response(json.loads(data))
