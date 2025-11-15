import requests

from TwitchChannelPointsMiner.classes.EventHook import LogAttributeValidatingEventHook
from TwitchChannelPointsMiner.classes.Settings import Events


class Webhook(LogAttributeValidatingEventHook):
    __slots__ = ["endpoint", "method", "events"]

    def __init__(self, endpoint: str, method: str, events: list):
        super().__init__("skip_webhook")
        self.endpoint = endpoint
        self.method = method
        self.events = [str(e) for e in events]

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            url = self.endpoint + f"?event_name={str(event)}&message={message}"

            if self.method.lower() == "get":
                requests.get(url=url)
            elif self.method.lower() == "post":
                requests.post(url=url)
            else:
                raise ValueError("Invalid method, use POST or GET")

    def validate_record(self, record):
        return super().validate_record(record) and self.endpoint != "https://example.com/webhook"
