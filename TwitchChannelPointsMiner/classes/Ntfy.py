from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.Settings import Events


class Ntfy(object):
    __slots__ = ["endpoint", "events", "headers"]

    def __init__(
        self, endpoint: str, events: list, token: str or None = None, priority: int = 3
    ):
        self.endpoint = endpoint
        self.events = [str(e) for e in events]

        self.headers = {
            "Priority": str(priority)
        }

        if token is not None:
            self.headers["Authorization"] = f"Bearer {token}"

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            requests.post(
                url=self.endpoint,
                data=dedent(message),
                headers=self.headers,
            )

