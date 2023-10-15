from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.Settings import Events


class Telegram(object):
    __slots__ = ["chat_id", "telegram_api", "events", "disable_notification", "message_prefix"]

    def __init__(
        self, chat_id: int, token: str, message_prefix: str, events: list, disable_notification: bool = False
    ):
        self.chat_id = chat_id
        self.telegram_api = f"https://api.telegram.org/bot{token}/sendMessage"
        self.events = [str(e) for e in events]
        self.disable_notification = disable_notification
        if not message_prefix or message_prefix == False:
            self.message_prefix = ""
        else:
            self.message_prefix = message_prefix
            
    def send(self, message: str, event: Events) -> None:
        message = self.message_prefix + message
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
