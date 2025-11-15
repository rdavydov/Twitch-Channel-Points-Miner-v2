from datetime import datetime

from TwitchChannelPointsMiner.classes.websocket.hermes.data.response.Base import ResponseBase
from TwitchChannelPointsMiner.utils import simple_repr


class WelcomeResponse(ResponseBase):
    """
    Represents a Hermes WebSocket Welcome Response. Example:

    .. code-block:: javascript
        {
            "welcome": {
                "keepaliveSec": int,
                "recoveryUrl": str(URL),
                "sessionId": str
            },
            "id": str,
            "type": "welcome",
            "timestamp": str(datetime)
        }
    """

    class Data:
        def __init__(self, keepalive_sec: int, recovery_url: str, session_id: str):
            self.keepalive_sec = keepalive_sec
            self.recovery_url = recovery_url
            self.session_id = session_id

        def __repr__(self):
            return simple_repr(self)

    def __init__(self, _id: str, timestamp: datetime, welcome: Data):
        super().__init__(_id, "welcome", timestamp)
        self.welcome = welcome
