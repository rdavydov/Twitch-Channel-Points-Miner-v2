from datetime import datetime

from TwitchChannelPointsMiner.classes.websocket.hermes.data.response.Base import Subscription, ResponseBase


class SubscribeResponse(ResponseBase):
    """
    Represents a Hermes WebSocket Subscription Response. Format:

    .. code-block:: javascript
        {
            "subscribeResponse": {
                "subscription": {
                    "id": str
                },
                "result": "ok"
            },
            "id": str,
            "parentId": str,
            "type": "subscribeResponse",
            "timestamp": str(datetime)
        }
    """

    class Data:
        def __init__(self, result: str, subscription: Subscription):
            self.result = result
            self.subscription = subscription

    def __init__(self, _id: str, parent_id: str, timestamp: datetime, subscribe_response: Data):
        super().__init__(_id, "subscribeResponse", timestamp)
        self.parent_id = parent_id
        self.subscribe_response = subscribe_response
