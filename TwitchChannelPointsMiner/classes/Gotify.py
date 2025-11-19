from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.Settings import Events

class Gotify(object):
    __slots__ = ["endpoint", "priority", "events"]

    def __init__(self, endpoint: str, priority: int, events: list):
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
