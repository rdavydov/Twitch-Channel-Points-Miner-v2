import abc
from datetime import datetime

from TwitchChannelPointsMiner.classes.websocket.hermes.data.response.Base import ResponseBase, Subscription
from TwitchChannelPointsMiner.utils import simple_repr


class NotificationResponse(ResponseBase):
    """
    Represents a Hermes WebSocket Notification Response. Format:

    .. code-block:: javascript
        {
            "notification": {
                "subscription": {
                    "id": str
                },
                "type": "pubsub",
                "pubsub": str(PubSub Message)
            },
            "id": str,
            "type": "notification",
            "timestamp": str(datetime)
        }
    """

    class DataBase(abc.ABC):
        def __init__(self, subscription: Subscription, _type: str):
            self.subscription = subscription
            self.type = _type

        def __repr__(self):
            return simple_repr(self)

    class PubSubData(DataBase):
        def __init__(self, subscription: Subscription, pubsub: str):
            super().__init__(subscription, "pubsub")
            self.pubsub = pubsub

    type Data = NotificationResponse.PubSubData

    def __init__(self, _id: str, timestamp: datetime, notification: Data):
        super().__init__(_id, "notification", timestamp)
        self.notification = notification
