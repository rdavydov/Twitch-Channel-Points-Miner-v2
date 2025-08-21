from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.EventHook import LogAttributeValidatingEventHook
from TwitchChannelPointsMiner.classes.Settings import Events


class Discord(LogAttributeValidatingEventHook):
    __invalid_urls = {
        "https://discord.com/api/webhooks/0123456789/0a1B2c3D4e5F6g7H8i9J",
        "https://discord.com/api/webhooks/9876543210/78ad737ba0e951cdfbde"
    }

    __slots__ = ["webhook_api", "events"]

    def __init__(self, webhook_api: str, events: list):
        super().__init__("skip_discord")
        self.webhook_api = webhook_api
        self.events = [str(e) for e in events]

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            requests.post(
                url=self.webhook_api,
                data={
                    "content": dedent(message),
                    "username": "Twitch Channel Points Miner",
                    "avatar_url": "https://i.imgur.com/X9fEkhT.png",
                },
            )

    def validate_record(self, record):
        return super().validate_record(record) and self.webhook_api not in Discord.__invalid_urls
