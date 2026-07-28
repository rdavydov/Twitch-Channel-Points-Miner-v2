import json

from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.utils import server_time


class Message(object):
    __slots__ = [
        "topic",
        "topic_user",
        "message",
        "type",
        "data",
        "timestamp",
        "channel_id",
        "identifier",
    ]

    def __init__(self, data):
        self.topic, self.topic_user = data["topic"].split(".")

        self.message = json.loads(data["message"])
        self.type = self.message["type"]

        self.data = self.message["data"] if "data" in self.message else None

        self.timestamp = self.__get_timestamp()
        self.channel_id = self.__get_channel_id()

        self.identifier = f"{self.type}.{self.topic}.{self.channel_id}"

    def __repr__(self):
        return f"{self.message}"

    def __str__(self):
        return f"{self.message}"

    def __get_timestamp(self):
        return (
            server_time(self.message)
            if self.data is None
            else (
                self.data["timestamp"]
                if "timestamp" in self.data
                else server_time(self.data)
            )
        )

    def __get_channel_id(self):
        return (
            self.topic_user
            if self.data is None
            else (
                self.data["prediction"]["channel_id"]
                if "prediction" in self.data
                else (
                    self.data["claim"]["channel_id"]
                    if "claim" in self.data
                    else (
                        self.data["channel_id"]
                        if "channel_id" in self.data
                        else (
                            self.data["balance"]["channel_id"]
                            if "balance" in self.data
                            else self.topic_user
                        )
                    )
                )
            )
        )

    def get_topic(self):
        return PubsubTopic(self.topic, self.topic_user, self.channel_id)
