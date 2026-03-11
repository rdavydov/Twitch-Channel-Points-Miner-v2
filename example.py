# -*- coding: utf-8 -*-
"""
Copy this file to `run.py` and edit the values below.

Most users only need to change:
- `USERNAME`
- `PASSWORD`
- `STREAMERS`
- `FOLLOWERS_ENABLED`
- optionally `PRIORITY_ORDER`

This example is intentionally biased toward a safe first run:
- optional notifications stay disabled
- `PASSWORD = None` prompts at startup instead of storing it in the file
- fork-specific streak and export settings are still shown, but kept grouped
"""

import logging
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Settings import FollowersOrder, Priority
from TwitchChannelPointsMiner.classes.entities.Bet import (
    BetSettings,
    Condition,
    DelayMode,
    FilterCondition,
    OutcomeKeys,
    Strategy,
)
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.logger import ColorPalette, LoggerSettings

# ---------------------------------------------------------------------------
# 1. Account
# ---------------------------------------------------------------------------
USERNAME = "your-twitch-username"
PASSWORD = None  # None = prompt at startup instead of storing your password here

# ---------------------------------------------------------------------------
# 2. What the miner should watch
# ---------------------------------------------------------------------------
# Set this to True if you want the miner to download your followed channels too.
FOLLOWERS_ENABLED = False
FOLLOWERS_ORDER = FollowersOrder.ASC  # ASC = oldest follows first, DESC = newest first

# Quickest possible setup:
# STREAMERS = ["your_main_streamer"]
#
# You can also mix plain usernames and Streamer(...) objects.
# Use StreamerSettings(...) only when one channel needs special behavior.
STREAMERS = [
    "your_main_streamer",
    # Favorite channel: only matters if Priority.FAVORITE is enabled below.
    Streamer(
        "favorite_streamer",
        settings=StreamerSettings(
            favorite=True,
            watch_streak=True,
        ),
    ),
]

# Optional per-streamer examples you can copy into STREAMERS:
#
# Streamer(
#     "streak_streamer",
#     settings=StreamerSettings(watch_streak=True),
# )
#
# Streamer(
#     "quiet_streamer",
#     settings=StreamerSettings(
#         chat=ChatPresence.NEVER,
#         claim_drops=False,
#     ),
# )
#
# Streamer(
#     "high_cap_streamer",
#     settings=StreamerSettings(
#         points_limit=150000,  # Override the global limit for just this channel
#     ),
# )
#
# Streamer(
#     "prediction_streamer",
#     settings=StreamerSettings(
#         follow_raid=False,
#         watch_streak=False,
#         bet=BetSettings(
#             strategy=Strategy.HIGH_ODDS,
#             percentage=7,
#             max_points=2500,
#             minimum_points=5000,
#             stealth_mode=True,
#             delay_mode=DelayMode.FROM_END,
#             delay=6,
#             filter_condition=FilterCondition(
#                 by=OutcomeKeys.PERCENTAGE_USERS,
#                 where=Condition.GTE,
#                 value=300,
#             ),
#         ),
#     ),
# )

# ---------------------------------------------------------------------------
# 3. Channel priority and streak behavior
# ---------------------------------------------------------------------------
# Twitch only awards points on up to 2 streams at the same time.
# The priority list decides which channels win when more are live.
PRIORITY_ORDER = [
    Priority.STREAK,    # Try to catch watch streaks first
    Priority.FAVORITE,  # Then prefer channels with favorite=True
    Priority.DROPS,     # Then finish active drops
    Priority.ORDER,     # Then follow the order from STREAMERS above
]

WATCH_STREAK_MAX_PARALLEL = 2
WATCH_STREAK_OFFLINE_WAIT_SECONDS = 30 * 60  # 0 = more aggressive checking

# ---------------------------------------------------------------------------
# 4. Logging
# ---------------------------------------------------------------------------
LOGGER_SETTINGS = LoggerSettings(
    save=True,                   # Write logs to logs/
    console_level=logging.INFO,  # Change to logging.DEBUG when troubleshooting
    file_level=logging.DEBUG,    # Keep file logs detailed
    console_username=False,      # True can help if you run multiple accounts
    auto_clear=True,             # Rotate logs daily and keep the last 7 files
    less=False,                  # True = quieter console
    colored=True,
    color_palette=ColorPalette(
        STREAMER_ONLINE="GREEN",
        STREAMER_OFFLINE="RED",
        BET_WIN="MAGENTA",
    ),
)

# ---------------------------------------------------------------------------
# 5. Default behavior for all channels
# ---------------------------------------------------------------------------
# These defaults apply to every streamer unless that streamer overrides them.
# `points_limit` skips channels that already have at least that many points.
# Set it to `None` to disable the limit. Pending watch streaks still bypass it.
DEFAULT_STREAMER_SETTINGS = StreamerSettings(
    make_predictions=True,
    follow_raid=True,
    claim_drops=True,
    claim_moments=True,
    watch_streak=True,
    points_limit=None,
    community_goals=False,
    chat=ChatPresence.ONLINE,
    bet=BetSettings(
        strategy=Strategy.SMART,
        percentage=5,
        percentage_gap=20,
        max_points=50000,
        minimum_points=20000,
        stealth_mode=True,
        delay_mode=DelayMode.FROM_END,
        delay=6,
        filter_condition=FilterCondition(
            by=OutcomeKeys.TOTAL_USERS,
            where=Condition.LTE,
            value=800,
        ),
    ),
)

# ---------------------------------------------------------------------------
# 6. Miner startup
# ---------------------------------------------------------------------------
CLAIM_DROPS_ON_STARTUP = False
ENABLE_ANALYTICS = False
DISABLE_SSL_CERT_VERIFICATION = False
MATCH_MENTIONS_WITHOUT_AT = False

twitch_miner = TwitchChannelPointsMiner(
    username=USERNAME,
    password=PASSWORD,
    claim_drops_startup=CLAIM_DROPS_ON_STARTUP,
    priority=PRIORITY_ORDER,
    enable_analytics=ENABLE_ANALYTICS,
    disable_ssl_cert_verification=DISABLE_SSL_CERT_VERIFICATION,
    disable_at_in_nickname=MATCH_MENTIONS_WITHOUT_AT,
    watch_streak_max_parallel=WATCH_STREAK_MAX_PARALLEL,
    watch_streak_min_offline_seconds=WATCH_STREAK_OFFLINE_WAIT_SECONDS,
    logger_settings=LOGGER_SETTINGS,
    streamer_settings=DEFAULT_STREAMER_SETTINGS,
)

# Useful files written under logs/:
# - report_YYYY-MM-DD_<account>.xlsx
# - watch_streak_cache.<account>.json
# - daily_points_baseline.<account>.json
#
# Optional notifications:
# Keep these disabled until you have real credentials. Matrix logs in during
# startup, and webhook-style integrations will try to send requests when events happen.
#
# Example imports if you want to enable them:
# from TwitchChannelPointsMiner.classes.Discord import Discord
# from TwitchChannelPointsMiner.classes.Gotify import Gotify
# from TwitchChannelPointsMiner.classes.Matrix import Matrix
# from TwitchChannelPointsMiner.classes.Pushover import Pushover
# from TwitchChannelPointsMiner.classes.Settings import Events
# from TwitchChannelPointsMiner.classes.Telegram import Telegram
# from TwitchChannelPointsMiner.classes.Webhook import Webhook
#
# Example events list:
# [
#     Events.STREAMER_ONLINE,
#     Events.STREAMER_OFFLINE,
#     Events.SUBSCRIPTION,
#     Events.BET_LOSE,
#     Events.CHAT_MENTION,
# ]
#
# Minimal Discord example:
# LOGGER_SETTINGS = LoggerSettings(
#     ...,
#     discord=Discord(
#         webhook_api="https://discord.com/api/webhooks/...",
#         events=[Events.SUBSCRIPTION],
#     ),
# )
#
# `Events.SUBSCRIPTION` comes from Twitch IRC `USERNOTICE` messages, so the
# streamer's chat setting must not be `ChatPresence.NEVER`.
# It is self-only: it alerts when your account gets a sub/resub/subgift/upgrade,
# and ignores other viewers' subscription events.

# Settings priority is:
# 1. Settings passed directly in mine(...)
# 2. Settings passed to TwitchChannelPointsMiner(...)
# 3. Default settings

# twitch_miner.analytics(host="127.0.0.1", port=5000, refresh=5, days_ago=7)

twitch_miner.mine(
    STREAMERS,
    followers=FOLLOWERS_ENABLED,
    followers_order=FOLLOWERS_ORDER,
)
