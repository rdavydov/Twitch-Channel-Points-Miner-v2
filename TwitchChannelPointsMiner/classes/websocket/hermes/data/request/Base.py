import abc
from datetime import datetime, UTC

from TwitchChannelPointsMiner.utils import create_random_id, simple_repr


class RequestBase(abc.ABC):
    def __init__(self, _type: str, _id: str | None = None, timestamp: datetime | None = None):
        self.id: str = _id or str(create_random_id(21))
        self.timestamp: datetime = timestamp or datetime.now(UTC)
        self.type: str = _type

    def __repr__(self):
        return simple_repr(self)
