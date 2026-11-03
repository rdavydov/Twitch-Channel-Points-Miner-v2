import logging
from textwrap import dedent

from TwitchChannelPointsMiner.classes.Settings import Events

logger = logging.getLogger(__name__)


class Apprise(object):
    """
    Sends events through Apprise (https://github.com/caronc/apprise), which supports 100+ services
    with one URL each: Discord, Telegram, Matrix, Pushover, Gotify, ntfy, Slack, email, webhooks, ...

        apprise=Apprise(
            urls=["discord://webhook_id/webhook_token", "tgram://bot_token/chat_id"],
            events=[Events.DROP_CLAIM, Events.DROP_STATUS],
        )

    URL formats: https://github.com/caronc/apprise/wiki
    """

    __slots__ = ["urls", "events", "title", "_client"]

    def __init__(self, urls, events: list, title: str = "Twitch Channel Points Miner"):
        self.urls = [urls] if isinstance(urls, str) else [u for u in (urls or []) if u]
        self.events = [str(e) for e in events]
        self.title = title
        self._client = None
        if not self.urls:
            return
        try:
            import apprise
        except ImportError:
            logger.error(
                "Apprise notifications are configured but the 'apprise' package is missing: pip install apprise"
            )
            return
        self._client = apprise.Apprise()
        for url in self.urls:
            if not self._client.add(url):
                logger.error(
                    f"Apprise: invalid notification URL ignored: {url.split('://')[0]}://..."
                )

    def send(self, message: str, event: Events) -> None:
        if self._client is None or str(event) not in self.events:
            return
        try:
            self._client.notify(title=self.title, body=dedent(message))
        except Exception as e:  # a failed notification must never stop the miner
            logger.debug(f"Apprise notify failed: {e}")
