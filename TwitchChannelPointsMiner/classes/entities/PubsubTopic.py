class PubsubTopic(object):
    __slots__ = ["topic", "user_id", "streamer"]

    def __init__(self, topic, user_id=None, streamer=None):
        self.topic = topic
        self.user_id = user_id
        self.streamer = streamer

    def is_user_topic(self):
        return self.streamer is None

    def __str__(self):
        if self.is_user_topic():
            if self.user_id is None:
                raise ValueError(f"Missing user_id for topic {self.topic}")
            return f"{self.topic}.{self.user_id}"
        else:
            if self.streamer is None or getattr(self.streamer, "channel_id", None) is None:
                raise ValueError(f"Missing streamer channel_id for topic {self.topic}")
            return f"{self.topic}.{self.streamer.channel_id}"
