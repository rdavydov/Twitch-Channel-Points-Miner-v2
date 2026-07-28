from datetime import datetime

from TwitchChannelPointsMiner.classes.websocket.hermes.data.request.Base import RequestBase
from TwitchChannelPointsMiner.utils import simple_repr, format_timestamp


class AuthenticateRequest(RequestBase):
    """
    Represents a Hermes WebSocket Authentication Request. Format:

    .. code-block:: javascript

        {
            "id": str,
            "type": "authenticate",
            "authenticate": {
                "token": str
            },
            "timestamp": str(datetime)
        }
    """

    class Data:
        def __init__(self, token: str):
            self.token = token

        def to_dict(self):
            return {
                "token": self.token
            }

        def __repr__(self):
            return simple_repr(self)

    def __init__(self, authenticate: Data, _id: str | None = None, timestamp: datetime | None = None):
        super().__init__("authenticate", _id, timestamp)
        self.authenticate = authenticate

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "authenticate": self.authenticate.to_dict(),
            "timestamp": format_timestamp(self.timestamp),
        }

    @staticmethod
    def create(token: str):
        return AuthenticateRequest(AuthenticateRequest.Data(token))
