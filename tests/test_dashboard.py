"""Dashboard correctness, read-only boundaries, and real refresh orchestration."""

import copy
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from TwitchChannelPointsMiner.classes.Settings import Priority, Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.dashboard.query import ReadCoordinator
from TwitchChannelPointsMiner.dashboard.reader import normalize, operation
from TwitchChannelPointsMiner.dashboard.security import redact
from TwitchChannelPointsMiner.dashboard.server import create_app
from TwitchChannelPointsMiner.dashboard.service import DashboardService
from TwitchChannelPointsMiner.dashboard.settings import DashboardSettings
from TwitchChannelPointsMiner.dashboard.store import DashboardStore
from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache


class Clock:
    def __init__(self):
        self.value = 1793540000.0

    def __call__(self):
        return self.value

    def wait(self, seconds):
        self.value += seconds
        return False


def response_for(payload):
    name = payload["operationName"]
    if name == "ChannelPointsContext":
        return {
            "data": {
                "community": {
                    "channel": {
                        "self": {
                            "communityPoints": {
                                "balance": 52093,
                                "availableClaim": {"id": "claim-me"},
                            },
                            "subscriptionBenefit": {"tier": "2000"},
                        },
                        "communityPointsSettings": {"isEnabled": True},
                    }
                }
            }
        }
    if name == "VideoPlayerStreamInfoOverlayChannel":
        return {
            "data": {
                "user": {
                    "stream": {
                        "id": "broadcast",
                        "viewersCount": 100,
                        "createdAt": "2026-11-01T10:00:00Z",
                    },
                    "broadcastSettings": {
                        "title": "Test stream",
                        "game": {"name": "Test game"},
                    },
                }
            }
        }
    if name == "RewardList":
        return {
            "data": {
                "channel": {
                    "self": {
                        "watchStreakMilestone": {
                            "watchStreakMilestone": {
                                "value": "4",
                                "achievementTimestamp": "2026-11-01T10:10:00Z",
                            },
                            "missedStreams": [
                                {"broadcastIdentifiers": [{"id": "missed"}]}
                            ],
                            "expiresAt": "2027-01-01T00:00:00Z",
                        }
                    }
                }
            }
        }
    if name == "WeeklyVisitRewardsQuery":
        return {"data": {"channel": {"self": {"weeklyVisitRewards": None}}}}
    if name == "ChatRoomBanStatus":
        return {"data": {"chatRoomBanStatus": None}}
    if name == "ChannelFollows":
        return {
            "data": {
                "user": {
                    "follows": {
                        "edges": [
                            {
                                "cursor": "last",
                                "node": {
                                    "login": "2okos",
                                    "self": {
                                        "follower": {
                                            "followedAt": "2025-01-01T00:00:00Z"
                                        }
                                    },
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False},
                    }
                }
            }
        }
    if name == "Inventory":
        return {"data": {"currentUser": {"inventory": {"dropCampaignsInProgress": []}}}}
    if name == "ViewerDropsDashboard":
        return {"data": {"currentUser": {"dropCampaigns": []}}}
    return {"data": {}}


def fixture_service(path, clock=None):
    settings = StreamerSettings(make_predictions=False, favorite=True)
    settings.default()
    settings.bet.default()
    Settings.streamer_settings = settings
    streamer = Streamer("2okos", settings)
    streamer.channel_id = "872174898"
    streamer.channel_points = 1830
    streamer.channel_points_context_at = time.time()
    calls = []
    twitch = SimpleNamespace(
        twitch_login=SimpleNamespace(get_user_id=lambda: "test-account"),
        query_coordinator=None,
    )

    def post(payload):
        def perform():
            twitch.query_coordinator.before_request()
            calls.append(copy.deepcopy(payload))
            return response_for(payload)

        return twitch.query_coordinator.run(payload, perform)

    twitch.post_gql_request = post
    miner = SimpleNamespace(
        username="armi1014",
        streamers=[streamer],
        running=True,
        twitch=twitch,
        prediction_tracker=SimpleNamespace(
            lock=threading.RLock(),
            state={"events": {}, "predictions": {}, "intents": {}},
        ),
        watch_streak_cache=WatchStreakCache(default_account_name="armi1014"),
        ws_pool=SimpleNamespace(clients=[]),
        session_id="test-session",
        start_datetime=datetime.now(),
        priority=[Priority.STREAK, Priority.FAVORITE, Priority.DROPS],
        watch_streak_max_parallel=1,
        streamer_follow_dates={},
        logs_file=None,
    )
    clock = clock or Clock()
    service = DashboardService(miner, DashboardSettings(), state_path=path, clock=clock)
    service.coordinator.wait = clock.wait
    twitch.query_coordinator = service.coordinator
    return service, calls


class DashboardTest(unittest.TestCase):
    def test_automatic_refresh_waits_five_minutes_after_completion(self):
        self.service.request_refresh()
        self.service.refresh_once()
        identity = self.service.refresh["id"]
        finished = self.service.refresh["completed_at"]
        self.service.clock.value = finished + 299
        self.service._queue_automatic_refresh()
        self.assertEqual(self.service.refresh["id"], identity)
        self.service.clock.value = finished + 300
        self.service._queue_automatic_refresh()
        self.assertNotEqual(self.service.refresh["id"], identity)
        self.assertTrue(self.service.refresh["automatic"])
        self.assertEqual(self.service.refresh["state"], "queued")

    def test_large_channel_snapshot_does_not_make_twitch_requests(self):
        self.service.miner.streamers = []
        for index in range(1000):
            settings = StreamerSettings(make_predictions=False)
            settings.default()
            settings.bet.default()
            self.service.miner.streamers.append(Streamer(f"channel_{index}", settings))
        started = time.monotonic()
        snapshot = self.service.build_snapshot()
        self.assertEqual(len(snapshot["channels"]), 1000)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(self.calls, [])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "dashboard.sqlite3"
        self.service, self.calls = fixture_service(self.path)

    def tearDown(self):
        self.service.stop()
        self.folder.cleanup()

    def test_full_refresh_has_no_twitch_actions_and_reports_real_values(self):
        self.service.request_refresh()
        self.service.refresh_once()
        row = self.service.build_snapshot()["channels"][0]
        self.assertEqual(row["points"], 52093)
        self.assertEqual(row["streak"], 4)
        self.assertTrue(row["recoverable"])
        self.assertEqual(row["subscription_tier"], "2000")
        self.assertEqual(self.service.refresh["state"], "complete")
        self.assertEqual(
            self.service.refresh["completed"], self.service.refresh["total"]
        )
        self.assertEqual(len(self.calls), 8)
        self.assertTrue(
            all(
                p["operationName"]
                in {
                    "ChannelPointsContext",
                    "VideoPlayerStreamInfoOverlayChannel",
                    "RewardList",
                    "WeeklyVisitRewardsQuery",
                    "ChatRoomBanStatus",
                    "Inventory",
                    "ViewerDropsDashboard",
                    "ChannelFollows",
                }
                for p in self.calls
            )
        )
        self.assertEqual(self.service.miner.streamers[0].channel_points, 1830)

    def test_cooldown_is_shared_and_survives_restart(self):
        first = self.service.request_refresh()
        self.assertEqual(self.service.request_refresh()["id"], first["id"])
        self.service.refresh_once()
        finished = self.service.refresh["completed_at"]
        self.assertEqual(self.service.refresh["next_manual_at"], finished + 60)
        self.assertEqual(self.service.refresh["next_auto_at"], finished + 300)
        self.assertEqual(self.service.request_refresh()["id"], first["id"])
        self.service.store.flush()
        self.service.stop()
        self.service, self.calls = fixture_service(self.path)
        self.assertEqual(self.service.request_refresh()["id"], first["id"])
        self.service.clock.value = finished + 60
        self.assertNotEqual(self.service.request_refresh()["id"], first["id"])

    def test_partial_failure_retains_last_value_and_marks_its_freshness(self):
        payload = operation("ChannelPointsContext", {"channelLogin": "2okos"})
        self.service.observe_response(payload, response_for(payload), 1, 2)
        self.service.observe_response(
            payload, {"errors": [{"message": "Unavailable"}]}, 3, 4
        )
        row = self.service.build_snapshot()["channels"][0]
        self.assertEqual(row["points"], 52093)
        self.assertEqual(row["freshness"]["points"]["checked_at"], 2)
        self.assertEqual(row["freshness"]["points"]["error"], "Twitch data unavailable")

    def test_delayed_read_cannot_erase_later_live_balance(self):
        payload = operation("ChannelPointsContext", {"channelLogin": "2okos"})
        message = SimpleNamespace(
            topic="community-points-user-v1",
            type="points-earned",
            timestamp="2026-11-01T10:00:00Z",
            data={
                "balance": {"balance": 60000},
                "point_gain": {"reason_code": "WATCH", "total_points": 10},
            },
        )
        started = self.service.clock() - 1
        self.service.live_message(message, self.service.miner.streamers[0])
        self.service.observe_response(
            payload, response_for(payload), started, self.service.clock() + 1
        )
        self.assertEqual(self.service.build_snapshot()["channels"][0]["points"], 60000)

    def test_live_gains_are_deduped_and_payouts_are_not_collection(self):
        at = datetime.fromtimestamp(self.service.clock(), timezone.utc).isoformat()
        for reason, amount in [("WATCH", 10), ("PREDICTION", 1000), ("REFUND", 500)]:
            message = SimpleNamespace(
                topic="community-points-user-v1",
                type="points-earned",
                timestamp=at,
                data={
                    "balance": {"balance": 60000},
                    "point_gain": {"reason_code": reason, "total_points": amount},
                },
            )
            self.service.live_message(message, self.service.miner.streamers[0])
            self.service.live_message(message, self.service.miner.streamers[0])
        self.service.store.flush()
        self.assertEqual(self.service.build_snapshot()["summary"]["earned_today"], 10)

    def test_api_exposes_no_miner_settings_writes_and_checks_origin(self):
        self.service.cached = self.service.build_snapshot()
        app = create_app(self.service)
        client = app.test_client()
        bootstrap = client.get("/api/v1/bootstrap").get_json()
        self.assertTrue(bootstrap["read_only"])
        token = bootstrap["csrf_token"]
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(
                client.open("/api/v1/channels/2okos", method=method).status_code, 405
            )
        self.assertEqual(client.post("/api/v1/refresh").status_code, 403)
        self.assertEqual(
            client.post(
                "/api/v1/refresh",
                headers={"Origin": "https://evil.invalid", "X-CSRF-Token": token},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.get(
                "/api/v1/snapshot", headers={"Host": "evil.invalid"}
            ).status_code,
            403,
        )
        headers = {"Origin": "http://localhost", "X-CSRF-Token": token}
        first = client.post("/api/v1/refresh", headers=headers)
        second = client.post("/api/v1/refresh", headers=headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.get_json()["id"], second.get_json()["id"])
        self.assertEqual(len(self.calls), 0)
        self.assertIn("no-store", first.headers["Cache-Control"])
        self.assertEqual(client.get("/api/v1/history/unknown").status_code, 404)
        self.assertEqual(client.get("/api/v1/history/2okos?start=nan").status_code, 400)
        self.assertEqual(
            client.get("/api/v1/reports/../cookies/armi1014.pkl").status_code, 404
        )

    def test_configuration_output_is_allowlisted(self):
        result = self.service.build_snapshot()
        serialized = json.dumps(result)
        for forbidden in ("password", "webhook_api", "cookies_file", "auth_token"):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(result["system"]["settings"]["make_predictions"])

    def test_recovery_attempt_is_distinct_from_confirmation_and_survives_restart(self):
        self.service.event("recovery_trying", channel="2okos", job_kind="recovery")
        self.service.event(
            "recovery_clip",
            channel="2okos",
            job_kind="recovery",
            method="Clip",
            replay_url="https://clips.twitch.tv/example",
        )
        self.assertEqual(
            self.service.build_snapshot()["channels"][0]["recovery_job"]["state"],
            "clip",
        )
        self.service.stop()
        self.service, _ = fixture_service(self.path)
        self.assertEqual(
            self.service.build_snapshot()["channels"][0]["recovery_job"]["state"],
            "interrupted",
        )
        self.service.event("recovery_confirmed", channel="2okos", job_kind="recovery")
        self.service.store.flush()
        self.assertEqual(len(self.service.store.events()), 3)

    def test_log_cursor_handles_append_rotation_and_secrets(self):
        path = Path(self.folder.name) / "miner.log"
        path.write_text(
            "01/11/26 11:00:00 - INFO - test - [run]: normal\n01/11/26 11:00:01 - DEBUG - test - [run]: Authorization: OAuth top-secret\n",
            encoding="utf-8",
        )
        self.service.miner.logs_file = str(path)
        read = self.service.logs()
        self.assertEqual(len(read["lines"]), 1)
        with path.open("a") as out:
            out.write("01/11/26 11:00:02 - WARNING - test - [run]: retry\n")
        self.assertEqual(
            self.service.logs(read["cursor"])["lines"][0]["message"], "retry"
        )
        all_lines = self.service.logs(debug=True)
        self.assertNotIn("top-secret", json.dumps(all_lines))
        path.write_text(
            "01/11/26 11:00:03 - ERROR - test - [run]: rotated\n", encoding="utf-8"
        )
        self.assertEqual(
            self.service.logs(all_lines["cursor"])["lines"][0]["message"], "rotated"
        )


class CoordinatorTest(unittest.TestCase):
    def test_read_cache_expires_and_has_a_four_megabyte_ceiling(self):
        clock = Clock()
        broker = ReadCoordinator(clock=clock, wait=clock.wait)
        for index in range(70):
            broker.run(
                operation("ChannelPointsContext", {"channelLogin": str(index)}),
                lambda: {"data": {"padding": "x" * 100000}},
            )
        self.assertLessEqual(
            sum(len(k) + len(v[1]) for k, v in broker.cache.items()), 4 * 1024 * 1024
        )
        self.assertLessEqual(len(broker.cache), 64)
        clock.value += 16
        broker.run(operation("Inventory"), lambda: {"data": {"inventory": {}}})
        self.assertEqual(len(broker.cache), 1)

    def test_oversized_response_is_still_shared_with_inflight_waiters(self):
        broker = ReadCoordinator()
        started, release = threading.Event(), threading.Event()
        calls = []

        def work():
            calls.append(1)
            started.set()
            release.wait(2)
            return {"data": {"padding": "x" * (4 * 1024 * 1024)}}

        results = []
        payload = operation("Inventory")
        a = threading.Thread(target=lambda: results.append(broker.run(payload, work)))
        b = threading.Thread(target=lambda: results.append(broker.run(payload, work)))
        a.start()
        started.wait(1)
        b.start()
        time.sleep(0.02)
        release.set()
        a.join()
        b.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(results[1]["data"]["padding"]), 4 * 1024 * 1024)
        self.assertEqual(broker.cache, {})

    def test_existing_batch_results_can_be_reused_without_new_requests(self):
        broker = ReadCoordinator()
        payload = [
            operation("Inventory"),
            operation("ChannelPointsContext", {"channelLogin": "2okos"}),
        ]
        broker.run(payload, lambda: [response_for(p) for p in payload])
        callback = Mock(side_effect=AssertionError("duplicate HTTP read"))
        result = broker.run(payload[1], callback)
        self.assertEqual(result, response_for(payload[1]))

    def test_retry_attempts_are_accounted_at_the_actual_http_boundary(self):
        import requests

        clock = Clock()
        broker = ReadCoordinator(clock=clock, wait=clock.wait)
        twitch = object.__new__(Twitch)
        twitch.query_coordinator = broker
        twitch.running = True
        response = SimpleNamespace(status_code=200, headers={})
        with broker.observation(), patch(
            "requests.request",
            side_effect=[
                requests.exceptions.ConnectionError("getaddrinfo failed"),
                response,
            ],
        ):
            result = twitch._request_with_retry(
                "POST", "https://gql.twitch.tv/gql", request_name="test", backoff_base=0
            )
        self.assertIs(result, response)
        self.assertEqual(broker.observer_requests, 2)

    def test_requests_and_retries_share_observer_budget(self):
        clock = Clock()
        broker = ReadCoordinator(clock=clock, wait=clock.wait)
        times = []
        with broker.observation():
            for _ in range(4):
                broker.before_request()
                times.append(clock())
        self.assertTrue(all(b - a >= 1 for a, b in zip(times, times[1:])))
        self.assertEqual(broker.observer_requests, 4)

    def test_single_flight_and_recent_success_are_shared(self):
        broker = ReadCoordinator()
        payload = operation("Inventory")
        started, release = threading.Event(), threading.Event()
        calls = []

        def work():
            calls.append(1)
            started.set()
            release.wait(2)
            return {"data": {"ok": 1}}

        result = []
        first = threading.Thread(
            target=lambda: result.append(broker.run(payload, work))
        )
        second = threading.Thread(
            target=lambda: result.append(broker.run(payload, work))
        )
        first.start()
        started.wait(1)
        second.start()
        release.set()
        first.join()
        second.join()
        result.append(broker.run(payload, work))
        self.assertEqual(len(calls), 1)
        result[0]["data"]["ok"] = 2
        self.assertEqual(result[2]["data"]["ok"], 1)

    def test_headers_and_exponential_backoff_are_persistable(self):
        clock = Clock()
        broker = ReadCoordinator(clock=clock, wait=clock.wait)
        response = SimpleNamespace(status_code=429, headers={})
        broker.response(response)
        self.assertEqual(broker.backoff_until, clock() + 60)
        clock.value += 60
        broker.response(response)
        self.assertEqual(broker.backoff_until, clock() + 120)
        broker.response(
            SimpleNamespace(
                status_code=429,
                headers={"Retry-After": "600", "Ratelimit-Reset": str(clock() + 800)},
            )
        )
        self.assertEqual(broker.backoff_until, clock() + 800)
        restored = ReadCoordinator(
            persisted=broker.status(), clock=clock, wait=clock.wait
        )
        self.assertEqual(restored.backoff_until, broker.backoff_until)
        broker.decoded({"errors": [{"extensions": {"code": "RATE_LIMITED"}}]})
        self.assertEqual(broker.strikes, 4)

    def test_mutations_are_rejected_for_observation_and_observer_failure_isolated(self):
        broker = ReadCoordinator(
            on_result=Mock(side_effect=RuntimeError("broken observer"))
        )
        with broker.observation():
            with self.assertRaises(ValueError):
                broker.run({"operationName": "MakePrediction"}, Mock())
        self.assertEqual(
            broker.run(operation("Inventory"), lambda: {"data": {"ok": True}}),
            {"data": {"ok": True}},
        )


class StoreTest(unittest.TestCase):
    def test_retention_keeps_exact_extrema_first_last_and_events(self):
        with tempfile.TemporaryDirectory() as folder:
            store = DashboardStore(Path(folder) / "history.sqlite3")
            try:
                at = 1700000000
                for seconds, value in ((0, 100), (60, 300), (120, 200)):
                    store.sample("channel", value, at + seconds)
                store.event("recovery_confirmed", "Confirmed", at=at, identity="one")
                store.event("recovery_confirmed", "Confirmed", at=at, identity="one")
                store.compact(at + 100 * 86400)
                store.flush()
                self.assertEqual(len(store.events(start=0, end=at + 1)), 1)
                with store.lock:
                    values = store.db.execute(
                        "SELECT first_balance,balance,low,high FROM samples WHERE resolution='hour'"
                    ).fetchone()
                    self.assertEqual(values, (100, 200, 100, 300))
                    self.assertEqual(
                        store.db.execute(
                            "SELECT count(*) FROM samples WHERE resolution='minute'"
                        ).fetchone()[0],
                        0,
                    )
                history = store.history("channel", at - 1, at + 200)
                self.assertIn(history[-1]["balance"], (100, 200, 300))
            finally:
                store.close()

    def test_corrupt_database_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.sqlite3"
            path.write_bytes(b"user data")
            with self.assertRaises(Exception):
                DashboardStore(path)
            self.assertEqual(path.read_bytes(), b"user data")

    def test_repeated_historical_import_does_not_repeat_events(self):
        with tempfile.TemporaryDirectory() as folder:
            service, _ = fixture_service(Path(folder) / "state.sqlite3")
            try:
                service.import_history()
                service.store.flush()
                count = len(service.store.events())
                service.import_history()
                service.store.flush()
                self.assertEqual(count, len(service.store.events()))
            finally:
                service.stop()


class ReaderSecurityTest(unittest.TestCase):
    def test_current_twitch_campaign_response_accepts_explicit_empty_drop_list(self):
        response = {
            "data": {
                "currentUser": {"dropCampaigns": None},
                "rewardCampaignsAvailableToUser": [
                    {
                        "id": "reward",
                        "name": "Reward event",
                        "status": "ACTIVE",
                        "startsAt": "2026-11-01T00:00:00Z",
                        "endsAt": "2026-11-02T00:00:00Z",
                    }
                ],
            }
        }
        result = normalize("ViewerDropsDashboard", response)
        self.assertEqual(result["campaigns"][0]["id"], "reward")
        self.assertIsNotNone(result["campaigns"][0]["ends_at"])

    def test_pure_fetch_helpers_do_not_claim_available_rewards(self):
        twitch = object.__new__(Twitch)
        with patch.object(
            Twitch, "post_gql_request", side_effect=response_for
        ), patch.object(Twitch, "claim_bonus") as bonus, patch.object(
            Twitch, "_confirm_drop_claims"
        ) as claims, patch.object(
            Twitch, "contribute_to_community_goals"
        ) as contribute:
            self.assertIn("data", twitch.fetch_channel_points_context("2okos"))
            self.assertIsInstance(twitch.fetch_inventory(), dict)
            bonus.assert_not_called()
            claims.assert_not_called()
            contribute.assert_not_called()

    def test_streak_value_and_noneligible_weekly_rewards(self):
        self.assertEqual(
            normalize("RewardList", response_for(operation("RewardList")))["streak"], 4
        )
        self.assertEqual(
            normalize(
                "WeeklyVisitRewardsQuery",
                {
                    "errors": [
                        {
                            "message": 'graphql: got nil for non-null "WeeklyVisitRewardTier"',
                            "path": [
                                "channel",
                                "self",
                                "weeklyVisitRewards",
                                "currentReward",
                            ],
                        }
                    ]
                },
            ),
            {"weekly": None},
        )
        self.assertFalse(
            normalize(
                "ChatRoomBanStatus",
                {"data": {"chatRoomBanStatus": {"banStatus": None}}},
            )["chat_banned"]
        )

    def test_redaction_covers_webhook_tokens_headers_and_playback_urls(self):
        text = 'https://discord.com/api/webhooks/123/private-token Authorization: Bearer abc-secret {"auth-token":"cookie-secret"} https://host/vod?sig=private-sig&token=private-token'
        output = redact(text)
        for value in ("abc-secret", "cookie-secret", "private-sig", "private-token"):
            self.assertNotIn(value, output)

    def test_settings_are_local_and_numerically_valid(self):
        for kwargs in (
            {"host": "0.0.0.0"},
            {"port": True},
            {"refresh_seconds": float("nan")},
            {"cooldown_seconds": 0},
        ):
            with self.assertRaises(ValueError):
                DashboardSettings(**kwargs)


if __name__ == "__main__":
    unittest.main()
