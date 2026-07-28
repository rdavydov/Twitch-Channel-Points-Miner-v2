import abc
import json

from TwitchChannelPointsMiner.classes.websocket.hermes.data.request import Request


class RequestEncoder(abc.ABC):
    """Abstract base class that encodes Requests into strings."""

    @abc.abstractmethod
    def encode(self, request: Request) -> str:
        raise NotImplementedError()


class JsonEncoder(RequestEncoder):
    """Encoder that encodes Requests into JSON format."""

    def encode(self, request: Request) -> str:
        return json.dumps(request.to_dict(), separators=(",", ":"))
