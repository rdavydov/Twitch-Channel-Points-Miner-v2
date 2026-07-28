import abc
from datetime import datetime

from TwitchChannelPointsMiner.utils import simple_repr


class ResponseBase(abc.ABC):
    def __init__(self, _id: str, _type: str, timestamp: datetime):
        self.id = _id
        self.type = _type
        self.timestamp = timestamp

    def __repr__(self):
        return simple_repr(self)


class Subscription:
    def __init__(self, _id: str):
        self.id = _id

    def __repr__(self):
        return simple_repr(self)
