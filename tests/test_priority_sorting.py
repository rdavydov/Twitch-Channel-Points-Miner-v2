import time
import unittest

from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache


class PrioritySortingTest(unittest.TestCase):
    def test_streak_then_drops_respects_order(self):
        twitch = Twitch("test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="test")
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
            "order_second_with_drop",
            "Drop-enabled streamer should be prioritized ahead of manual order when streak ties",
        )
        self.assertEqual(len(selection), 3)


if __name__ == "__main__":
    unittest.main()
