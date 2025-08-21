from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.EventHook import LogAttributeValidatingEventHook
from TwitchChannelPointsMiner.classes.Settings import Events


class Telegram(LogAttributeValidatingEventHook):
    __slots__ = ["chat_id", "telegram_api", "events", "disable_notification"]

    def __init__(
        self, chat_id: int, token: str, events: list, disable_notification: bool = False
    ):
        super().__init__("skip_telegram")
        self.chat_id = chat_id
        self.telegram_api = f"https://api.telegram.org/bot{token}/sendMessage"
        self.events = [str(e) for e in events]
        self.disable_notification = disable_notification

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            requests.post(
                url=self.telegram_api,
                data={
                    "chat_id": self.chat_id,
                    "text": dedent(message),
                    "disable_web_page_preview": True,  # include link to twitch streamer?
                    "disable_notification": self.disable_notification,  # no sound, notif just in tray
                },
            )

    def validate_record(self, record):
        return super().validate_record(record) and self.chat_id != 123456789
