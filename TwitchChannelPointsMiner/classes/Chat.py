import logging
import time
from enum import Enum, auto
from threading import Thread

from irc.bot import SingleServerIRCBot

from TwitchChannelPointsMiner.constants import IRC, IRC_PORT
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.utils import _millify

logger = logging.getLogger(__name__)


class ChatPresence(Enum):
    ALWAYS = auto()
    NEVER = auto()
    ONLINE = auto()
    OFFLINE = auto()

    def __str__(self):
        return self.name


class ClientIRC(SingleServerIRCBot):
    def __init__(self, username, token, streamer):
        self.token = token
        self.streamer = streamer
        self.channel_name = self._get_channel_name(streamer)
        self.channel = "#" + self.channel_name
        self.__active = False

        super(ClientIRC, self).__init__(
            [(IRC, IRC_PORT, f"oauth:{token}")], username, username
        )

    @staticmethod
    def _get_channel_name(streamer):
        if hasattr(streamer, "username"):
            return streamer.username
        return str(streamer).lstrip("#")

    def on_welcome(self, client, event):
        try:
            client.cap("REQ", "twitch.tv/tags", "twitch.tv/commands")
        except Exception:
            logger.debug("Failed to request Twitch IRC capabilities", exc_info=True)
        client.join(self.channel)

    @staticmethod
    def _tags_to_dict(tags):
        return {tag["key"]: tag.get("value") for tag in (tags or [])}

    @staticmethod
    def _normalize_user(value):
        return str(value).strip().lstrip("@").lower() if value else None

    @staticmethod
    def _format_sub_plan(plan_code):
        plans = {
            "Prime": "Prime",
            "1000": "Tier 1",
            "2000": "Tier 2",
            "3000": "Tier 3",
        }
        if not plan_code:
            return "Unknown"
        return plans.get(str(plan_code), str(plan_code))

    def _format_streamer_label(self):
        if hasattr(self.streamer, "username"):
            return self.streamer.username
        return self.channel_name

    def _format_points_label(self):
        if hasattr(self.streamer, "channel_points"):
            return f"{_millify(self.streamer.channel_points)} points"
        return "Unknown"

    @staticmethod
    def _build_detail_message(title, details):
        lines = [
            f"**{title}**",
            "",
            *details,
        ]
        return "\n".join(lines)

    def _targets_current_user(self, msg_id, tags):
        current_user = self._normalize_user(getattr(self, "_nickname", None))
        if current_user is None:
            return False

        if msg_id in [
            "sub",
            "resub",
            "giftpaidupgrade",
            "anongiftpaidupgrade",
            "primepaidupgrade",
        ]:
            candidates = [
                tags.get("login"),
                tags.get("user-login"),
                tags.get("display-name"),
            ]
        elif msg_id in ["subgift", "anonsubgift"]:
            candidates = [
                tags.get("msg-param-recipient-user-name"),
                tags.get("msg-param-recipient-display-name"),
            ]
        else:
            return False

        return any(
            self._normalize_user(candidate) == current_user
            for candidate in candidates
            if candidate
        )

    def _build_subscription_message(self, event):
        tags = self._tags_to_dict(event.tags)
        msg_id = tags.get("msg-id")
        if msg_id is None:
            return None
        if self._targets_current_user(msg_id, tags) is False:
            return None

        subscriber = (
            tags.get("display-name")
            or tags.get("login")
            or tags.get("user-login")
            or "Unknown"
        )
        recipient = (
            tags.get("msg-param-recipient-display-name")
            or tags.get("msg-param-recipient-user-name")
            or "Unknown"
        )
        gifter = (
            tags.get("msg-param-sender-name")
            or tags.get("msg-param-sender-login")
            or subscriber
        )
        if msg_id == "anonsubgift":
            gifter = "Anonymous"

        channel = self._format_streamer_label()
        points = self._format_points_label()
        months = tags.get("msg-param-cumulative-months")
        plan = self._format_sub_plan(tags.get("msg-param-sub-plan"))

        if msg_id == "sub":
            return self._build_detail_message(
                "New Subscription",
                [
                    f"**Channel:** `{channel}` (`{points}`)",
                    f"**Subscriber:** **{subscriber}**",
                    f"**Tier:** `{plan}`",
                ],
            )
        elif msg_id == "resub":
            details = [
                f"**Channel:** `{channel}` (`{points}`)",
                f"**Subscriber:** **{subscriber}**",
                f"**Tier:** `{plan}`",
            ]
            if months:
                details.append(f"**Months:** `{months}`")
            return self._build_detail_message(
                "Subscription Renewed",
                details,
            )
        elif msg_id in ["subgift", "anonsubgift"]:
            return self._build_detail_message(
                "Received Subgift",
                [
                    f"**Channel:** `{channel}` (`{points}`)",
                    f"**Recipient:** **{recipient}**",
                    f"**From:** **{gifter}**",
                    f"**Tier:** `{plan}`",
                ],
            )
        elif msg_id in ["giftpaidupgrade", "anongiftpaidupgrade"]:
            return self._build_detail_message(
                "Gift Subscription Upgraded",
                [
                    f"**Channel:** `{channel}` (`{points}`)",
                    f"**Subscriber:** **{subscriber}**",
                ],
            )
        elif msg_id == "primepaidupgrade":
            return self._build_detail_message(
                "Prime Subscription Upgraded",
                [
                    f"**Channel:** `{channel}` (`{points}`)",
                    f"**Subscriber:** **{subscriber}**",
                ],
            )
        else:
            return None

    def start(self):
        self.__active = True
        self._connect()
        while self.__active:
            try:
                self.reactor.process_once(timeout=0.2)
                time.sleep(0.01)
            except Exception as e:
                logger.error(
                    f"Exception raised: {e}. Thread is active: {self.__active}"
                )
                # Stop the loop on socket/select errors to avoid tight log spam
                self.__active = False
                try:
                    self.connection.disconnect("Disconnecting after error")
                except Exception:
                    pass

    def die(self, msg="Bye, cruel world!"):
        self.connection.disconnect(msg)
        self.__active = False

    """
    def on_join(self, connection, event):
        logger.info(f"Event: {event}", extra={"emoji": ":speech_balloon:"})
    """

    # """
    def on_pubmsg(self, connection, event):
        msg = event.arguments[0]
        mention = None

        if Settings.disable_at_in_nickname is True:
            mention = f"{self._nickname.lower()}"
        else:
            mention = f"@{self._nickname.lower()}"

        # also self._realname
        # if msg.startswith(f"@{self._nickname}"):
        if mention != None and mention in msg.lower():
            # nickname!username@nickname.tmi.twitch.tv
            nick = event.source.split("!", 1)[0]
            # chan = event.target

            logger.info(f"{nick} at {self.channel} wrote: {msg}", extra={
                        "emoji": ":speech_balloon:", "event": Events.CHAT_MENTION})
    # """

    def on_usernotice(self, connection, event):
        message = self._build_subscription_message(event)
        if message is not None:
            logger.info(
                message,
                extra={"emoji": ":partying_face:", "event": Events.SUBSCRIPTION},
            )


class ThreadChat(Thread):
    def __deepcopy__(self, memo):
        return None

    def __init__(self, username, token, streamer):
        super(ThreadChat, self).__init__()

        self.username = username
        self.token = token
        self.streamer = streamer
        self.channel = ClientIRC._get_channel_name(streamer)

        self.chat_irc = None

    def run(self):
        self.chat_irc = ClientIRC(self.username, self.token, self.streamer)
        logger.info(
            f"Join IRC Chat: {self.channel}", extra={"emoji": ":speech_balloon:"}
        )
        self.chat_irc.start()

    def stop(self):
        if self.chat_irc is not None:
            logger.info(
                f"Leave IRC Chat: {self.channel}", extra={"emoji": ":speech_balloon:"}
            )
            self.chat_irc.die()
