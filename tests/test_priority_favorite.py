import time
import unittest

from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings


class FavoritePriorityTest(unittest.TestCase):
    def _make_streamer(
        self,
        username: str,
        *,
        favorite: bool,
        points: int,
        watch_streak: bool = False,
        subscribed: bool = False,
    ) -> Streamer:
        settings = StreamerSettings(
            watch_streak=watch_streak,
            favorite=favorite,
            claim_drops=False,
            claim_moments=False,
            make_predictions=False,
            follow_raid=False,
            community_goals=False,
        )
        streamer = Streamer(username, settings=settings)
        streamer.channel_points = points
        streamer.activeMultipliers = [{"factor": 1}] if subscribed else []
        streamer.is_online = True
        streamer.online_at = time.time() - 180
        streamer.stream.broadcast_id = f"broadcast-{username}"
        streamer.stream.watch_streak_missing = watch_streak
        return streamer

    def test_favorite_priority_selects_favorites_before_non_favorites(self):
        twitch = Twitch("favorite-priority", "ua")
        twitch.max_watch_amount = 2

        streamers = [
            self._make_streamer("fav_high_points", favorite=True, points=500),
            self._make_streamer("nonfav_low_points", favorite=False, points=10),
            self._make_streamer("fav_mid_points", favorite=True, points=200),
        ]

        selection = twitch._select_streamers_to_watch(
            streamers,
            list(range(len(streamers))),
            [Priority.FAVORITE, Priority.POINTS_ASCENDING],
        )

        selected_usernames = [streamers[i].username for i in selection]
        self.assertEqual(selected_usernames, ["fav_mid_points", "fav_high_points"])

    def test_favorite_priority_without_online_favorites_keeps_next_priorities(self):
        twitch = Twitch("favorite-no-online", "ua")
        twitch.max_watch_amount = 2

        streamers = [
            self._make_streamer("sub_high", favorite=False, subscribed=True, points=300),
            self._make_streamer("sub_low", favorite=False, subscribed=True, points=100),
            self._make_streamer("nonsub_lowest", favorite=False, subscribed=False, points=1),
        ]

        selection = twitch._select_streamers_to_watch(
            streamers,
            [0, 1, 2],
            [Priority.FAVORITE, Priority.SUBSCRIBED, Priority.POINTS_ASCENDING],
        )

        selected_usernames = [streamers[i].username for i in selection]
        self.assertEqual(selected_usernames, ["sub_low", "sub_high"])

    def test_streak_priority_still_preempts_favorites(self):
        twitch = Twitch("favorite-streak", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="favorite-streak")
        twitch.max_watch_amount = 2
        twitch.max_streak_sessions = 2

        now = time.time()
        streak_a = self._make_streamer("streak_a", favorite=False, points=100, watch_streak=True)
        streak_b = self._make_streamer("streak_b", favorite=False, points=150, watch_streak=True)
        favorite = self._make_streamer("favorite", favorite=True, points=1, watch_streak=False)

        for streamer in [streak_a, streak_b]:
            twitch.watch_streak_cache.ensure_session(
                streamer.username,
                streamer.stream.broadcast_id,
                started_at=now - 180,
                account_name=twitch.account_username,
            )

        streamers = [favorite, streak_a, streak_b]
        selection = twitch._select_streamers_to_watch(
            streamers,
            [0, 1, 2],
            [Priority.STREAK, Priority.FAVORITE, Priority.POINTS_ASCENDING],
        )

        selected_usernames = [streamers[i].username for i in selection]
        self.assertEqual(set(selected_usernames), {"streak_a", "streak_b"})


if __name__ == "__main__":
    unittest.main()
