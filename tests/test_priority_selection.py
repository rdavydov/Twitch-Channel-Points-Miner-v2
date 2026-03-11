import unittest
from unittest.mock import patch

from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.utils import set_default_settings


class PrioritySelectionTest(unittest.TestCase):
    def test_subscribed_lowest_points_takes_first_slot(self):
        twitch = Twitch("self-check", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="self-check")
        priorities = [Priority.STREAK, Priority.SUBSCRIBED, Priority.POINTS_ASCENDING]

        def make_streamer(name, points, subscribed=False, watch_streak=True):
            settings = StreamerSettings(
                watch_streak=watch_streak,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
            )
            streamer = Streamer(name, settings=settings)
            streamer.channel_points = points
            streamer.activeMultipliers = [{"factor": 2.0}] if subscribed else None
            streamer.stream.watch_streak_missing = watch_streak
            return streamer

        streamers = [
            make_streamer("subscribed_low", 10, subscribed=True, watch_streak=True),
            make_streamer("other_low", 100, watch_streak=False),
            make_streamer("other_high", 200, watch_streak=False),
        ]
        streamers_index = list(range(len(streamers)))
        selection = twitch._select_streamers_to_watch(
            streamers, streamers_index, priorities
        )

        self.assertEqual(len(selection), 2)
        self.assertEqual(streamers[selection[0]].username, "subscribed_low")
        self.assertEqual(streamers[selection[1]].username, "other_low")

    def test_selection_skips_streamers_without_points_or_with_chat_ban(self):
        twitch = Twitch("self-check", "ua")
        priorities = [Priority.ORDER]

        def make_streamer(name):
            settings = StreamerSettings(
                watch_streak=False,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
            )
            streamer = Streamer(name, settings=settings)
            streamer.channel_points = 100
            return streamer

        eligible = make_streamer("eligible")
        no_points = make_streamer("no_points")
        no_points.channel_points_enabled = False
        chat_banned = make_streamer("chat_banned")
        chat_banned.chat_banned = True

        streamers = [eligible, no_points, chat_banned]
        selection = twitch._select_streamers_to_watch(
            streamers, [0, 1, 2], priorities
        )

        self.assertEqual(len(selection), 1)
        self.assertEqual(streamers[selection[0]].username, "eligible")

    def test_refresh_selection_context_updates_newly_subscribed_streamer(self):
        twitch = Twitch("self-check", "ua")
        priorities = [Priority.SUBSCRIBED, Priority.POINTS_ASCENDING]

        def make_streamer(name, points, subscribed=False):
            settings = StreamerSettings(
                watch_streak=False,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
            )
            streamer = Streamer(name, settings=settings)
            streamer.channel_points = points
            streamer.activeMultipliers = [{"factor": 2.0}] if subscribed else None
            streamer.is_online = True
            return streamer

        newly_subscribed = make_streamer("newsub", 50, subscribed=False)
        already_subscribed = make_streamer("oldsub", 100, subscribed=True)
        other = make_streamer("other", 10, subscribed=False)
        streamers = [newly_subscribed, already_subscribed, other]

        def refresh_side_effect(_self, streamer):
            if streamer.username == "newsub":
                streamer.activeMultipliers = [{"factor": 2.0}]
                streamer.subscription_tier = 1
            streamer.channel_points_context_at = 999999.0

        with patch.object(
            Twitch,
            "load_channel_points_context",
            autospec=True,
            side_effect=refresh_side_effect,
        ):
            twitch._refresh_selection_context(streamers, [0, 1, 2], priorities)
            selection = twitch._select_streamers_to_watch(
                streamers, [0, 1, 2], priorities
            )

        self.assertEqual(
            [streamers[index].username for index in selection],
            ["newsub", "oldsub"],
        )

    def test_points_limit_skips_capped_streamers_and_allows_per_streamer_override(self):
        twitch = Twitch("limit-test", "ua")
        priorities = [Priority.ORDER]
        default_settings = StreamerSettings(
            watch_streak=False,
            claim_drops=False,
            claim_moments=False,
            make_predictions=False,
            follow_raid=False,
            community_goals=False,
            points_limit=500,
        )

        def make_streamer(name, points, settings=None):
            streamer = Streamer(
                name, settings=set_default_settings(settings, default_settings)
            )
            streamer.channel_points = points
            streamer.is_online = True
            return streamer

        capped_by_default = make_streamer("capped_default", 750)
        allowed_by_override = make_streamer(
            "override_limit",
            750,
            settings=StreamerSettings(points_limit=1000),
        )
        below_limit = make_streamer("below_limit", 400)

        streamers = [capped_by_default, allowed_by_override, below_limit]
        selection = twitch._select_streamers_to_watch(
            streamers, [0, 1, 2], priorities
        )

        self.assertEqual(
            [streamers[index].username for index in selection],
            ["override_limit", "below_limit"],
        )

    def test_points_limit_does_not_block_pending_watch_streak(self):
        twitch = Twitch("limit-streak", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="limit-streak")
        priorities = [Priority.ORDER]

        now = 1_700_000_000
        capped_streak = Streamer(
            "capped_streak",
            settings=StreamerSettings(
                watch_streak=True,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
                points_limit=500,
            ),
        )
        capped_streak.channel_points = 750
        capped_streak.is_online = True
        capped_streak.online_at = now - 300
        capped_streak.stream.broadcast_id = "broadcast-capped-streak"
        capped_streak.stream.watch_streak_missing = True
        twitch.watch_streak_cache.ensure_session(
            capped_streak.username,
            capped_streak.stream.broadcast_id,
            started_at=now - 300,
            account_name=twitch.account_username,
        )

        first_uncapped = Streamer(
            "first_uncapped",
            settings=StreamerSettings(
                watch_streak=False,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
                points_limit=500,
            ),
        )
        first_uncapped.channel_points = 200
        first_uncapped.is_online = True
        first_uncapped.online_at = now - 300
        first_uncapped.stream.broadcast_id = "broadcast-first-uncapped"

        second_uncapped = Streamer(
            "second_uncapped",
            settings=StreamerSettings(
                watch_streak=False,
                claim_drops=False,
                claim_moments=False,
                make_predictions=False,
                follow_raid=False,
                community_goals=False,
                points_limit=500,
            ),
        )
        second_uncapped.channel_points = 250
        second_uncapped.is_online = True
        second_uncapped.online_at = now - 300
        second_uncapped.stream.broadcast_id = "broadcast-second-uncapped"

        with patch("TwitchChannelPointsMiner.classes.Twitch.time.time", return_value=now):
            streamers = [first_uncapped, second_uncapped, capped_streak]
            selection = twitch._select_streamers_to_watch(
                streamers,
                [0, 1, 2],
                priorities,
            )

        selected_usernames = [streamers[index].username for index in selection]
        self.assertEqual(selected_usernames, ["capped_streak", "first_uncapped"])


if __name__ == "__main__":
    unittest.main()
