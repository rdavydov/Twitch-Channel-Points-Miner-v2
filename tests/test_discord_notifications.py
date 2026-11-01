import json
import logging
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.PubSub import PubSubHandler
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Bet import BetSettings, Strategy
from TwitchChannelPointsMiner.classes.entities.EventPrediction import EventPrediction
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.logger import GlobalFormatter, LoggerSettings

WEBHOOK = "https://discord.example.invalid/webhook/TEST_SECRET"
EVENTS = [Events.DROP_CLAIM, Events.SUBSCRIPTION, Events.BET_WIN,
          Events.BET_LOSE, Events.BET_REFUND, Events.BET_FAILED, Events.BET_PLACED]


def units(text):
    return len(text.encode("utf-16-le")) // 2


def fields(payload):
    return {field["name"]: field["value"] for field in payload["embeds"][0].get("fields", [])}


class DiscordPayloadTest(unittest.TestCase):
    def setUp(self):
        self.discord = Discord(WEBHOOK, EVENTS)

    def test_all_event_styles_have_emoji_color_and_timestamp(self):
        cases = [
            (Events.DROP_CLAIM, "🎁 Drop claimed", 0x5865F2),
            (Events.SUBSCRIPTION, "🎉 Subscription", 0x9146FF),
            (Events.BET_WIN, "✅ Prediction won", 0x57F287),
            (Events.BET_LOSE, "❌ Prediction lost", 0xED4245),
            (Events.BET_REFUND, "↩️ Prediction refunded", 0xFEE75C),
            (Events.BET_FAILED, "⚠️ Prediction failed", 0xE67E22),
            (Events.BET_PLACED, "🎯 Prediction placed", 0x3498DB),
        ]
        for event, title, color in cases:
            with self.subTest(event=event):
                payload = self.discord.build_payload("Original message", event)
                embed = payload["embeds"][0]
                self.assertEqual((embed["title"], embed["color"]), (title, color))
                self.assertIn("Original message", embed["description"])
                self.assertIsNotNone(datetime.fromisoformat(embed["timestamp"]).tzinfo)
                self.assertEqual(payload["allowed_mentions"], {"parse": []})
                self.assertNotIn("image", embed)
                self.assertNotIn("thumbnail", embed)

    def test_detailed_prediction_uses_metadata_instead_of_parsing_text(self):
        payload = self.discord.build_payload("Unrelated log text", Events.BET_WIN, details={
            "channel": "2okos", "prediction": "Will blue win?", "outcome": "Blue",
            "stake": 5000, "payout": 8750, "net_points": 3750,
        })
        actual = fields(payload)
        self.assertEqual(actual["Channel"], "[2okos](https://www.twitch.tv/2okos)")
        self.assertEqual(actual["Prediction"], "Will blue win?")
        self.assertEqual(actual["Outcome"], "Blue")
        self.assertEqual(actual["Stake"], "5,000 points")
        self.assertEqual(actual["Payout"], "8,750 points")
        self.assertEqual(actual["Net result"], "**+3,750 points**")
        self.assertNotIn("Unrelated log text", json.dumps(payload))

    def test_drop_fields_and_inventory_link(self):
        payload = self.discord.build_payload("Claimed", Events.DROP_CLAIM, details={
            "drop_name": "Launch reward", "reward": "Golden crown", "minutes_required": 120,
        })
        self.assertEqual(fields(payload), {
            "Drop": "Launch reward", "Reward": "Golden crown", "Watch time": "120 minutes",
        })
        self.assertIn("https://www.twitch.tv/drops/inventory", payload["embeds"][0]["description"])
        self.assertNotIn("Channel", fields(payload))

    def test_placed_prediction_has_choice_and_stake_without_result(self):
        payload = self.discord.build_payload("Confirmed", Events.BET_PLACED, details={
            "channel": "2okos", "prediction": "Blue wins?", "outcome": "Blue", "stake": 5000,
        })
        self.assertEqual(fields(payload), {
            "Channel": "[2okos](https://www.twitch.tv/2okos)", "Prediction": "Blue wins?",
            "Outcome": "Blue", "Stake": "5,000 points",
        })

    def test_subscription_only_shows_known_fields(self):
        payload = self.discord.build_payload("Subgift", Events.SUBSCRIPTION, details={
            "msg_id": "subgift", "channel": "2okos", "recipient": "armi1014",
            "gifter": "Anonymous", "plan": "Tier 1", "months": None,
        })
        self.assertEqual(payload["embeds"][0]["title"], "🎉 Gift subscription received")
        self.assertEqual(fields(payload)["Gifted by"], "Anonymous")
        self.assertEqual(fields(payload)["Recipient"], "armi1014")
        self.assertNotIn("Months", fields(payload))
        self.assertNotIn("Subscriber", fields(payload))

    def test_invalid_points_and_unknown_metadata_are_omitted(self):
        payload = self.discord.build_payload("Failure", Events.BET_FAILED, details={
            "channel": "Unknown", "stake": None, "payout": True,
            "net_points": "not a number", "error": "Prediction closed",
        })
        self.assertEqual(fields(payload), {"Reason": "Prediction closed"})

    def test_markdown_is_escaped_and_mentions_are_disabled(self):
        payload = self.discord.build_payload("Result", Events.BET_WIN, details={
            "channel": "2okos", "prediction": "@everyone **win** [click](https://example.invalid)",
            "outcome": "`blue` | 🦊",
        })
        self.assertIn(r"\*\*win\*\*", fields(payload)["Prediction"])
        self.assertIn(r"\[click\]", fields(payload)["Prediction"])
        self.assertIn("🦊", fields(payload)["Outcome"])
        self.assertEqual(payload["allowed_mentions"], {"parse": []})

    def test_long_unicode_payloads_obey_individual_and_total_limits(self):
        huge = "🦊**\\" * 5000
        payloads = [
            self.discord.build_payload(huge, Events.BET_FAILED),
            self.discord.build_payload(huge, Events.SUBSCRIPTION, details={
                key: huge for key in ("channel", "plan", "subscriber", "recipient", "months")
            }),
        ]
        for payload in payloads:
            with self.subTest(payload_type=bool(fields(payload))):
                embed = payload["embeds"][0]
                self.assertLessEqual(units(embed["title"]), 256)
                self.assertLessEqual(units(embed.get("description", "")), 4096)
                self.assertLessEqual(len(embed.get("fields", [])), 25)
                total = units(embed["title"]) + units(embed["footer"]["text"])
                total += units(embed.get("description", ""))
                for field in embed.get("fields", []):
                    self.assertTrue(field["value"])
                    self.assertLessEqual(units(field["name"]), 256)
                    self.assertLessEqual(units(field["value"]), 1024)
                    total += units(field["name"]) + units(field["value"])
                self.assertLessEqual(total, 6000)
                json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def test_plain_mode_keeps_markdown_and_caps_content(self):
        discord = Discord(WEBHOOK, EVENTS, message_format="plain")
        payload = discord.build_payload("**Original**\n`message`", Events.BET_WIN)
        self.assertEqual(payload["content"], "**Original**\n`message`")
        self.assertNotIn("embeds", payload)
        self.assertLessEqual(units(discord.build_payload("🦊" * 3000, Events.BET_WIN)["content"]), 2000)
        with self.assertRaises(ValueError):
            Discord(WEBHOOK, EVENTS, message_format="invalid")

    def test_json_delivery_and_event_filter(self):
        with patch("TwitchChannelPointsMiner.classes.Discord.requests.post") as post:
            self.discord.send("Not selected", Events.GAIN_FOR_WATCH)
            self.assertEqual(post.call_count, 0)
            self.discord.send("Selected", Events.DROP_CLAIM)
            self.assertEqual(post.call_count, 1)
            self.assertIn("embeds", post.call_args.kwargs["json"])
            self.assertNotIn("data", post.call_args.kwargs)
            self.assertEqual(post.call_args.kwargs["timeout"], 20)
            post.return_value.raise_for_status.assert_called_once()

    def test_other_selected_event_has_generic_fallback(self):
        discord = Discord(WEBHOOK, [Events.STREAMER_ONLINE])
        with patch("TwitchChannelPointsMiner.classes.Discord.requests.post") as post:
            discord.send("Streamer is online", Events.STREAMER_ONLINE)
        self.assertEqual(post.call_args.kwargs["json"]["embeds"][0]["description"], "Streamer is online")


class DiscordIntegrationTest(unittest.TestCase):
    def test_formatter_keeps_emoji_with_console_emoji_disabled_and_copies_metadata(self):
        discord = Discord(WEBHOOK, EVENTS)
        formatter = GlobalFormatter(fmt="%(message)s", settings=LoggerSettings(emoji=False, discord=discord))
        details = {"channel": "2okos", "net_points": 3750}
        record = logging.makeLogRecord({
            "msg": "Result: %s", "args": ("won",), "event": Events.BET_WIN,
            "created": 1767225600, "discord_details": details,
        })
        with patch("TwitchChannelPointsMiner.classes.Discord.requests.post") as post:
            self.assertEqual(formatter.format(record), "Result: won")
        embed = post.call_args.kwargs["json"]["embeds"][0]
        self.assertEqual(embed["title"], "✅ Prediction won")
        self.assertEqual(embed["timestamp"], "2026-01-01T00:00:00+00:00")
        self.assertNotIn("timestamp", details)

    def test_network_failure_does_not_leak_url_or_stop_other_services(self):
        formatter = GlobalFormatter(fmt="%(message)s", settings=LoggerSettings(
            emoji=False, discord=Discord(WEBHOOK, EVENTS),
        ))
        record = logging.makeLogRecord({"msg": "Original", "event": Events.BET_FAILED})
        for error in (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            with self.subTest(error=error.__name__):
                with (
                    patch("TwitchChannelPointsMiner.classes.Discord.requests.post",
                          side_effect=error(WEBHOOK)),
                    patch.object(formatter, "webhook") as other_service,
                    patch("TwitchChannelPointsMiner.logger.logging.getLogger") as logger,
                ):
                    self.assertEqual(formatter.format(record), "Original")
                other_service.assert_called_once()
                self.assertNotIn("TEST_SECRET", str(logger.return_value.warning.call_args))

    def test_prediction_result_producer_preserves_stake_payout_and_net(self):
        for result_type, won, payout, net in (
            ("WIN", 8750, 8750, 3750), ("LOSE", 0, 0, -5000), ("REFUND", 0, 5000, 0),
        ):
            with self.subTest(result_type=result_type):
                bet_settings = BetSettings(strategy=Strategy.NUMBER_1, percentage=50, max_points=5000)
                bet_settings.default()
                streamer = Streamer("2okos", StreamerSettings(bet=bet_settings))
                streamer.channel_id = "123"
                event = EventPrediction(streamer, "evt", "Blue wins?", datetime.now(timezone.utc), 60, "ACTIVE", [
                    {"id": "blue", "title": "Blue", "color": "BLUE", "total_users": 1, "total_points": 10},
                    {"id": "pink", "title": "Pink", "color": "PINK", "total_users": 1, "total_points": 10},
                ])
                event.bet.calculate(10000)
                event.bet_confirmed = True
                handler = PubSubHandler(Mock(), [streamer], {"evt": event})
                message = SimpleNamespace(channel_id="123", topic="predictions-user-v1", type="prediction-result", data={
                    "prediction": {"id": "prediction-1", "event_id": "evt", "channel_id": "123",
                                   "outcome_id": "blue", "points": 5000,
                                   "result": {"type": result_type, "points_won": won}},
                })
                with (
                    patch.object(Settings, "logger", LoggerSettings(less=True)),
                    patch.object(Settings, "enable_analytics", False),
                    patch("TwitchChannelPointsMiner.classes.PredictionTracker.logger") as logger,
                ):
                    handler.on_message(message)
                logger.error.assert_not_called()
                details = logger.info.call_args.kwargs["extra"]["discord_details"]
                self.assertEqual((details["stake"], details["payout"], details["net_points"]), (5000, payout, net))
                self.assertEqual(details["outcome"], "Blue")

    def test_placed_notification_waits_for_confirmation_and_ignores_duplicates(self):
        settings = BetSettings(strategy=Strategy.NUMBER_1, percentage=50, max_points=5000)
        settings.default()
        streamer = Streamer("2okos", StreamerSettings(bet=settings))
        streamer.channel_id = "123"
        event = EventPrediction(streamer, "evt", "Blue wins?", datetime.now(timezone.utc), 60, "ACTIVE", [
            {"id": "blue", "title": "Blue", "color": "BLUE", "total_users": 1, "total_points": 10},
            {"id": "pink", "title": "Pink", "color": "PINK", "total_users": 1, "total_points": 10},
        ])
        event.bet.calculate(10000)
        handler = PubSubHandler(Mock(), [streamer], {"evt": event})
        message = SimpleNamespace(channel_id="123", topic="predictions-user-v1", type="prediction-updated",
                                  data={"prediction": {"id": "prediction-1", "event_id": "evt",
                                                       "channel_id": "123", "outcome_id": "blue", "points": 5000}})
        with (
            patch.object(Settings, "logger", LoggerSettings(less=True)),
            patch.object(Settings, "enable_analytics", False),
            patch("TwitchChannelPointsMiner.classes.PredictionTracker.logger") as logger,
        ):
            handler.on_message(message)
            logger.info.assert_not_called()
            self.assertFalse(event.bet_confirmed)
            message.type = "prediction-made"
            handler.on_message(message)
            handler.on_message(message)
        logger.error.assert_not_called()
        logger.info.assert_called_once()
        self.assertTrue(event.bet_confirmed)
        extra = logger.info.call_args.kwargs["extra"]
        self.assertEqual(extra["event"], Events.BET_PLACED)
        self.assertEqual(extra["discord_details"], {
            "channel": "2okos", "prediction": "Blue wins?", "outcome": "Blue", "stake": 5000,
            "source": "Manual / external",
        })

    def test_drop_is_not_announced_before_or_without_new_success(self):
        drop = SimpleNamespace(drop_instance_id="drop-1", name="Drop", benefit="Reward", minutes_required=60)
        cases = [
            ({"data": {"claimDropRewards": {"status": "ELIGIBLE_FOR_ALL"}}}, False, 0),
            ({"data": {"claimDropRewards": {"status": "DROP_INSTANCE_ALREADY_CLAIMED"}}}, True, 0),
            ({"data": {"claimDropRewards": {"status": "NOT_ELIGIBLE"}}}, False, 0),
            ({"data": {"claimDropRewards": None}}, False, 0),
            ({"errors": [{"message": "Drop rejected"}]}, False, 0),
        ]
        for response, success, expected in cases:
            with self.subTest(response=response):
                with tempfile.TemporaryDirectory() as cache, patch("TwitchChannelPointsMiner.classes.Twitch.logger") as logger:
                    twitch = Twitch("discord-test", "ua")
                    twitch.cookies_file = cache + "/cookies.pkl"
                    twitch._drop_claims = {}
                    def submit(_):
                        self.assertFalse(any(call.kwargs.get("extra", {}).get("event") == Events.DROP_CLAIM
                                             for call in logger.info.call_args_list))
                        return response
                    with patch.object(Twitch, "post_gql_request", side_effect=submit):
                        self.assertEqual(twitch.claim_drop(drop), success)
                    notifications = [call for call in logger.info.call_args_list
                                     if call.kwargs.get("extra", {}).get("event") == Events.DROP_CLAIM]
                    self.assertEqual(len(notifications), expected)
                    if expected:
                        self.assertEqual(notifications[0].kwargs["extra"]["discord_details"]["reward"], "Reward")


if __name__ == "__main__":
    unittest.main()
