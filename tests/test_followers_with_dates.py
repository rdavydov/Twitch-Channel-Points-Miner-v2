import unittest
from unittest.mock import patch

from TwitchChannelPointsMiner.classes.Settings import FollowersOrder
from TwitchChannelPointsMiner.classes.Twitch import Twitch


class FollowersWithDatesTest(unittest.TestCase):
    def _follows_page(self, edges, has_next):
        return {
            "data": {
                "user": {
                    "follows": {
                        "edges": edges,
                        "pageInfo": {"hasNextPage": has_next},
                    }
                }
            }
        }

    def test_get_followers_with_dates_parses_edges_and_pagination(self):
        twitch = Twitch("follows-dates-test", "ua")

        page_1 = self._follows_page(
            [
                {
                    "cursor": "cursor-1",
                    "node": {
                        "login": "EasyEmi",
                        "self": {"follower": {"followedAt": "2025-07-21T12:34:56Z"}},
                    },
                },
                {
                    "cursor": "cursor-2",
                    "node": {
                        "login": "dorozea",
                        "self": {"follower": {"followedAt": None}},
                    },
                },
            ],
            has_next=True,
        )
        page_2 = self._follows_page(
            [
                {
                    "cursor": "cursor-3",
                    "node": {
                        "login": "rubia",
                        "self": {},
                    },
                }
            ],
            has_next=False,
        )

        with patch.object(Twitch, "post_gql_request", side_effect=[page_1, page_2]):
            follows = twitch.get_followers_with_dates(order=FollowersOrder.ASC)

        self.assertEqual(
            follows,
            {
                "easyemi": "2025-07-21T12:34:56Z",
                "dorozea": None,
                "rubia": None,
            },
        )

    def test_get_followers_with_dates_returns_partial_on_non_timeout_error(self):
        twitch = Twitch("follows-dates-partial", "ua")

        page_1 = self._follows_page(
            [
                {
                    "cursor": "cursor-1",
                    "node": {
                        "login": "easyemi",
                        "self": {"follower": {"followedAt": "2025-07-21T12:34:56Z"}},
                    },
                }
            ],
            has_next=True,
        )
        timeout_error = {"errors": [{"message": "service timeout"}]}
        generic_error = {"errors": [{"message": "other error"}]}

        with patch.object(
            Twitch,
            "post_gql_request",
            side_effect=[page_1, timeout_error, generic_error],
        ), patch("TwitchChannelPointsMiner.classes.Twitch.time.sleep"):
            follows = twitch.get_followers_with_dates(order=FollowersOrder.ASC)

        self.assertEqual(
            follows,
            {
                "easyemi": "2025-07-21T12:34:56Z",
            },
        )


if __name__ == "__main__":
    unittest.main()
