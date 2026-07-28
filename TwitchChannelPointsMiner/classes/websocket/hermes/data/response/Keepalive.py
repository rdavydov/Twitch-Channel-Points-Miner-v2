from datetime import datetime

from TwitchChannelPointsMiner.classes.websocket.hermes.data.response.Base import ResponseBase


class KeepaliveResponse(ResponseBase):
    """
    Represents a Hermes WebSocket Keepalive Response. Format:

    .. code-block:: javascript
        {
            "id": str,
            "type": "keepalive",
            "timestamp": str(datetime)
        }
    """

    def __init__(self, _id: str, timestamp: datetime):
        super().__init__(_id, "keepalive", timestamp)
