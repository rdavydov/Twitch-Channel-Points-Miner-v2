import json
import os
import tempfile
import time
import unittest

from TwitchChannelPointsMiner.WatchStreakCache import (
    MIN_OFFLINE_FOR_NEW_STREAK,
    STALE_SESSION_TTL_SECONDS,
    WatchStreakCache,
)


class WatchStreakCacheTest(unittest.TestCase):
    def test_cache_session_lifecycle_and_prune(self):
        now = time.time()
        cache = WatchStreakCache(default_account_name="tester")

        session = cache.ensure_session("streamer", "broadcastA", now)
        self.assertEqual(session.attempts, 0)

        cache.mark_attempt("streamer", "broadcastA", now + 10)
        self.assertEqual(cache.get_session("streamer", "broadcastA").attempts, 1)

        cache.mark_claimed("streamer", "broadcastA", now + 20)
        claimed_session = cache.get_session("streamer", "broadcastA")
        self.assertTrue(claimed_session.claimed)
        self.assertIsNotNone(claimed_session.ended_at)

        cache.record_online("streamer", "broadcastA", now + 30)
        self.assertFalse(cache.should_create_session("streamer"))

        cache.record_offline("streamer", now + 60)
        cache.mark_bootstrap_done()
        cache.record_online(
            "streamer",
            "broadcastB",
            now + 60 + MIN_OFFLINE_FOR_NEW_STREAK + 5,
        )
        self.assertTrue(cache.should_create_session("streamer"))

        # Session ended at now + 20 above, so prune after ttl + margin from that point.
        cache._prune_stale_sessions(now + STALE_SESSION_TTL_SECONDS + 60)
        self.assertIsNone(cache.get_session("streamer", "broadcastA"))

    def test_load_from_disk_can_filter_by_account(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "watch_streak_cache.json")
            payload = {
                "version": 2,
                "sessions": [
                    {
                        "account_name": "acc_one",
                        "streamer_login": "streamer-a",
                        "broadcast_id": "b1",
                        "started_at": 1,
                        "attempts": 0,
                        "claimed": False,
                        "last_attempt_at": None,
                        "ended_at": None,
                    },
                    {
                        "account_name": "acc_two",
                        "streamer_login": "streamer-b",
                        "broadcast_id": "b2",
                        "started_at": 2,
                        "attempts": 0,
                        "claimed": False,
                        "last_attempt_at": None,
                        "ended_at": None,
                    },
                ],
            }
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj)

            cache = WatchStreakCache.load_from_disk(
                path,
                default_account_name="acc_one",
                account_filter="acc_one",
            )
            self.assertIsNotNone(cache.get_session("streamer-a", "b1"))
            self.assertIsNone(cache.get_session("streamer-b", "b2", account_name="acc_two"))

    def test_short_offline_gap_does_not_create_session_even_if_broadcast_changes(self):
        now = time.time()
        cache = WatchStreakCache(default_account_name="tester")
        cache.mark_bootstrap_done()

        cache.record_online("streamer", "broadcastA", now)
        cache.record_offline("streamer", now + 5)
        cache.record_online("streamer", "broadcastB", now + 120)

        self.assertFalse(cache.should_create_session("streamer"))

    def test_long_offline_gap_creates_session_when_broadcast_changes(self):
        now = time.time()
        cache = WatchStreakCache(default_account_name="tester")
        cache.mark_bootstrap_done()

        cache.record_online("streamer", "broadcastA", now)
        cache.record_offline("streamer", now + 5)
        cache.record_online(
            "streamer",
            "broadcastB",
            now + 5 + MIN_OFFLINE_FOR_NEW_STREAK + 1,
        )

        self.assertTrue(cache.should_create_session("streamer"))

    def test_bootstrap_online_streamer_can_create_initial_session_without_offline_gap(self):
        now = time.time()
        cache = WatchStreakCache(default_account_name="tester")

        cache.record_online("streamer", "broadcastA", now)
        self.assertFalse(cache.should_create_session("streamer"))

        cache.mark_bootstrap_done()
        self.assertTrue(cache.should_create_session("streamer"))

    def test_custom_min_offline_gap_allows_immediate_new_session(self):
        now = time.time()
        cache = WatchStreakCache(
            default_account_name="tester", min_offline_for_new_streak=0
        )
        cache.mark_bootstrap_done()

        cache.record_online("streamer", "broadcastA", now)
        cache.record_offline("streamer", now + 5)
        cache.record_online("streamer", "broadcastB", now + 20)

        self.assertTrue(cache.should_create_session("streamer"))

    def test_streamer_status_saved_and_loaded(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "watch_streak_cache.json")
            now = time.time()
            cache = WatchStreakCache(default_account_name="acc_one")
            cache.set_streamer_status(
                "online_detected",
                watch_streak_detected=True,
                watch_streak_days=7,
                last_stream_started_at=now - 120,
                is_online=True,
                broadcast_id="broadcast-1",
                checked_at=now,
            )
            cache.set_streamer_status(
                "offline_missing",
                watch_streak_detected=False,
                is_online=False,
                broadcast_id=None,
                checked_at=now,
            )
            cache.save_to_disk_if_dirty(path)

            loaded = WatchStreakCache.load_from_disk(
                path,
                default_account_name="acc_one",
                account_filter="acc_one",
            )
            online = loaded.get_streamer_status("online_detected")
            offline = loaded.get_streamer_status("offline_missing")

            self.assertIsNotNone(online)
            self.assertTrue(online.watch_streak_detected)
            self.assertEqual(online.watch_streak_days, 7)
            self.assertEqual(online.last_stream_started_at, now - 120)
            self.assertTrue(online.is_online)
            self.assertEqual(online.broadcast_id, "broadcast-1")

            self.assertIsNotNone(offline)
            self.assertFalse(offline.watch_streak_detected)
            self.assertFalse(offline.is_online)
            self.assertIsNone(offline.broadcast_id)

    def test_set_streamer_status_keeps_existing_metadata_when_not_provided(self):
        now = time.time()
        cache = WatchStreakCache(default_account_name="acc_one")

        cache.set_streamer_status(
            "demo",
            watch_streak_detected=True,
            watch_streak_days=9,
            last_stream_started_at=now - 300,
            is_online=True,
            broadcast_id="broadcast-1",
            checked_at=now,
        )

        cache.set_streamer_status(
            "demo",
            watch_streak_detected=False,
            is_online=False,
            broadcast_id=None,
            checked_at=now + 10,
        )

        status = cache.get_streamer_status("demo")
        self.assertIsNotNone(status)
        self.assertEqual(status.watch_streak_days, 9)
        self.assertEqual(status.last_stream_started_at, now - 300)

    def test_streamer_statuses_respect_account_filter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "watch_streak_cache.json")
            payload = {
                "version": 3,
                "sessions": [],
                "streamer_statuses": [
                    {
                        "account_name": "acc_one",
                        "streamer_login": "streamer-a",
                        "watch_streak_detected": True,
                        "is_online": True,
                        "broadcast_id": "a1",
                        "checked_at": 1,
                    },
                    {
                        "account_name": "acc_two",
                        "streamer_login": "streamer-b",
                        "watch_streak_detected": False,
                        "is_online": False,
                        "broadcast_id": None,
                        "checked_at": 2,
                    },
                ],
            }
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj)

            cache = WatchStreakCache.load_from_disk(
                path,
                default_account_name="acc_one",
                account_filter="acc_one",
            )
            self.assertIsNotNone(cache.get_streamer_status("streamer-a"))
            self.assertIsNone(
                cache.get_streamer_status("streamer-b", account_name="acc_two")
            )

    def test_claimed_streak_days_counts_only_claimed_sessions(self):
        now = time.time()
        cache = WatchStreakCache(default_account_name="tester")

        cache.ensure_session("easyemi", "b1", now)
        cache.mark_claimed("easyemi", "b1", now + 1)
        cache.ensure_session("easyemi", "b2", now + 2)
        cache.mark_claimed("easyemi", "b2", now + 3)
        cache.ensure_session("easyemi", "b3", now + 4)
        cache.ensure_session("rubia", "r1", now + 5)
        cache.mark_claimed("rubia", "r1", now + 6)

        self.assertEqual(cache.claimed_streak_days("easyemi"), 2)
        self.assertEqual(cache.claimed_streak_days("rubia"), 1)
        self.assertEqual(cache.claimed_streak_days("itsceydi"), 0)



if __name__ == "__main__":
    unittest.main()
