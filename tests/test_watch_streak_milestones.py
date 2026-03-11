import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from TwitchChannelPointsMiner.WatchStreakCache import WatchStreakCache
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.classes.Twitch import ActiveWatchStreakAttempt, Twitch
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings


class WatchStreakMilestoneTest(unittest.TestCase):
    def _make_streamer(self, username: str) -> Streamer:
        settings = StreamerSettings(
            watch_streak=True,
            claim_drops=False,
            claim_moments=False,
            make_predictions=False,
            follow_raid=False,
            community_goals=False,
        )
        streamer = Streamer(username, settings=settings)
        streamer.channel_id = "123456"
        return streamer

    def _stream_info_payload(
        self,
        broadcast_id: str,
        watch_streak_missing: bool | None = None,
    ) -> dict:
        payload = {
            "stream": {"id": broadcast_id, "tags": [], "viewersCount": 21},
            "broadcastSettings": {"title": "title", "game": {}},
            "chatRoomBanStatus": None,
        }
        if watch_streak_missing is not None:
            payload["watchStreakMissing"] = watch_streak_missing
        return payload

    def test_extract_stream_created_timestamp_handles_null_nodes(self):
        twitch = Twitch("stream-created-null", "ua")
        self.assertIsNone(twitch._extract_stream_created_timestamp({"data": {"user": None}}))
        self.assertIsNone(
            twitch._extract_stream_created_timestamp(
                {"data": {"user": {"stream": None}}}
            )
        )

    def test_is_chat_banned_handles_none_empty_and_ban_payloads(self):
        twitch = Twitch("chat-ban-parse", "ua")

        self.assertFalse(twitch._is_chat_banned(None))
        self.assertFalse(twitch._is_chat_banned({}))
        self.assertFalse(twitch._is_chat_banned({"isBanned": False}))
        self.assertTrue(twitch._is_chat_banned({"isBanned": True}))
        self.assertTrue(
            twitch._is_chat_banned(
                {
                    "createdAt": "2026-03-01T10:00:00Z",
                    "isPermanent": False,
                }
            )
        )

    def test_update_stream_sets_chat_banned_from_chat_room_ban_status(self):
        twitch = Twitch("chat-ban-update", "ua")
        streamer = self._make_streamer("streamer")

        with patch.object(
            Twitch,
            "get_stream_info",
            return_value={
                "stream": {
                    "id": "broadcast-ban-1",
                    "tags": [],
                    "viewersCount": 21,
                    "createdAt": "2026-03-01T10:00:00Z",
                },
                "broadcastSettings": {"title": "title", "game": {}},
                "chatRoomBanStatus": {
                    "createdAt": "2026-03-01T10:05:00Z",
                    "isPermanent": False,
                },
            },
        ):
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        self.assertTrue(streamer.chat_banned)

    def test_update_stream_does_not_mark_empty_chat_room_ban_status_as_banned(self):
        twitch = Twitch("chat-ban-empty-status", "ua")
        streamer = self._make_streamer("streamer")

        with patch.object(
            Twitch,
            "get_stream_info",
            return_value={
                "stream": {
                    "id": "broadcast-ban-2",
                    "tags": [],
                    "viewersCount": 21,
                    "createdAt": "2026-03-01T10:00:00Z",
                },
                "broadcastSettings": {"title": "title", "game": {}},
                "chatRoomBanStatus": {},
            },
        ):
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        self.assertFalse(streamer.chat_banned)

    def test_get_chat_ban_status_returns_false_when_twitch_reports_null(self):
        twitch = Twitch("chat-ban-direct-null", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "ChatRoomBanStatus": {
                "data": {
                    "chatRoomBanStatus": None,
                    "targetUser": {
                        "id": "261663741",
                        "login": "armi1014",
                        "__typename": "User",
                    },
                }
            }
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(
            type(twitch.twitch_login),
            "get_user_id",
            return_value="261663741",
        ), patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            chat_banned = twitch.get_chat_ban_status(streamer)

        self.assertFalse(chat_banned)

    def test_get_chat_ban_status_returns_true_when_twitch_reports_ban(self):
        twitch = Twitch("chat-ban-direct-hit", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "ChatRoomBanStatus": {
                "data": {
                    "chatRoomBanStatus": {
                        "createdAt": "2026-03-06T19:08:21.925400515Z",
                        "isPermanent": False,
                    },
                    "targetUser": {
                        "id": "261663741",
                        "login": "armi1014",
                        "__typename": "User",
                    },
                }
            }
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(
            type(twitch.twitch_login),
            "get_user_id",
            return_value="261663741",
        ), patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            chat_banned = twitch.get_chat_ban_status(streamer)

        self.assertTrue(chat_banned)

    def test_get_stream_info_marks_streak_complete_from_milestone_timestamp(self):
        twitch = Twitch("milestone-test", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-1",
                            "tags": [],
                            "viewersCount": 42,
                        },
                        "broadcastSettings": {"title": "title", "game": {}},
                    }
                }
            },
            "WithIsStreamLiveQuery": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-1",
                            "createdAt": "2026-03-01T10:00:00Z",
                        }
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "achievementTimestamp": "2026-03-01T10:06:00Z"
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            stream_info = twitch.get_stream_info(streamer)

        self.assertIsNotNone(stream_info)
        self.assertIn("createdAt", stream_info["stream"])
        self.assertFalse(stream_info.get("watchStreakMissing", True))

    def test_get_stream_info_extracts_watch_streak_days(self):
        twitch = Twitch("milestone-days-test", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-days-1",
                            "tags": [],
                            "viewersCount": 42,
                            "createdAt": "2026-03-01T10:00:00Z",
                        }
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "watchStreakDays": 26,
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            stream_info = twitch.get_stream_info(streamer)

        self.assertIsNotNone(stream_info)
        self.assertEqual(stream_info.get("watchStreakDays"), 26)

    def test_get_stream_info_extracts_watch_streak_days_from_real_reward_list_value(self):
        twitch = Twitch("milestone-days-real-shape", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-days-real-1",
                            "tags": [],
                            "viewersCount": 42,
                            "createdAt": "2026-03-01T10:00:00Z",
                        }
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "id": "2506435d-cabb-4586-b1fc-5a7b17879811",
                                    "value": "1",
                                    "category": "WATCH_STREAK",
                                    "achievementTimestamp": "2026-03-06T19:08:21.925400515Z",
                                    "shareStatus": "CAN_NOT_SHARE",
                                    "__typename": "ViewerMilestone",
                                },
                                "watchStreakThreshold": 3,
                                "watchStreakCopoBonus": 350,
                                "state": "ACTIVE",
                                "missedStreams": None,
                                "expiresAt": None,
                                "__typename": "WatchStreakMilestone",
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            stream_info = twitch.get_stream_info(streamer)

        self.assertIsNotNone(stream_info)
        self.assertEqual(stream_info.get("watchStreakDays"), 1)

    def test_get_watch_streak_days_queries_reward_list(self):
        twitch = Twitch("milestone-days-direct", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "watchStreakDays": 19,
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            days = twitch.get_watch_streak_days(streamer)

        self.assertEqual(days, 19)

    def test_get_watch_streak_days_queries_reward_list_real_shape(self):
        twitch = Twitch("milestone-days-direct-real-shape", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "value": "1",
                                    "category": "WATCH_STREAK",
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            days = twitch.get_watch_streak_days(streamer)

        self.assertEqual(days, 1)

    def test_extract_watch_streak_days_prefers_watch_streak_days_field(self):
        twitch = Twitch("milestone-days-priority", "ua")
        response = {
            "data": {
                "channel": {
                    "self": {
                        "watchStreakMilestone": {
                            "watchStreakMilestone": {
                                "currentDay": 3,
                                "watchStreakDays": 26,
                                "dayCount": 7,
                            }
                        }
                    }
                }
            }
        }

        self.assertEqual(twitch._extract_watch_streak_days(response), 26)

    def test_get_stream_info_handles_null_reward_list_channel_without_crashing(self):
        twitch = Twitch("milestone-null-channel", "ua")
        streamer = self._make_streamer("streamer")

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-null-1",
                            "tags": [],
                            "viewersCount": 12,
                        },
                        "broadcastSettings": {"title": "title", "game": {}},
                    }
                }
            },
            "WithIsStreamLiveQuery": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-null-1",
                            "createdAt": "2026-03-01T10:00:00Z",
                        }
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": None,
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            stream_info = twitch.get_stream_info(streamer)

        self.assertIsNotNone(stream_info)
        self.assertNotIn("watchStreakMissing", stream_info)

    def test_update_stream_marks_cache_claimed_when_milestone_indicates_completed(self):
        twitch = Twitch("milestone-claim", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="milestone-claim")
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-claim-1",
                            "tags": [],
                            "viewersCount": 21,
                        },
                        "broadcastSettings": {"title": "title", "game": {}},
                    }
                }
            },
            "WithIsStreamLiveQuery": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-claim-1",
                            "createdAt": "2026-03-01T10:00:00Z",
                        }
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "achievementTimestamp": "2026-03-01T10:07:00Z"
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        session = twitch.watch_streak_cache.get_session(
            streamer.username,
            "broadcast-claim-1",
            account_name=twitch.account_username,
        )
        self.assertIsNotNone(session)
        self.assertTrue(session.claimed)
        self.assertFalse(streamer.stream.watch_streak_missing)

    def test_update_stream_persists_watch_streak_days_in_status_cache(self):
        twitch = Twitch("milestone-days-cache", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="milestone-days-cache")
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-days-cache-1",
                            "tags": [],
                            "viewersCount": 21,
                            "createdAt": "2026-03-01T10:00:00Z",
                        },
                        "broadcastSettings": {"title": "title", "game": {}},
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "watchStreakDays": 31,
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post):
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        status = twitch.watch_streak_cache.get_streamer_status(
            streamer.username,
            account_name=twitch.account_username,
        )
        self.assertIsNotNone(status)
        self.assertEqual(status.watch_streak_days, 31)

    def test_update_stream_logs_detected_watch_streak_even_for_preclaimed_session(self):
        twitch = Twitch("milestone-preclaimed", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="milestone-preclaimed")
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)

        now = time.time()
        session = twitch.watch_streak_cache.ensure_session(
            streamer.username,
            "broadcast-preclaimed-1",
            started_at=now - 300,
            account_name=twitch.account_username,
        )
        twitch.watch_streak_cache.mark_claimed(
            streamer.username,
            broadcast_id="broadcast-preclaimed-1",
            now=now - 120,
            account_name=twitch.account_username,
        )

        responses = {
            "VideoPlayerStreamInfoOverlayChannel": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-preclaimed-1",
                            "tags": [],
                            "viewersCount": 21,
                        },
                        "broadcastSettings": {"title": "title", "game": {}},
                    }
                }
            },
            "WithIsStreamLiveQuery": {
                "data": {
                    "user": {
                        "stream": {
                            "id": "broadcast-preclaimed-1",
                            "createdAt": "2026-03-01T10:00:00Z",
                        }
                    }
                }
            },
            "RewardList": {
                "data": {
                    "channel": {
                        "self": {
                            "watchStreakMilestone": {
                                "watchStreakMilestone": {
                                    "achievementTimestamp": "2026-03-01T10:07:00Z"
                                }
                            }
                        }
                    }
                }
            },
        }

        def fake_post(json_data):
            return responses.get(json_data.get("operationName"), {})

        with patch.object(Twitch, "post_gql_request", side_effect=fake_post), patch(
            "TwitchChannelPointsMiner.classes.Twitch.logger.info"
        ) as mocked_info:
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        self.assertTrue(session.claimed)
        self.assertFalse(streamer.stream.watch_streak_missing)
        mocked_info.assert_called_once()
        self.assertIn("Detected WATCH_STREAK for %s", mocked_info.call_args[0][0])

    def test_update_stream_startup_probe_logs_detected_when_already_marked(self):
        twitch = Twitch("milestone-startup-probe", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="milestone-startup-probe")
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)

        now = time.time()
        streamer.stream.broadcast_id = "broadcast-startup-probe-1"
        streamer.stream.watch_streak_missing = False

        twitch.watch_streak_cache.ensure_session(
            streamer.username,
            "broadcast-startup-probe-1",
            started_at=now - 300,
            account_name=twitch.account_username,
        )
        twitch.watch_streak_cache.mark_claimed(
            streamer.username,
            broadcast_id="broadcast-startup-probe-1",
            now=now - 120,
            account_name=twitch.account_username,
        )

        with patch.object(
            Twitch,
            "get_stream_info",
            return_value=self._stream_info_payload(
                "broadcast-startup-probe-1",
                watch_streak_missing=False,
            ),
        ), patch("TwitchChannelPointsMiner.classes.Twitch.logger.info") as mocked_info:
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        mocked_info.assert_called_once()
        self.assertIn("Detected WATCH_STREAK for %s", mocked_info.call_args[0][0])

    def test_update_stream_startup_probe_skips_detected_log_when_reward_seen(self):
        twitch = Twitch("milestone-startup-no-duplicate", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="milestone-startup-no-duplicate")
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)

        now = time.time()
        streamer.stream.broadcast_id = "broadcast-startup-no-duplicate-1"
        streamer.stream.watch_streak_missing = False
        streamer.history["WATCH_STREAK"] = {"counter": 1, "amount": 450}

        twitch.watch_streak_cache.ensure_session(
            streamer.username,
            "broadcast-startup-no-duplicate-1",
            started_at=now - 300,
            account_name=twitch.account_username,
        )
        twitch.watch_streak_cache.mark_claimed(
            streamer.username,
            broadcast_id="broadcast-startup-no-duplicate-1",
            now=now - 120,
            account_name=twitch.account_username,
        )

        with patch.object(
            Twitch,
            "get_stream_info",
            return_value=self._stream_info_payload(
                "broadcast-startup-no-duplicate-1",
                watch_streak_missing=False,
            ),
        ), patch("TwitchChannelPointsMiner.classes.Twitch.logger.info") as mocked_info:
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        mocked_info.assert_not_called()

    def test_update_stream_runtime_does_not_relog_detected_streak(self):
        twitch = Twitch("milestone-runtime-no-relog", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="milestone-runtime-no-relog")
        twitch.watch_streak_cache.mark_bootstrap_done()
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)

        now = time.time()
        streamer.stream.broadcast_id = "broadcast-runtime-no-relog-1"
        streamer.stream.watch_streak_missing = False

        twitch.watch_streak_cache.ensure_session(
            streamer.username,
            "broadcast-runtime-no-relog-1",
            started_at=now - 300,
            account_name=twitch.account_username,
        )
        twitch.watch_streak_cache.mark_claimed(
            streamer.username,
            broadcast_id="broadcast-runtime-no-relog-1",
            now=now - 120,
            account_name=twitch.account_username,
        )

        with patch.object(
            Twitch,
            "get_stream_info",
            return_value=self._stream_info_payload(
                "broadcast-runtime-no-relog-1",
                watch_streak_missing=False,
            ),
        ), patch("TwitchChannelPointsMiner.classes.Twitch.logger.info") as mocked_info:
            updated = twitch.update_stream(streamer)

        self.assertTrue(updated)
        mocked_info.assert_not_called()

    def test_cleanup_ends_attempt_after_two_watch_events(self):
        twitch = Twitch("watch-events-test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="watch-events-test")
        streamer = self._make_streamer("streamer")
        streamer.is_online = True
        streamer.online_at = time.time() - 60
        streamer.stream.broadcast_id = "broadcast-2"
        streamer.stream.watch_streak_missing = True
        streamer.history["WATCH"] = {"counter": 2, "amount": 20}

        now = time.time()
        session = twitch.watch_streak_cache.ensure_session(
            streamer.username,
            streamer.stream.broadcast_id,
            started_at=now - 60,
            account_name=twitch.account_username,
        )
        twitch._active_streak_attempts[session.key()] = ActiveWatchStreakAttempt(
            session_key=session.key(),
            streamer=streamer.username,
            broadcast_id=streamer.stream.broadcast_id,
            started_at=now - 30,
            watch_counter_at_start=0,
        )

        twitch._cleanup_streak_attempts([streamer], now)

        self.assertFalse(streamer.stream.watch_streak_missing)
        self.assertEqual(twitch._active_streak_attempts, {})
        updated = twitch.watch_streak_cache.get_session(
            streamer.username,
            streamer.stream.broadcast_id,
            account_name=twitch.account_username,
        )
        self.assertIsNotNone(updated)
        self.assertIsNotNone(updated.ended_at)

    def test_streak_selection_rotates_candidates_when_many_are_eligible(self):
        twitch = Twitch("rotation-test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="rotation-test")
        twitch.max_streak_sessions = 2
        twitch.max_watch_amount = 2

        now = time.time()
        streamers = []
        for i in range(4):
            streamer = self._make_streamer(f"streamer{i}")
            streamer.is_online = True
            streamer.online_at = now - 120
            streamer.stream.broadcast_id = f"broadcast-{i}"
            streamer.stream.watch_streak_missing = True
            twitch.watch_streak_cache.ensure_session(
                streamer.username,
                streamer.stream.broadcast_id,
                started_at=now - 120,
                account_name=twitch.account_username,
            )
            streamers.append(streamer)

        first = twitch._select_streak_streamers(
            streamers,
            list(range(len(streamers))),
            [Priority.STREAK],
            now,
        )
        twitch._active_streak_attempts = {}
        second = twitch._select_streak_streamers(
            streamers,
            list(range(len(streamers))),
            [Priority.STREAK],
            now + 1,
        )

        first_names = [streamers[i].username for i in first]
        second_names = [streamers[i].username for i in second]
        self.assertEqual(len(first_names), 2)
        self.assertEqual(len(second_names), 2)
        self.assertNotEqual(first_names, second_names)
        self.assertGreaterEqual(len(set(first_names + second_names)), 3)

    def test_streak_selection_bootstrap_creates_session_for_online_streamer(self):
        twitch = Twitch("startup-probe-test", "ua")
        twitch.watch_streak_cache = WatchStreakCache(default_account_name="startup-probe-test")
        twitch.watch_streak_cache.mark_bootstrap_done()
        twitch.max_streak_sessions = 1
        twitch.max_watch_amount = 1

        now = time.time()
        streamer = self._make_streamer("streamer")
        streamer.is_online = True
        streamer.online_at = now - 1200
        streamer.stream.broadcast_id = "startup-broadcast-1"
        streamer.stream.created_at = now - 1200
        streamer.stream.watch_streak_missing = True

        selection = twitch._select_streak_streamers(
            [streamer],
            [0],
            [Priority.STREAK],
            now,
        )

        self.assertEqual(selection, [0])
        session = twitch.watch_streak_cache.get_session(
            streamer.username,
            streamer.stream.broadcast_id,
            account_name=twitch.account_username,
        )
        self.assertIsNotNone(session)
        self.assertFalse(session.claimed)

    def test_set_online_does_not_reset_detected_streak_state(self):
        streamer = self._make_streamer("streamer")
        Settings.logger = SimpleNamespace(less=True)
        streamer.is_online = False
        streamer.stream.broadcast_id = "broadcast-state-1"
        streamer.stream.watch_streak_missing = False

        streamer.set_online()

        self.assertTrue(streamer.is_online)
        self.assertFalse(streamer.stream.watch_streak_missing)

    def test_streak_start_is_not_logged(self):
        twitch = Twitch("streak-log-start", "ua")
        cache = WatchStreakCache(default_account_name="streak-log-start")
        session = cache.ensure_session(
            "streamer",
            "broadcast-log-1",
            started_at=time.time(),
            account_name="streak-log-start",
        )

        with patch("TwitchChannelPointsMiner.classes.Twitch.logger.info") as mocked_info:
            twitch._log_streak_start(session)

        mocked_info.assert_not_called()

    def test_streak_claimed_logs_once_per_session(self):
        twitch = Twitch("streak-log-claimed", "ua")
        cache = WatchStreakCache(default_account_name="streak-log-claimed")
        session = cache.ensure_session(
            "streamer",
            "broadcast-log-2",
            started_at=time.time(),
            account_name="streak-log-claimed",
        )

        with patch("TwitchChannelPointsMiner.classes.Twitch.logger.info") as mocked_info:
            twitch._log_streak_claimed(session)
            twitch._log_streak_claimed(session)

        mocked_info.assert_called_once()
        self.assertIn("Detected WATCH_STREAK for %s", mocked_info.call_args[0][0])

    def test_streak_failed_logs_once_per_session(self):
        twitch = Twitch("streak-log-failed", "ua")
        cache = WatchStreakCache(default_account_name="streak-log-failed")
        session = cache.ensure_session(
            "streamer",
            "broadcast-log-3",
            started_at=time.time(),
            account_name="streak-log-failed",
        )
        session.attempts = 2

        with patch("TwitchChannelPointsMiner.classes.Twitch.logger.info") as mocked_info:
            twitch._log_streak_failed(session)
            twitch._log_streak_failed(session)

        mocked_info.assert_called_once()
        self.assertIn("[STREAK] Exhausted for %s after %d attempts", mocked_info.call_args[0][0])
        self.assertIsNone(session.ended_at)


if __name__ == "__main__":
    unittest.main()
