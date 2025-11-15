from datetime import datetime

from TwitchChannelPointsMiner.classes.websocket.hermes.data.response.Base import ResponseBase
from TwitchChannelPointsMiner.utils import simple_repr


class ReconnectResponse(ResponseBase):
    """
    Represents a Hermes WebSocket Reconnect Response. Format:

    .. code-block:: javascript
        {
            "reconnect": {
                "url": str(URL)
            },
            "id": str,
            "type": "reconnect",
            "timestamp": str(datetime)
        }
    """

    class Data:
        def __init__(self, url: str):
            self.url = url

        def __repr__(self):
            return simple_repr(self)

    def __init__(self, _id: str, timestamp: datetime, reconnect: Data):
        super().__init__(_id, "reconnect", timestamp)
        self.reconnect = reconnect
