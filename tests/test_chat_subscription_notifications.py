import unittest
from unittest.mock import patch

from irc.client import Event

from TwitchChannelPointsMiner.classes.Chat import ClientIRC
from TwitchChannelPointsMiner.classes.Settings import Events
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer


class ChatSubscriptionNotificationsTest(unittest.TestCase):
    def _make_client(self, name="streamer", points=184880, nickname="myuser"):
        client = ClientIRC.__new__(ClientIRC)
        client.streamer = Streamer(name)
        client.streamer.channel_points = points
        client.channel_name = name
        client.channel = f"#{name}"
        client._nickname = nickname
        return client

    def _make_event(self, msg_id, tags):
        payload = [{"key": "msg-id", "value": msg_id}]
        payload.extend({"key": key, "value": value} for key, value in tags.items())
        return Event("usernotice", "tmi.twitch.tv", "#streamer", ["ignored"], payload)

    def test_builds_pretty_subgift_message(self):
        client = self._make_client(nickname="LuckyViewer")
        event = self._make_event(
            "subgift",
            {
                "display-name": "GiftGiver",
                "msg-param-recipient-user-name": "luckyviewer",
                "msg-param-recipient-display-name": "LuckyViewer",
                "msg-param-sub-plan": "1000",
            },
        )

        message = client._build_subscription_message(event)

        self.assertEqual(
            message,
            "\n".join(
                [
                    "**Received Subgift**",
                    "",
                    "**Channel:** `streamer` (`184.88k points`)",
                    "**Recipient:** **LuckyViewer**",
                    "**From:** **GiftGiver**",
                    "**Tier:** `Tier 1`",
                ]
            ),
        )

    def test_builds_pretty_resub_message_with_months(self):
        client = self._make_client(
            name="resubchannel",
            points=1200,
            nickname="ReturningViewer",
        )
        event = self._make_event(
            "resub",
            {
                "display-name": "ReturningViewer",
                "login": "returningviewer",
                "msg-param-sub-plan": "Prime",
                "msg-param-cumulative-months": "7",
            },
        )

        message = client._build_subscription_message(event)

        self.assertEqual(
            message,
            "\n".join(
                [
                    "**Subscription Renewed**",
                    "",
                    "**Channel:** `resubchannel` (`1.2k points`)",
                    "**Subscriber:** **ReturningViewer**",
                    "**Tier:** `Prime`",
                    "**Months:** `7`",
                ]
            ),
        )

    def test_emits_subscription_event_with_package_emoji(self):
        client = self._make_client(nickname="FreshSub")
        event = self._make_event(
            "sub",
            {
                "display-name": "FreshSub",
                "login": "freshsub",
                "msg-param-sub-plan": "1000",
            },
        )

        with patch("TwitchChannelPointsMiner.classes.Chat.logger.info") as info_log:
            client.on_usernotice(None, event)

        info_log.assert_called_once()
        args, kwargs = info_log.call_args
        self.assertIn("**New Subscription**", args[0])
        self.assertEqual(kwargs["extra"]["emoji"], ":partying_face:")
        self.assertEqual(kwargs["extra"]["event"], Events.SUBSCRIPTION)

    def test_ignores_subscription_events_for_other_users(self):
        client = self._make_client(nickname="myuser")
        event = self._make_event(
            "subgift",
            {
                "display-name": "GiftGiver",
                "msg-param-recipient-user-name": "someoneelse",
                "msg-param-recipient-display-name": "SomeoneElse",
            },
        )

        self.assertIsNone(client._build_subscription_message(event))

        with patch("TwitchChannelPointsMiner.classes.Chat.logger.info") as info_log:
            client.on_usernotice(None, event)

        info_log.assert_not_called()

    def test_ignores_resub_events_for_other_users(self):
        client = self._make_client(nickname="myuser")
        event = self._make_event(
            "resub",
            {
                "display-name": "isacshyne",
                "login": "isacshyne",
                "msg-param-sub-plan": "1000",
                "msg-param-cumulative-months": "19",
            },
        )

        self.assertIsNone(client._build_subscription_message(event))

        with patch("TwitchChannelPointsMiner.classes.Chat.logger.info") as info_log:
            client.on_usernotice(None, event)

        info_log.assert_not_called()
