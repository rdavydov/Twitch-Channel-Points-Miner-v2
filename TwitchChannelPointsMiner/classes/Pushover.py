from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.EventHook import LogAttributeValidatingEventHook
from TwitchChannelPointsMiner.classes.Settings import Events


class Pushover(LogAttributeValidatingEventHook):
    __slots__ = ["userkey", "token", "priority", "sound", "events"]

    def __init__(self, userkey: str, token: str, priority, sound, events: list):
        super().__init__("skip_pushover")
        self.userkey = userkey
        self.token = token
        self.priority = priority
        self.sound = sound
        self.events = [str(e) for e in events]

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            requests.post(
                url="https://api.pushover.net/1/messages.json",
                data={
                    "user": self.userkey,
                    "token": self.token,
                    "message": dedent(message),
                    "title": "Twitch Channel Points Miner",
                    "priority": self.priority,
                    "sound": self.sound,
                },
            )

    def validate_record(self, record):
        return super().validate_record(
            record
        ) and self.userkey != "YOUR-ACCOUNT-TOKEN" and self.token != "YOUR-APPLICATION-TOKEN"
