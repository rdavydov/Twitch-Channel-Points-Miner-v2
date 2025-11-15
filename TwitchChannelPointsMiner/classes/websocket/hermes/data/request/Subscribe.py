import abc
from datetime import datetime

from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.websocket.hermes.data.request.Base import RequestBase
from TwitchChannelPointsMiner.utils import create_random_id, simple_repr, format_timestamp


class SubscribeRequestBase(RequestBase, abc.ABC):
    class DataBase(abc.ABC):
        def __init__(self, _type: str, _id: str | None = None):
            self.id = _id or create_random_id(21)
            self.type = _type

        def __repr__(self):
            return simple_repr(self)

    def __init__(self, _id: str | None = None, timestamp: datetime | None = None):
        super().__init__("subscribe", _id, timestamp)


class SubscribePubSubRequest(SubscribeRequestBase):
    """
    Represents a Hermes WebSocket Subscription Request. Format:

    .. code-block:: javascript

        {
            "type": "subscribe",
            "id": str,
            "subscribe": {
                "id": str,
                "type": "pubsub",
                "pubsub": {
                    "topic": str(PubsubTopic)
                }
            },
            "timestamp": str(datetime)
        }
    """

    class Data(SubscribeRequestBase.DataBase):
        class PubSub:
            def __init__(self, topic: str):
                self.topic = topic

            def to_dict(self) -> dict:
                return {
                    "topic": self.topic,
                }

        def __init__(self, pubsub: PubSub, _id: str | None = None):
            super().__init__("pubsub", _id)
            self.pubsub = pubsub

        def to_dict(self):
            return {
                "id": self.id,
                "type": self.type,
                "pubsub": self.pubsub.to_dict()
            }

    def __init__(self, subscribe: Data, _id: str | None = None, timestamp: datetime | None = None):
        super().__init__(_id, timestamp)
        self.subscribe = subscribe

    def topic(self):
        return PubsubTopic(self.subscribe.pubsub.topic)

    def to_dict(self):
        return {
            "type": self.type,
            "id": self.id,
            "subscribe": self.subscribe.to_dict(),
            "timestamp": format_timestamp(self.timestamp),
        }

    @staticmethod
    def create(topic: PubsubTopic) -> "SubscribePubSubRequest":
        return SubscribePubSubRequest(SubscribePubSubRequest.Data(SubscribePubSubRequest.Data.PubSub(str(topic))))
