import time
import unittest
from unittest.mock import patch

from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache


class PrioritySortingTest(unittest.TestCase):
    def test_streak_selection_prefers_oldest_pending_stream_before_drops(self):
        twitch = Twitch("test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="test")
        twitch.watch_streak_cache.mark_bootstrap_done()
        twitch.max_watch_amount = 3
        twitch.max_streak_sessions = 3

        def make_streamer(username: str, has_drops: bool) -> Streamer:
            settings = StreamerSettings(
                watch_streak=True,
                claim_drops=True,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
            )
            streamer = Streamer(username, settings=settings)
            streamer.is_online = True
            streamer.online_at = time.time()
            if has_drops:
                streamer.stream.campaigns_ids = ["campaign"]
            return streamer

        streamers = [
            make_streamer("order_first_no_drop", has_drops=False),
            make_streamer("order_second_with_drop", has_drops=True),
            make_streamer("order_third_no_drop", has_drops=False),
        ]
        streamers_index = list(range(len(streamers)))

        selection = twitch._select_streamers_to_watch(
            streamers, streamers_index, [Priority.STREAK, Priority.DROPS, Priority.ORDER]
        )

        selected_usernames = [streamers[i].username for i in selection]
        self.assertEqual(
            selected_usernames[0],
            "order_first_no_drop",
            "Pending streak age should be prioritized before drops while streaks are unverified",
        )
        self.assertEqual(len(selection), 3)

    def test_completed_streaks_fall_through_to_favorite_priority(self):
        twitch = Twitch("test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="test")
        twitch.watch_streak_cache.mark_bootstrap_done()
        twitch.max_watch_amount = 1
        twitch.max_streak_sessions = 1

        now = 1_700_000_000

        def make_streamer(username: str, *, favorite: bool, online_at: float) -> Streamer:
            settings = StreamerSettings(
                watch_streak=True,
                favorite=favorite,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
            )
            streamer = Streamer(username, settings=settings)
            streamer.channel_points = 100
            streamer.is_online = True
            streamer.online_at = online_at
            streamer.stream.broadcast_id = f"broadcast-{username}"
            streamer.stream.watch_streak_missing = False
            return streamer

        streamers = [
            make_streamer("older_non_favorite", favorite=False, online_at=now - 900),
            make_streamer("newer_favorite", favorite=True, online_at=now - 300),
        ]

        with patch("TwitchChannelPointsMiner.classes.Twitch.time.time", return_value=now):
            selection = twitch._select_streamers_to_watch(
                streamers,
                list(range(len(streamers))),
                [Priority.STREAK, Priority.FAVORITE, Priority.ORDER],
            )

        self.assertEqual(
            [streamers[index].username for index in selection],
            ["newer_favorite"],
        )


if __name__ == "__main__":
    unittest.main()
