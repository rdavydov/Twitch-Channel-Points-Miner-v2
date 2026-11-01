import copy
import json
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from flask import Flask

from TwitchChannelPointsMiner.classes.AnalyticsServer import (
    AnalyticsServer,
    filter_datas,
    json_all,
    read_json,
    streamers_available,
)
from TwitchChannelPointsMiner.classes.Chat import ChatPresence, ClientIRC, ThreadChat
from TwitchChannelPointsMiner.classes.Exceptions import (
    BadCredentialsException,
    StreamerDoesNotExistException,
)
from TwitchChannelPointsMiner.classes.Matrix import Matrix
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.TwitchLogin import TwitchLogin
from TwitchChannelPointsMiner.classes.Webhook import Webhook
from TwitchChannelPointsMiner.classes.entities.Bet import Bet, BetSettings, Strategy
from TwitchChannelPointsMiner.classes.entities.Campaign import Campaign
from TwitchChannelPointsMiner.classes.entities.Drop import Drop
from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.classes.websocket.hermes.Client import HermesClient, State
from TwitchChannelPointsMiner.classes.websocket.hermes.Pool import HermesWebSocketPool
from TwitchChannelPointsMiner.classes.websocket.hermes.data import (
    JsonDecoder,
    JsonEncoder,
)
from TwitchChannelPointsMiner.logger import GlobalFormatter, LoggerSettings
from TwitchChannelPointsMiner.utils import (
    download_file,
    dump_json,
    internet_connection_available,
    server_time,
)
from TwitchChannelPointsMiner.TwitchChannelPointsMiner import TwitchChannelPointsMiner


def response(status, payload):
    return Mock(status_code=status, json=Mock(return_value=payload))


class LoginRegressionTest(unittest.TestCase):
    def setUp(self):
        self.login = TwitchLogin("client", "device", "tester", "ua")

    def test_device_code_expires_without_another_token_request(self):
        device = response(
            200,
            {
                "user_code": "code",
                "device_code": "device",
                "expires_in": 5,
                "interval": 5,
            },
        )
        with (
            patch.object(
                TwitchLogin, "send_oauth_request", return_value=device
            ) as post,
            patch("TwitchChannelPointsMiner.classes.TwitchLogin.sleep"),
            patch(
                "TwitchChannelPointsMiner.classes.TwitchLogin.monotonic",
                side_effect=[0, 0, 0, 5],
            ),
        ):
            self.assertFalse(self.login.login_flow())
        post.assert_called_once()

    def test_pending_then_success_uses_configured_client(self):
        device = response(
            200,
            {
                "user_code": "code",
                "device_code": "device",
                "expires_in": 60,
                "interval": 5,
            },
        )
        with (
            patch.object(
                TwitchLogin,
                "send_oauth_request",
                side_effect=[
                    device,
                    response(400, {"message": "authorization_pending"}),
                    response(200, {"access_token": "test-token"}),
                ],
            ) as post,
            patch.object(TwitchLogin, "check_login", return_value=True),
            patch("TwitchChannelPointsMiner.classes.TwitchLogin.sleep"),
            patch(
                "TwitchChannelPointsMiner.classes.TwitchLogin.monotonic", return_value=0
            ),
        ):
            self.assertTrue(self.login.login_flow())
        self.assertEqual(post.call_args.args[1]["client_id"], "client")
        self.assertEqual(self.login.get_auth_token(), "test-token")

    def test_terminal_device_error_stops_polling(self):
        device = response(
            200,
            {
                "user_code": "code",
                "device_code": "device",
                "expires_in": 60,
                "interval": 5,
            },
        )
        with (
            patch.object(
                TwitchLogin,
                "send_oauth_request",
                side_effect=[device, response(400, {"message": "invalid device code"})],
            ) as post,
            patch("TwitchChannelPointsMiner.classes.TwitchLogin.sleep"),
            patch(
                "TwitchChannelPointsMiner.classes.TwitchLogin.monotonic", return_value=0
            ),
        ):
            self.assertFalse(self.login.login_flow())
        self.assertEqual(post.call_count, 2)

    def test_revoked_token_is_rejected(self):
        self.login.set_token("revoked")
        with patch.object(
            type(self.login.session), "get", return_value=response(401, {})
        ):
            self.assertFalse(self.login.check_login())

    def test_token_identity_overrides_stale_persistent_cookie(self):
        self.login.cookies = [{"name": "persistent", "value": "999"}]
        self.login.set_token("valid")
        with patch.object(
            type(self.login.session),
            "get",
            return_value=response(200, {"login": "Tester", "user_id": "123"}),
        ) as get:
            self.assertTrue(self.login.check_login())
        self.assertEqual(self.login.get_user_id(), 123)
        self.assertEqual(get.call_args.kwargs["timeout"], 20)
        self.login.set_token("replacement")
        self.assertFalse(self.login.login_check_result)

    def test_token_for_another_account_is_rejected(self):
        self.login.set_token("wrong-account")
        with patch.object(
            type(self.login.session),
            "get",
            return_value=response(200, {"login": "someoneelse", "user_id": "456"}),
        ):
            self.assertFalse(self.login.check_login())

    def test_failed_login_does_not_start_anonymous_mining(self):
        twitch = Twitch("tester", "ua")
        with (
            patch(
                "TwitchChannelPointsMiner.classes.Twitch.os.path.isfile",
                return_value=False,
            ),
            patch.object(TwitchLogin, "login_flow", return_value=False),
        ):
            with self.assertRaises(BadCredentialsException):
                twitch.login()


class HermesRegressionTest(unittest.TestCase):
    def setUp(self):
        self.topic = PubsubTopic("community-points-user-v1", user_id="123")
        self.client = HermesClient(
            0, "wss://example.invalid", Mock(), [], JsonEncoder(), JsonDecoder()
        )
        self.client.state = State.OPEN

    def test_failed_live_subscription_is_preserved(self):
        with patch.object(self.client, "send_request", return_value=False):
            self.client.subscribe(self.topic)
        self.assertEqual(self.client.pending_topics, [self.topic])
        self.assertEqual(self.client.subscriptions, {})
        self.client.pending_topics.clear()
        with patch.object(
            self.client, "send_request", side_effect=OSError("send failed")
        ):
            with self.assertRaises(OSError):
                self.client.subscribe(self.topic)
        self.assertEqual(self.client.pending_topics, [self.topic])
        self.assertEqual(self.client.subscriptions, {})

    def test_failed_pending_subscription_is_preserved_and_stops_flush(self):
        self.client.pending_topics = [self.topic]
        with patch.object(self.client, "send_request", return_value=False) as send:
            self.client.subscribe_pending()
        self.assertEqual(self.client.all_topics(), [self.topic])
        send.assert_called_once()

    def test_subscription_is_registered_before_send(self):
        def send(request):
            self.assertEqual(self.client.topic(request.subscribe.id), self.topic)
            return True

        with patch.object(self.client, "send_request", side_effect=send):
            self.client.subscribe(self.topic)

    def test_pool_closes_clients_outside_its_lock(self):
        pool = HermesWebSocketPool(
            "wss://example.invalid", Mock(), [], JsonEncoder(), JsonDecoder()
        )

        def close():
            self.assertFalse(pool._HermesWebSocketPool__lock.locked())

        self.client.close = Mock(side_effect=close)
        pool.clients = [self.client]
        pool.end()
        self.client.close.assert_called_once()

    def test_reconnect_replaces_client_before_close_callback(self):
        pool = HermesWebSocketPool(
            "wss://example.invalid", Mock(), [], JsonEncoder(), JsonDecoder()
        )
        pool.clients = [self.client]
        self.client.pending_topics = [self.topic]

        def close():
            self.assertFalse(pool._HermesWebSocketPool__lock.locked())
            pool.on_close(self.client, 1000, "closed")

        self.client.close = Mock(side_effect=close)
        with (
            patch(
                "TwitchChannelPointsMiner.classes.websocket.hermes.Pool.interruptible_sleep"
            ),
            patch(
                "TwitchChannelPointsMiner.classes.websocket.hermes.Pool.internet_connection_available",
                return_value=True,
            ),
            patch.object(HermesClient, "open") as open_client,
        ):
            pool.on_close(self.client, 1000, "closed")
        self.client.close.assert_called_once()
        open_client.assert_called_once()
        self.assertEqual(pool.clients[0].all_topics(), [self.topic])


class PredictionRegressionTest(unittest.TestCase):
    def outcomes(self):
        return [
            {
                "id": "a",
                "title": "A",
                "color": "BLUE",
                "total_users": 1,
                "total_points": 10,
                "top_predictors": [{"points": 10}],
            },
            {
                "id": "b",
                "title": "B",
                "color": "PINK",
                "total_users": 9,
                "total_points": 90,
                "top_predictors": [{"points": 90}],
            },
        ]

    def bet(self, strategy=Strategy.MOST_VOTED, **kwargs):
        settings = BetSettings(strategy=strategy, **kwargs)
        settings.default()
        return Bet(self.outcomes(), settings)

    def test_initial_snapshot_informs_decision(self):
        bet = self.bet()
        self.assertEqual(bet.calculate(1000)["id"], "b")
        self.assertEqual(bet.outcomes[1]["percentage_users"], 90)

    def test_updates_follow_outcome_ids_even_when_reordered(self):
        bet = self.bet()
        reordered = list(reversed(self.outcomes()))
        reordered[0]["total_users"] = 2
        reordered[1]["total_users"] = 8
        bet.update_outcomes(reordered)
        self.assertEqual(bet.calculate(1000)["id"], "a")

    def test_empty_top_predictors_reset_smart_money(self):
        bet = self.bet(Strategy.SMART_MONEY)
        updates = self.outcomes()
        updates[1]["top_predictors"] = []
        bet.update_outcomes(updates)
        self.assertEqual(bet.calculate(1000)["id"], "a")

    def test_zero_snapshot_clears_ratios(self):
        bet = self.bet()
        updates = self.outcomes()
        for outcome in updates:
            outcome.update(total_users=0, total_points=0)
        bet.update_outcomes(updates)
        self.assertEqual(bet.outcomes[1]["percentage_users"], 0)
        self.assertEqual(bet.outcomes[1]["odds"], 0)

    def test_bet_cannot_exceed_balance_or_be_negative(self):
        bet = self.bet(percentage=200)
        self.assertEqual(bet.calculate(100)["amount"], 100)
        self.assertEqual(bet.calculate(-100)["amount"], 0)

    def test_stealth_does_not_produce_negative_points(self):
        bet = self.bet(stealth_mode=True, percentage=100)
        bet.outcomes[1]["top_points"] = 1
        with patch(
            "TwitchChannelPointsMiner.classes.entities.Bet.uniform", return_value=5
        ):
            self.assertEqual(bet.calculate(100)["amount"], 0)
        bet.outcomes[1]["top_points"] = 0
        self.assertEqual(bet.calculate(100)["amount"], 100)

    def test_empty_outcomes_skip_without_crashing(self):
        settings = BetSettings()
        settings.default()
        bet = Bet([], settings)
        self.assertEqual(bet.calculate(100)["amount"], 0)
        self.assertTrue(bet.skip()[0])
        repr(bet)

    def test_constructor_does_not_mutate_event_payload(self):
        original = self.outcomes()
        before = copy.deepcopy(original)
        settings = BetSettings()
        settings.default()
        Bet(original, settings)
        self.assertEqual(original, before)

    def test_smart_strategy_uses_top_two_counts_for_many_outcomes(self):
        settings = BetSettings(strategy=Strategy.SMART, percentage_gap=20)
        settings.default()
        outcomes = self.outcomes()
        outcomes[0].update(total_users=40, total_points=20)
        outcomes[1].update(total_users=5, total_points=5)
        outcomes.append(dict(outcomes[1], id="c", total_users=39, total_points=100))
        bet = Bet(outcomes, settings)
        self.assertEqual(bet.calculate(1000)["id"], "b")


class PlaybackAndApiRegressionTest(unittest.TestCase):
    def setUp(self):
        self.twitch = Twitch("tester", "ua")
        self.streamer = Streamer("test", StreamerSettings(watch_streak=False))

    def test_gql_debug_logs_do_not_include_playback_credentials(self):
        payload = {"data": {"streamPlaybackAccessToken": {"value": "private-token"}}}
        result = response(200, payload)
        result.text = json.dumps(payload)
        with (
            patch.object(Twitch, "_request_with_retry", return_value=result),
            patch.object(Twitch, "update_client_version", return_value="version"),
            patch.object(TwitchLogin, "get_auth_token", return_value="private-auth"),
            self.assertLogs(
                "TwitchChannelPointsMiner.classes.Twitch", level="DEBUG"
            ) as logs,
        ):
            self.assertEqual(
                self.twitch.post_gql_request({"operationName": "PlaybackAccessToken"}),
                payload,
            )
        self.assertIn("PlaybackAccessToken", " ".join(logs.output))
        self.assertNotIn("private-token", " ".join(logs.output))
        self.assertNotIn("private-auth", " ".join(logs.output))

    def test_stream_metadata_is_read_from_user_broadcast_settings(self):
        payload = {
            "data": {
                "user": {
                    "broadcastSettings": {
                        "title": "Stream title",
                        "game": {"id": "42", "name": "Game"},
                    },
                    "stream": {
                        "id": "broadcast",
                        "tags": [],
                        "viewersCount": 100,
                        "createdAt": "2026-09-26T12:00:00Z",
                    },
                }
            }
        }
        with (
            patch.object(Twitch, "post_gql_request", return_value=payload),
            patch.object(Twitch, "get_chat_ban_status", return_value=False),
        ):
            result = self.twitch.get_stream_info(self.streamer)
        self.assertEqual(result["broadcastSettings"]["game"]["id"], "42")
        self.assertEqual(result["broadcastSettings"]["title"], "Stream title")

    def test_cached_playlist_does_not_bypass_expired_token(self):
        self.streamer.stream.hls_url = "https://old.example/playlist.m3u8"
        self.streamer.stream.playback_access_token = {
            "signature": "old",
            "value": "old",
            "expires_at": 0,
        }
        fresh = {"signature": "new", "value": "new", "expires_at": 9999999999}
        playlist = Mock(status_code=200, text="https://new.example/playlist.m3u8\n")
        with (
            patch.object(
                Twitch, "_fetch_playback_access_token", return_value=fresh
            ) as token,
            patch.object(Twitch, "_request_with_retry", return_value=playlist),
        ):
            self.assertEqual(
                self.twitch._get_hls_playlist_url(self.streamer),
                "https://new.example/playlist.m3u8",
            )
        token.assert_called_once()

    def test_relative_hls_urls_resolve_against_playlist(self):
        self.assertEqual(
            self.twitch._last_http_url_from_playlist(
                "#EXTM3U\n#EXTINF:2\n../segment.ts\n",
                "https://video.example/low/index.m3u8",
            ),
            "https://video.example/segment.ts",
        )

    def test_null_playback_response_is_treated_as_unavailable(self):
        with patch.object(Twitch, "post_gql_request", return_value={"data": None}):
            self.assertIsNone(self.twitch._fetch_playback_access_token(self.streamer))

    def test_null_inventory_dashboard_and_campaign_details_do_not_crash(self):
        for payload in ({"data": None}, {"data": {"currentUser": None}}):
            with patch.object(Twitch, "post_gql_request", return_value=payload):
                self.assertEqual(self.twitch._Twitch__get_inventory(), {})
                self.assertEqual(self.twitch._Twitch__get_drops_dashboard(), [])
        with patch.object(
            Twitch, "post_gql_request", return_value=[{"data": {"user": None}}]
        ):
            self.assertEqual(
                self.twitch._Twitch__get_campaigns_details([{"id": "campaign"}]), []
            )

    def test_null_channel_self_preserves_last_known_balance(self):
        self.streamer.channel_points = 100
        with patch.object(
            Twitch,
            "post_gql_request",
            return_value={"data": {"community": {"channel": {"self": None}}}},
        ):
            self.twitch.load_channel_points_context(self.streamer)
        self.assertEqual(self.streamer.channel_points, 100)

    def test_missing_point_context_data_preserves_cached_state_without_logging_payload(self):
        self.streamer.channel_points = 100
        self.streamer.channel_points_context_at = 123
        payloads = (
            {"data": None, "private_marker": "private-payload"},
            {"private_marker": "private-payload"},
            {"data": []},
            [{"data": None}],
        )
        for payload in payloads:
            with (
                self.subTest(payload=payload),
                patch.object(Twitch, "post_gql_request", return_value=payload),
                self.assertLogs("TwitchChannelPointsMiner.classes.Twitch") as logs,
            ):
                self.twitch.load_channel_points_context(self.streamer)
            self.assertEqual(self.streamer.channel_points, 100)
            self.assertEqual(self.streamer.channel_points_context_at, 123)
            self.assertNotIn("private-payload", " ".join(logs.output))

    def test_transient_point_context_failure_does_not_remove_streamer_at_startup(self):
        self.streamer.channel_points = 100
        with (
            patch.object(Twitch, "post_gql_request", return_value={"data": None}),
            patch.object(Twitch, "check_streamer_online") as online_check,
            patch("TwitchChannelPointsMiner.classes.Twitch.time.sleep"),
        ):
            failed = self.twitch.initialize_streamers_context([self.streamer])
        self.assertEqual(failed, set())
        online_check.assert_called_once_with(self.streamer)
        self.assertEqual(self.streamer.channel_points, 100)

    def test_explicit_missing_channel_still_raises(self):
        with patch.object(
            Twitch,
            "post_gql_request",
            return_value={"data": {"community": {"channel": None}}},
        ):
            with self.assertRaises(StreamerDoesNotExistException):
                self.twitch.load_channel_points_context(self.streamer)

    def test_prediction_timer_cannot_place_bet_after_shutdown(self):
        self.twitch.running = False
        event = Mock()
        self.twitch.make_predictions(event)
        event.bet.calculate.assert_not_called()


class MinerStartupRegressionTest(unittest.TestCase):
    def miner(self):
        miner = TwitchChannelPointsMiner.__new__(TwitchChannelPointsMiner)
        miner.twitch = Mock()
        miner.twitch.get_channel_id.return_value = "123"
        miner.twitch.initialize_streamers_context.return_value = set()
        miner.running = False
        miner.session_id = "test"
        miner.username = "tester"
        miner.claim_drops_startup = False
        miner.watch_streak_cache = None
        miner.watch_streak_min_offline_seconds = 1800
        miner.watch_streak_cache_path = "unused-cache"
        miner.subscription_notification_cache_path = "unused-subscriptions"
        miner.streamers = []
        miner.ws_pool = None
        miner.minute_watcher_thread = None
        miner.sync_campaigns_thread = None
        miner.streamers_export_thread = None
        return miner

    def test_empty_streamer_list_stops_before_starting_workers(self):
        miner = self.miner()
        with (
            patch.object(
                TwitchChannelPointsMiner,
                "_watch_streak_cache_load_path",
                return_value="unused",
            ),
            patch.object(
                import_module("TwitchChannelPointsMiner.TwitchChannelPointsMiner").WatchStreakCache, "load_from_disk",
                return_value=None,
            ),
            patch.object(TwitchChannelPointsMiner, "_export_streamers_snapshot"),
            patch.object(
                TwitchChannelPointsMiner, "_save_daily_points_baseline_if_dirty"
            ),
        ):
            miner.run([])
        self.assertFalse(miner.running)
        self.assertFalse(miner.twitch.running)
        miner.twitch.get_followers_with_dates.assert_not_called()

    def test_duplicate_and_blacklisted_names_are_normalized(self):
        miner = self.miner()
        miner.twitch.initialize_streamers_context.side_effect = RuntimeError(
            "stop after bootstrap"
        )
        settings = StreamerSettings(chat=ChatPresence.NEVER)
        settings.default()
        settings.bet.default()
        with (
            patch.object(Settings, "streamer_settings", settings, create=True),
            patch.object(
                TwitchChannelPointsMiner,
                "_watch_streak_cache_load_path",
                return_value="unused",
            ),
            patch.object(
                import_module("TwitchChannelPointsMiner.TwitchChannelPointsMiner").WatchStreakCache, "load_from_disk",
                return_value=None,
            ),
            patch.object(TwitchChannelPointsMiner, "_export_streamers_snapshot"),
            patch.object(
                TwitchChannelPointsMiner, "_save_daily_points_baseline_if_dirty"
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "stop after bootstrap"):
                miner.run(["Test", " test ", "BLOCKED"], blacklist=[" Blocked "])
        miner.twitch.get_channel_id.assert_called_once_with("test")
        self.assertEqual(len(miner.streamers), 1)

    def test_startup_exception_stops_existing_workers_and_pool(self):
        miner = self.miner()
        miner.twitch.login.side_effect = RuntimeError("startup failure")
        miner.minute_watcher_thread = Mock()
        miner.sync_campaigns_thread = Mock()
        miner.reward_automation_thread = Mock()
        miner.ws_pool = Mock()
        with (
            patch.object(TwitchChannelPointsMiner, "_export_streamers_snapshot"),
            patch.object(
                TwitchChannelPointsMiner, "_save_daily_points_baseline_if_dirty"
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "startup failure"):
                miner.run([])
        self.assertFalse(miner.twitch.running)
        miner.reward_automation_thread.stop.assert_called_once()
        miner.reward_automation_thread.join.assert_called_once()
        miner.ws_pool.end.assert_called_once()
        miner.minute_watcher_thread.join.assert_called_once()
        miner.sync_campaigns_thread.join.assert_called_once()


class DropRegressionTest(unittest.TestCase):
    def drop_data(self):
        now = datetime.now(timezone.utc)
        return {
            "id": "drop",
            "name": "Reward",
            "requiredMinutesWatched": 60,
            "benefitEdges": [{"benefit": {"name": "Submarine Skin"}}],
            "startAt": (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endAt": (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def test_drop_and_campaign_use_utc_boundaries(self):
        data = self.drop_data()
        with patch(
            "TwitchChannelPointsMiner.classes.entities.Drop.datetime", wraps=datetime
        ) as clock:
            drop = Drop(data)
        clock.now.assert_called_once_with(timezone.utc)
        self.assertTrue(drop.dt_match)
        campaign = Campaign(
            dict(
                data,
                game={},
                status="ACTIVE",
                allow={"channels": None},
                timeBasedDrops=[data],
            )
        )
        self.assertTrue(campaign.dt_match)

    def test_cosmetic_name_does_not_make_drop_subscriber_only(self):
        self.assertFalse(Drop(self.drop_data()).requires_subscription)

    def test_inventory_campaigns_survive_empty_dashboard_without_duplicates(self):
        drop = self.drop_data()
        campaign = dict(
            drop,
            id="campaign",
            game={"id": "game"},
            status="ACTIVE",
            allow={"channels": None},
            timeBasedDrops=[drop],
        )
        for details in ([], [campaign]):
            with self.subTest(dashboard_details=bool(details)):
                twitch = Twitch("tester", "ua")
                streamer = Streamer("test", StreamerSettings(claim_drops=True))
                streamer.is_online = True
                streamer.stream.game = {"id": "game"}
                with (
                    patch.object(Twitch, "claim_all_drops_from_inventory"),
                    patch.object(
                        Twitch, "_Twitch__get_drops_dashboard", return_value=[]
                    ),
                    patch.object(
                        Twitch,
                        "_Twitch__get_campaigns_details",
                        return_value=list(details),
                    ),
                    patch.object(
                        Twitch,
                        "_Twitch__get_inventory",
                        return_value={"dropCampaignsInProgress": [campaign]},
                    ),
                    patch.object(
                        Twitch,
                        "_Twitch__sync_campaigns",
                        side_effect=lambda campaigns: campaigns,
                    ),
                    patch.object(
                        Twitch,
                        "_Twitch__chuncked_sleep",
                        side_effect=lambda *args, **kwargs: setattr(
                            twitch, "running", False
                        ),
                    ),
                ):
                    twitch.sync_campaigns([streamer])
                self.assertEqual(
                    [c.id for c in streamer.stream.campaigns], ["campaign"]
                )

    def test_claim_requires_progress_and_preconditions(self):
        drop = Drop(self.drop_data())
        for progress in (
            {"currentMinutesWatched": 1, "dropInstanceID": "instance"},
            {
                "currentMinutesWatched": 60,
                "dropInstanceID": "instance",
                "hasPreconditionsMet": False,
            },
        ):
            drop.update(progress)
            self.assertFalse(drop.is_claimable)
        drop.update(
            {
                "currentMinutesWatched": 60,
                "dropInstanceID": "instance",
                "hasPreconditionsMet": True,
            }
        )
        self.assertTrue(drop.is_claimable)

    def test_paid_subscription_drop_is_not_farmable_by_watching(self):
        drop = Drop(dict(self.drop_data(), requiredSubs=1))
        drop.update({"currentMinutesWatched": 60, "dropInstanceID": "instance"})
        self.assertFalse(drop.is_claimable)
        streamer = Streamer("test")
        streamer.subscription_tier = "1000"
        streamer.stream.campaigns = [SimpleNamespace(drops=[drop])]
        self.assertFalse(streamer.has_farmable_drops())
        drop.update(
            {
                "currentMinutesWatched": 60,
                "dropInstanceID": "instance",
                "hasPreconditionsMet": True,
            }
        )
        self.assertTrue(
            drop.is_claimable
        )  # An already earned paid reward can still be claimed.


class AnalyticsRegressionTest(unittest.TestCase):
    def test_empty_missing_and_annotations_only_data(self):
        for data in (
            {},
            {"series": [], "annotations": []},
            {"annotations": [{"x": 1}]},
        ):
            with self.subTest(data=data):
                result = filter_datas(None, None, data)
                self.assertEqual(result["series"], [])

    def test_range_before_first_sample_is_empty(self):
        sample = int(datetime(2026, 9, 2, tzinfo=timezone.utc).timestamp() * 1000)
        result = filter_datas(
            "2026-09-01", "2026-09-01", {"series": [{"x": sample, "y": 100}]}
        )
        self.assertEqual(result["series"], [])

    def test_range_after_last_sample_uses_known_balance(self):
        sample = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
        result = filter_datas(
            "2026-09-02", "2026-09-02", {"series": [{"x": sample, "y": 100}]}
        )
        self.assertEqual([point["y"] for point in result["series"]], [100, 100])

    def test_missing_analytics_directory_is_empty(self):
        with patch.object(
            Settings, "analytics_path", "nonexistent-test-directory", create=True
        ):
            self.assertEqual(streamers_available(), [])

    def test_json_all_preserves_names_and_invalid_date_returns_400(self):
        app = Flask(__name__)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "jon.json").write_text('{"series": []}', encoding="utf-8")
            with patch.object(Settings, "analytics_path", directory, create=True):
                with app.test_request_context("/"):
                    self.assertEqual(
                        json.loads(json_all().get_data())[0]["name"], "jon"
                    )
                with app.test_request_context("/?startDate=invalid"):
                    self.assertEqual(read_json("jon").status_code, 400)

    def test_log_cursor_is_per_client_and_recovers_after_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory, "tester.log")
            logfile.write_text("a🙂b", encoding="utf-8")
            with patch("TwitchChannelPointsMiner.classes.AnalyticsServer.check_assets"):
                server = AnalyticsServer(username="tester", log_file_path=str(logfile))
            client = server.app.test_client()
            first = client.get("/log")
            self.assertEqual(first.headers["X-Log-Index"], "3")
            self.assertEqual(client.get("/log").get_data(as_text=True), "a🙂b")
            self.assertEqual(client.get("/log?lastIndex=3").get_data(as_text=True), "")
            logfile.write_text("new", encoding="utf-8")
            self.assertEqual(
                client.get("/log?lastIndex=100").get_data(as_text=True), "new"
            )
            self.assertEqual(client.get("/log?lastIndex=invalid").status_code, 200)


class NotificationRegressionTest(unittest.TestCase):
    def test_matrix_login_failure_keeps_optional_notifications_disabled(self):
        with patch(
            "TwitchChannelPointsMiner.classes.Matrix.requests.post",
            side_effect=requests.exceptions.ConnectionError("secret-url"),
        ):
            matrix = Matrix(
                "user",
                "password",
                "matrix.example.invalid",
                "!room:server",
                [Events.SUBSCRIPTION],
            )
        self.assertIsNone(matrix.access_token)
        with patch("TwitchChannelPointsMiner.classes.Matrix.requests.put") as put:
            matrix.send("test", Events.SUBSCRIPTION)
        put.assert_not_called()

    def test_webhook_uses_encoded_params_and_preserves_endpoint_query(self):
        webhook = Webhook(
            "https://example.invalid/hook?existing=1", "get", [Events.SUBSCRIPTION]
        )
        with patch("TwitchChannelPointsMiner.classes.Webhook.requests.get") as get:
            webhook.send("A&B #tag\nnext", Events.SUBSCRIPTION)
        self.assertEqual(get.call_args.kwargs["params"]["message"], "A&B #tag\nnext")
        self.assertEqual(get.call_args.kwargs["url"], webhook.endpoint)
        self.assertEqual(get.call_args.kwargs["timeout"], 20)

    def test_matrix_uses_put_with_transaction_id(self):
        with patch(
            "TwitchChannelPointsMiner.classes.Matrix.requests.post",
            return_value=response(200, {"access_token": "test-token"}),
        ):
            matrix = Matrix(
                "user",
                "password",
                "https://matrix.example.invalid",
                "!room/test:server",
                [Events.SUBSCRIPTION],
            )
        with patch("TwitchChannelPointsMiner.classes.Matrix.requests.put") as put:
            matrix.send("test", Events.SUBSCRIPTION)
            matrix.send("test", Events.SUBSCRIPTION)
        urls = [call.kwargs["url"] for call in put.call_args_list]
        self.assertNotEqual(urls[0], urls[1])
        self.assertIn("/rooms/%21room%2Ftest%3Aserver/send/m.room.message/", urls[0])
        self.assertNotIn("test-token", urls[0])

    def test_notification_failure_does_not_break_other_services_or_logging(self):
        settings = LoggerSettings(username="", emoji=False)
        formatter = GlobalFormatter(fmt="%(message)s", settings=settings)
        record = logging.LogRecord("test", logging.INFO, "", 0, "message", (), None)
        record.event = Events.SUBSCRIPTION
        with (
            patch.object(
                formatter,
                "telegram",
                side_effect=requests.exceptions.ConnectionError("secret-url"),
            ),
            patch.object(formatter, "discord") as discord,
            patch("TwitchChannelPointsMiner.logger.logging.getLogger") as logger,
        ):
            self.assertEqual(formatter.format(record), "message")
        discord.assert_called_once()
        self.assertNotIn("secret-url", str(logger.return_value.warning.call_args))


class UtilityAndChatRegressionTest(unittest.TestCase):
    def test_server_timestamp_is_valid_iso8601(self):
        from dateutil.parser import isoparse

        self.assertEqual(isoparse(server_time({"server_time": 0})).timestamp(), 0)
        isoparse(server_time(None))

    def test_chat_connection_uses_tls_with_a_timeout(self):
        with patch(
            "TwitchChannelPointsMiner.classes.Chat.ssl.create_default_context"
        ) as context:
            client = ClientIRC("tester", "test-token", "streamer")
        with patch.object(client, "connect") as connection:
            client._connect()
        address = connection.call_args.args[:2]
        self.assertEqual(address, ("irc.chat.twitch.tv", 6697))
        with patch(
            "TwitchChannelPointsMiner.classes.Chat.socket.create_connection"
        ) as connect:
            secured_socket = connection.call_args.kwargs["connect_factory"](address)
        connect.assert_called_once_with(address, timeout=20)
        context.assert_called_once_with()
        context.return_value.wrap_socket.assert_called_once_with(
            connect.return_value, server_hostname="irc.chat.twitch.tv"
        )
        self.assertIs(secured_socket, context.return_value.wrap_socket.return_value)

    def test_leaving_chat_waits_for_original_thread_before_replacing_it(self):
        streamer = Streamer("tester", StreamerSettings(chat=ChatPresence.ALWAYS))
        chat = Mock(username="tester", token="test-token")
        chat.is_alive.return_value = True
        streamer.irc_chat = chat
        streamer.leave_chat()
        chat.stop.assert_called_once()
        chat.join.assert_called_once_with(timeout=25)
        self.assertIsNot(streamer.irc_chat, chat)

    def test_chat_shutdown_during_read_does_not_log_socket_error(self):
        client = ClientIRC("tester", "test-token", "streamer")

        def stop_during_read(**kwargs):
            client.die()
            raise OSError("Read on closed or unwrapped SSL socket")

        with (
            patch.object(client, "_connect"),
            patch.object(client.connection, "disconnect") as disconnect,
            patch.object(client.reactor, "process_once", side_effect=stop_during_read),
            patch("TwitchChannelPointsMiner.classes.Chat.logger.error") as error,
        ):
            client.start()
        error.assert_not_called()
        disconnect.assert_called_once()

    def test_chat_read_error_while_running_is_still_logged_and_disconnects(self):
        client = ClientIRC("tester", "test-token", "streamer")
        with (
            patch.object(client, "_connect"),
            patch.object(client.connection, "disconnect") as disconnect,
            patch.object(
                client.reactor, "process_once", side_effect=OSError("Socket failed")
            ),
            patch("TwitchChannelPointsMiner.classes.Chat.logger.error") as error,
        ):
            client.start()
        error.assert_called_once()
        disconnect.assert_called_once_with("Disconnecting after error")

    def test_connectivity_check_closes_socket_and_does_not_set_global_timeout(self):
        with (
            patch("TwitchChannelPointsMiner.utils.socket.create_connection") as connect,
            patch("TwitchChannelPointsMiner.utils.socket.setdefaulttimeout") as default,
        ):
            self.assertTrue(internet_connection_available())
        connect.return_value.__exit__.assert_called_once()
        default.assert_not_called()

    def test_download_asset_uses_forward_slashes_and_reports_404(self):
        with patch("TwitchChannelPointsMiner.utils.requests.get") as get:
            get.return_value.__enter__.return_value.status_code = 404
            self.assertFalse(download_file("assets\\script.js", "unused-file"))
        self.assertNotIn("\\", get.call_args.args[0])

    def test_dump_json_supports_filename_without_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            try:
                os.chdir(directory)
                dump_json("state.json", {"saved": True})
                self.assertEqual(
                    json.loads(Path("state.json").read_text()), {"saved": True}
                )
            finally:
                os.chdir(previous)

    def test_offline_shutdown_does_not_poll_connectivity_forever(self):
        twitch = Twitch("tester", "ua")
        twitch.running = False
        with patch(
            "TwitchChannelPointsMiner.classes.Twitch.internet_connection_available",
            return_value=False,
        ) as internet:
            twitch._Twitch__check_connection_handler(3)
        internet.assert_not_called()

    def test_stop_before_chat_start_prevents_connection(self):
        thread = ThreadChat("tester", "test-token", "streamer")
        thread.stop()
        with patch("TwitchChannelPointsMiner.classes.Chat.ClientIRC") as irc:
            thread.run()
        irc.assert_not_called()

    def test_finished_chat_thread_is_recreated(self):
        streamer = Streamer("tester", StreamerSettings(chat=ChatPresence.ALWAYS))
        old_thread = Mock(ident=1, username="tester", token="token")
        old_thread.is_alive.return_value = False
        streamer.irc_chat = old_thread
        with patch(
            "TwitchChannelPointsMiner.classes.entities.Streamer.ThreadChat"
        ) as chat:
            streamer.toggle_chat()
        chat.return_value.start.assert_called_once()
        old_thread.start.assert_not_called()
