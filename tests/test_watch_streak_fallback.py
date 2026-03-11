import time
import unittest

from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache
from TwitchChannelPointsMiner.classes.Twitch import ActiveWatchStreakAttempt, Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings


class WatchStreakFallbackTest(unittest.TestCase):
    def test_watch_reward_ends_streak_attempt_without_watch_streak(self):
        twitch = Twitch("fallback-test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="fallback-test")

        settings = StreamerSettings(
            watch_streak=True,
            claim_drops=False,
            claim_moments=False,
            make_predictions=False,
            follow_raid=False,
            community_goals=False,
        )
        streamer = Streamer("streamer", settings=settings)
        streamer.is_online = True
        streamer.online_at = time.time() - 600
        streamer.stream.broadcast_id = "broadcastA"
        streamer.stream.watch_streak_missing = True
        streamer.history["WATCH"] = {"counter": 2, "amount": 20}

        now = time.time()
        session = twitch.watch_streak_cache.ensure_session(
            streamer.username,
            streamer.stream.broadcast_id,
            started_at=now - 600,
            account_name=twitch.account_username,
        )
        attempt = ActiveWatchStreakAttempt(
            session_key=session.key(),
            streamer=streamer.username,
            broadcast_id=streamer.stream.broadcast_id,
            started_at=now - 30,
            watch_counter_at_start=0,
        )
        twitch._active_streak_attempts[session.key()] = attempt

        twitch._cleanup_streak_attempts([streamer], now)

        updated_session = twitch.watch_streak_cache.get_session(
            streamer.username,
            streamer.stream.broadcast_id,
            account_name=twitch.account_username,
        )
        self.assertIsNotNone(updated_session)
        self.assertFalse(updated_session.claimed)
        self.assertIsNotNone(updated_session.ended_at)
        self.assertFalse(streamer.stream.watch_streak_missing)
        self.assertEqual(twitch._active_streak_attempts, {})


if __name__ == "__main__":
    unittest.main()
