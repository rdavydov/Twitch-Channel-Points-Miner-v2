from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.EventHook import LogAttributeValidatingEventHook
from TwitchChannelPointsMiner.classes.Settings import Events


class Gotify(LogAttributeValidatingEventHook):
    __slots__ = ["endpoint", "priority", "events"]

    def __init__(self, endpoint: str, priority: int, events: list):
        super().__init__("skip_gotify")
        self.endpoint = endpoint
        self.priority = priority
        self.events = [str(e) for e in events]

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            requests.post(
                url=self.endpoint,
                data={
                    "message": dedent(message),
                    "priority": self.priority
                },
            )

    def validate_record(self, record):
        return super().validate_record(record) and self.endpoint != "https://example.com/message?token=TOKEN"
