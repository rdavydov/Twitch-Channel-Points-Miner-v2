import copy
import json
import logging
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.PredictionTracker import PredictionTracker
from TwitchChannelPointsMiner.classes.PubSub import PubSubHandler
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Bet import BetSettings, Strategy
from TwitchChannelPointsMiner.classes.entities.EventPrediction import EventPrediction
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.logger import (
    GlobalFormatter,
    LoggerSettings,
    configure_loggers,
)

MODULE = "TwitchChannelPointsMiner.classes.PredictionTracker"


class PredictionTrackingTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "logs/.state/predictions.test.json"
        self.twitch = Twitch("test", "ua")
        settings = BetSettings(
            strategy=Strategy.NUMBER_1, percentage=5, max_points=5000
        )
        settings.default()
        self.streamer = Streamer(
            "2okos", StreamerSettings(bet=settings, make_predictions=False)
        )
        self.streamer.channel_id = "123"
        self.streamer.channel_points = 100000
        self.event = EventPrediction(
            self.streamer,
            "event-1",
            "Who wins?",
            datetime.now(timezone.utc),
            60,
            "ACTIVE",
            [
                {
                    "id": "ice",
                    "title": "ICE",
                    "color": "BLUE",
                    "total_users": 1,
                    "total_points": 10,
                },
                {
                    "id": "kds",
                    "title": "KDS",
                    "color": "PINK",
                    "total_users": 2,
                    "total_points": 20,
                },
            ],
        )
        self.events = {"event-1": self.event}
        self.streamers = [self.streamer]
        self.settings = LoggerSettings(
            less=True,
            emoji=False,
            colored=False,
            discord=Discord(
                "https://discord.example.invalid/TEST_SECRET",
                [Events.BET_PLACED, Events.BET_WIN, Events.BET_LOSE, Events.BET_REFUND],
            ),
        )
        self.addCleanup(patch.stopall)
        patch.object(Settings, "logger", self.settings, create=True).start()
        patch.object(Settings, "enable_analytics", False, create=True).start()
        self.formatter = GlobalFormatter(fmt="%(message)s", settings=self.settings)
        self.records = []

        def deliver(message, *args, extra):
            record = logging.makeLogRecord({"msg": message, "args": args, **extra})
            self.records.append(record)
            self.formatter.format(record)

        self.logger = patch(MODULE + ".logger").start()
        self.logger.info.side_effect = deliver
        self.post = patch("requests.post", return_value=Mock()).start()
        self.tracker = self.new_tracker()
        self.twitch.prediction_tracker = self.tracker

    def new_tracker(self, *, account="test", events=None):
        tracker = PredictionTracker(
            self.twitch,
            account,
            state_path=self.path,
            events=self.events if events is None else events,
            streamers=self.streamers,
        )
        tracker.account_id = "user-1"
        return tracker

    def payload(
        self, *, points=52093, result=None, event_id="event-1", outcome="kds", at=None
    ):
        return {
            "id": "prediction-" + event_id,
            "event_id": event_id,
            "channel_id": "123",
            "user_id": "user-1",
            "outcome_id": outcome,
            "points": points,
            "predicted_at": "2026-10-26T18:10:39Z",
            "updated_at": at or datetime.now(timezone.utc).isoformat(),
            "result": result,
        }

    def snapshot(self, payload):
        return {
            "id": payload["event_id"],
            "channel_id": payload["channel_id"],
            "channel_login": "2okos",
            "title": "Who wins?",
            "status": "RESOLVED" if payload.get("result") else "ACTIVE",
            "outcomes": [
                {"id": "ice", "title": "ICE", "color": "BLUE"},
                {"id": "kds", "title": "KDS", "color": "PINK"},
            ],
            "prediction": payload,
        }

    def message(self, payload, kind):
        return SimpleNamespace(
            channel_id="123",
            topic="predictions-user-v1",
            type=kind,
            data={"prediction": payload},
        )

    def test_manual_bet_overrides_planned_choice_and_cannot_be_overwritten_by_timer(
        self,
    ):
        self.event.bet.calculate(
            100000
        )  # Planned ICE, different from the real KDS wager.
        handler = PubSubHandler(self.twitch, self.streamers, self.events, self.tracker)
        payload = self.payload()
        before = copy.deepcopy(payload)
        handler.on_message(self.message(payload, "prediction-made"))
        self.assertEqual(payload, before)
        details = self.records[-1].discord_details
        self.assertEqual(
            (details["stake"], details["outcome"], details["source"]),
            (52093, "KDS", "Manual / external"),
        )
        self.assertEqual(
            self.event.bet.decision, {"id": "kds", "amount": 52093, "choice": 1}
        )
        with patch.object(Twitch, "post_gql_request") as post:
            self.twitch.make_predictions(self.event)
        post.assert_not_called()
        self.assertEqual(self.event.bet.decision["amount"], 52093)

    def test_result_without_placement_and_duplicate_results_account_once(self):
        handler = PubSubHandler(self.twitch, self.streamers, self.events, self.tracker)
        message = self.message(
            self.payload(result={"type": "LOSE", "points_won": None}),
            "prediction-result",
        )
        handler.on_message(message)
        handler.on_message(message)
        self.assertEqual(
            self.streamer.history["PREDICTION"], {"counter": 1, "amount": -52093}
        )
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0].discord_details["outcome"], "KDS")

    def test_all_result_numbers_and_refund_semantics(self):
        for result_type, won, payout, net in (
            ("WIN", 8750, 8750, 3750),
            ("LOSE", None, 0, -5000),
            ("REFUND", 0, 5000, 0),
        ):
            with self.subTest(result_type=result_type):
                event_id = "case-" + result_type
                self.tracker.remember_event(
                    event_id, self.snapshot(self.payload(event_id=event_id))
                )
                self.tracker.handle_user(
                    self.payload(
                        event_id=event_id,
                        points=5000,
                        result={"type": result_type, "points_won": won},
                    ),
                    "prediction-result",
                )
                details = self.records[-1].discord_details
                self.assertEqual(
                    (details["stake"], details["payout"], details["net_points"]),
                    (5000, payout, net),
                )

    def test_restarts_reconcile_a_result_settled_while_offline_and_do_not_repeat_it(
        self,
    ):
        self.tracker.handle_user(self.payload(points=1000), "prediction-made")
        restored = self.new_tracker(events={})
        settled = self.payload(points=1000, result={"type": "WIN", "points_won": 2400})
        with patch.object(
            Twitch, "get_prediction_snapshot", return_value=self.snapshot(settled)
        ) as query:
            restored.reconcile_once()
        query.assert_called_once_with("event-1", "123")
        self.assertEqual(len(self.records), 2)
        self.assertTrue(self.records[-1].discord_details["recovered"])
        self.assertEqual(restored.summary()["net"], 1400)
        again = self.new_tracker(events={})
        with patch.object(Twitch, "get_prediction_snapshot") as query:
            again.reconcile_once()
        query.assert_not_called()
        self.assertEqual(len(self.records), 2)

    def test_crash_after_request_intent_recovers_without_placing_another_bet(self):
        decision = {"id": "ice", "amount": 2000, "choice": 0}
        self.assertTrue(self.tracker.register_intent(self.event, decision))
        restored = self.new_tracker(events={})
        payload = self.payload(
            points=2000, outcome="ice", result={"type": "WIN", "points_won": 4500}
        )
        with patch.object(
            Twitch, "get_prediction_snapshot", return_value=self.snapshot(payload)
        ), patch.object(Twitch, "post_gql_request") as post:
            restored.reconcile_once()
        post.assert_not_called()
        self.assertEqual(self.records[-1].event, Events.BET_WIN)
        self.assertEqual(self.records[-1].discord_details["source"], "Miner")
        self.assertEqual(restored.summary(source="Miner")["net"], 2500)

    def test_unknown_manual_event_is_enriched_even_when_auto_betting_is_disabled(self):
        self.events.clear()
        payload = self.payload(event_id="unknown")
        handler = PubSubHandler(self.twitch, self.streamers, self.events, self.tracker)
        handler.on_message(self.message(payload, "prediction-made"))
        self.assertEqual(self.records, [])
        self.assertFalse(self.streamer.settings.make_predictions)
        with patch.object(
            Twitch, "get_prediction_snapshot", return_value=self.snapshot(payload)
        ):
            self.tracker.reconcile_once()
        self.assertEqual(self.records[-1].discord_details["stake"], 52093)
        self.assertEqual(self.records[-1].discord_details["outcome"], "KDS")

    def test_unmonitored_channel_is_not_discarded(self):
        tracker = PredictionTracker(self.twitch, "test", events={}, streamers=[])
        tracker.remember_event("event-1", self.snapshot(self.payload()))
        handler = PubSubHandler(self.twitch, [], {}, tracker)
        handler.on_message(self.message(self.payload(), "prediction-made"))
        self.assertEqual(self.records[-1].discord_details["channel"], "2okos")

    def test_failed_discord_delivery_is_retried_after_restart(self):
        self.post.side_effect = requests.Timeout("TEST_SECRET")
        self.tracker.handle_user(self.payload(), "prediction-made")
        saved = json.loads(self.path.read_text())
        self.assertNotIn(
            "discord", saved["predictions"]["event-1"].get("placement_sent", [])
        )
        self.post.side_effect = None
        restored = self.new_tracker()
        restored.emit_pending()
        self.assertEqual(self.post.call_count, 2)
        self.assertEqual(
            restored.state["predictions"]["event-1"]["placement_sent"], ["discord"]
        )
        self.new_tracker().emit_pending()
        self.assertEqual(self.post.call_count, 2)
        self.assertNotIn("TEST_SECRET", self.path.read_text())

    def test_retry_does_not_repeat_a_provider_that_already_succeeded(self):
        self.settings.telegram = SimpleNamespace(events=[str(Events.BET_PLACED)])
        with patch.object(self.formatter, "telegram") as telegram:
            self.post.side_effect = requests.ConnectionError("TEST_SECRET")
            self.tracker.handle_user(self.payload(), "prediction-made")
            self.post.side_effect = None
            self.new_tracker().emit_pending()
        telegram.assert_called_once()
        self.assertEqual(self.post.call_count, 2)

    def test_delayed_placement_does_not_undo_result_and_topups_use_latest_stake(self):
        self.tracker.handle_user(self.payload(points=100), "prediction-made")
        self.tracker.handle_user(self.payload(points=200), "prediction-made")
        self.tracker.handle_user(
            self.payload(points=200, result={"type": "LOSE", "points_won": None}),
            "prediction-result",
        )
        before = len(self.records)
        self.tracker.handle_user(self.payload(points=100), "prediction-made")
        self.assertEqual(len(self.records), before)
        self.assertEqual(self.tracker.summary()["net"], -200)

    def test_payout_balance_notification_does_not_double_count_profit(self):
        handler = PubSubHandler(self.twitch, self.streamers, self.events, self.tracker)
        handler.on_message(
            SimpleNamespace(
                channel_id="123",
                topic="community-points-user-v1",
                type="points-earned",
                data={
                    "balance": {"balance": 104110},
                    "point_gain": {"total_points": 8309, "reason_code": "PREDICTION"},
                },
            )
        )
        handler.on_message(
            self.message(
                self.payload(points=4199, result={"type": "WIN", "points_won": 8309}),
                "prediction-result",
            )
        )
        self.assertEqual(
            self.streamer.history["PREDICTION"], {"counter": 1, "amount": 4110}
        )
        self.assertEqual(self.streamer.channel_points, 104110)

    def test_old_catchup_is_in_history_csv_not_todays_points(self):
        payload = self.payload(
            points=1000,
            result={"type": "LOSE", "points_won": None},
            at="2020-01-02T00:00:00Z",
        )
        self.tracker.handle_user(payload, "prediction-result", recovered=True)
        self.assertNotIn("PREDICTION", self.streamer.history)
        self.assertEqual(self.tracker.summary()["net"], -1000)
        report = self.path.parent.parent / "reports/predictions/predictions.test.csv"
        self.assertIn("2020-01-02", report.read_text(encoding="utf-8-sig"))

    def test_corrupt_or_wrong_account_state_is_preserved(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for text in (
            "{broken",
            json.dumps(
                {
                    "version": 1,
                    "account": "someone-else",
                    "events": {},
                    "predictions": {},
                    "intents": {},
                }
            ),
        ):
            self.path.write_text(text)
            tracker = self.new_tracker()
            self.assertTrue(tracker.read_only)
            tracker.handle_user(self.payload(), "prediction-made")
            self.assertEqual(self.path.read_text(), text)

    def test_malformed_predictions_and_wrong_user_do_not_generate_false_results(self):
        for changes in (
            {"points": None},
            {"points": -1},
            {"points": True},
            {"outcome_id": None},
            {"user_id": "other"},
            {"result": {"type": "WIN", "points_won": None}},
        ):
            with self.subTest(changes=changes):
                payload = {**self.payload(), **changes}
                self.assertFalse(
                    self.tracker.handle_user(
                        payload,
                        "prediction-result"
                        if payload.get("result")
                        else "prediction-made",
                    )
                )
        self.assertEqual(self.records, [])
        self.assertEqual(self.tracker.summary()["closed"], 0)

    def test_api_failure_leaves_pending_record_intact(self):
        self.tracker.handle_user(self.payload(), "prediction-made")
        before = copy.deepcopy(self.tracker.state["predictions"])
        with patch.object(Twitch, "get_prediction_snapshot", return_value=None):
            self.tracker.reconcile_once()
        self.assertEqual(self.tracker.state["predictions"], before)

    def test_failed_atomic_save_keeps_previous_file_and_cleans_temporary_file(self):
        self.tracker.handle_user(self.payload(), "prediction-made")
        before = self.path.read_bytes()
        with patch(MODULE + ".os.replace", side_effect=PermissionError):
            self.tracker.remember_event(
                "event-2", {"title": "Another", "channel_id": "123"}, self.streamer
            )
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_snapshot_query_reads_actual_points_and_results_without_mutation(self):
        response = {
            "data": {
                "user": {"login": "2okos"},
                "predictionEvent": {
                    "id": "event-1",
                    "title": "Who wins?",
                    "status": "RESOLVED",
                    "channel": {"id": "123"},
                    "outcomes": [],
                    "self": {
                        "prediction": {
                            "id": "p",
                            "points": 52093,
                            "outcome": {"id": "kds"},
                            "result": "LOSE",
                            "pointsWon": 0,
                        }
                    },
                },
            }
        }
        with patch.object(Twitch, "post_gql_request", return_value=response) as post:
            snapshot = self.twitch.get_prediction_snapshot("event-1", "123")
        self.assertEqual(snapshot["prediction"]["points"], 52093)
        self.assertEqual(
            snapshot["prediction"]["result"], {"type": "LOSE", "points_won": 0}
        )
        self.assertNotIn("mutation", post.call_args.args[0]["query"])

    def test_csv_does_not_execute_prediction_titles_as_spreadsheet_formulas(self):
        self.event.title = '=HYPERLINK("https://example.invalid", "click")'
        self.tracker.handle_user(
            self.payload(result={"type": "LOSE", "points_won": 0}), "prediction-result"
        )
        report = self.path.parent.parent / "reports/predictions/predictions.test.csv"
        import csv

        with report.open(encoding="utf-8-sig", newline="") as source:
            row = next(csv.DictReader(source))
        self.assertTrue(row["prediction"].startswith("'="))
        self.assertEqual(row["net"], "-52093")

    def test_older_topup_snapshot_does_not_override_newer_data_with_different_timezone_format(
        self,
    ):
        self.tracker.handle_user(
            self.payload(points=200, at="2026-10-26T18:11:00+00:00"), "prediction-made"
        )
        self.tracker.handle_user(
            self.payload(points=100, at="2026-10-26T18:10:00Z"), "prediction-made"
        )
        self.assertEqual(self.tracker.state["predictions"]["event-1"]["points"], 200)

    def test_real_logging_queue_acknowledges_delivery_before_shutdown(self):
        root = logging.getLogger()
        original_handlers, original_level = list(root.handlers), root.level
        working_directory = os.getcwd()
        listener = None
        try:
            os.chdir(self.folder.name)
            with patch("sys.stdout", new=__import__("io").StringIO()):
                _, listener = configure_loggers("queue-test", self.settings)
                with patch(
                    MODULE + ".logger", logging.getLogger("prediction-queue-test")
                ):
                    self.tracker.handle_user(self.payload(), "prediction-made")
                listener.stop()
                saved = json.loads(self.path.read_text())
                self.assertEqual(
                    saved["predictions"]["event-1"]["placement_sent"], ["discord"]
                )
                self.assertEqual(self.post.call_count, 1)
        finally:
            if listener is not None and listener._thread is not None:
                listener.stop()
            if listener is not None:
                for handler in listener.handlers:
                    handler.close()
            for handler in list(root.handlers):
                if handler not in original_handlers:
                    root.removeHandler(handler)
                    handler.close()
            root.setLevel(original_level)
            os.chdir(working_directory)

    def test_reconciliation_does_not_starve_bets_beyond_the_first_batch(self):
        for index in range(21):
            self.tracker.handle_user(
                self.payload(event_id=f"pending-{index}"),
                "prediction-made",
                notify=False,
            )
        with patch.object(
            Twitch, "get_prediction_snapshot", return_value=None
        ) as query:
            self.tracker.reconcile_once()
            self.tracker.reconcile_once()
        self.assertIn(
            ("pending-20", "123"), [call.args for call in query.call_args_list]
        )

    def test_live_prediction_analytics_are_preserved_without_duplicate_annotations(
        self,
    ):
        with patch.object(Settings, "enable_analytics", True), patch.object(
            Streamer, "persistent_annotations"
        ) as annotate:
            self.tracker.handle_user(self.payload(), "prediction-made")
            result = self.payload(result={"type": "LOSE", "points_won": 0})
            self.tracker.handle_user(result, "prediction-result")
            self.tracker.handle_user(result, "prediction-result")
        self.assertEqual(
            [call.args[0] for call in annotate.call_args_list],
            ["PREDICTION_MADE", "LOSE"],
        )


if __name__ == "__main__":
    unittest.main()
