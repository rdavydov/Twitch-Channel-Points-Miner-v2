# -*- coding: utf-8 -*-
"""
Copy this file to `run.py` and edit the values below.

Most users only need to change:
- `USERNAME`
- `STREAMERS`
- `FOLLOWERS_ENABLED`
- optionally `PRIORITY_ORDER`

This example is intentionally biased toward a safe first run:
- optional notifications stay disabled
- `PASSWORD = None` uses Twitch's activation-code login and a saved session
- fork-specific streak and export settings are still shown, but kept grouped
"""

import logging
from TwitchChannelPointsMiner import DashboardSettings, TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Settings import Events, FollowersOrder, Priority
from TwitchChannelPointsMiner.classes.entities.Bet import (
    BetSettings,
    Condition,
    DelayMode,
    FilterCondition,
    OutcomeKeys,
    Strategy,
)
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    PlaybackSimulationMode,
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.logger import ColorPalette, LoggerSettings

# ---------------------------------------------------------------------------
# 1. Account
# ---------------------------------------------------------------------------
USERNAME = "your-twitch-username"
PASSWORD = None  # Leave unset; the first login uses a Twitch activation code

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

WATCH_STREAK_MAX_PARALLEL = 2  # max simultaneous streak attempts; capped by Twitch's 2-stream watch limit
WATCH_STREAK_OFFLINE_WAIT_SECONDS = 30 * 60  # 0 = more aggressive checking

# ---------------------------------------------------------------------------
# 4. Logging
# ---------------------------------------------------------------------------
# Optional notifications: uncomment the import and the matching LoggerSettings
# block below, then replace its placeholders. You can enable several providers.
# See the README's Notifications section for obtaining credentials.
# from TwitchChannelPointsMiner.classes.Discord import Discord
# from TwitchChannelPointsMiner.classes.Gotify import Gotify
# from TwitchChannelPointsMiner.classes.Matrix import Matrix
# from TwitchChannelPointsMiner.classes.Pushover import Pushover
# from TwitchChannelPointsMiner.classes.Telegram import Telegram
# from TwitchChannelPointsMiner.classes.Webhook import Webhook

NOTIFICATION_EVENTS = [
    Events.STREAMER_ONLINE,
    Events.SUBSCRIPTION,
    Events.DROP_CLAIM,
    # Events.BET_PLACED,  # Twitch-confirmed bets, including the outcome and stake
    # Events.BET_WIN,
    # Events.BET_LOSE,
    # Events.BET_REFUND,
    # Events.BET_FAILED,
]

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
    # Telegram: bot token from BotFather, numeric destination chat ID.
    # telegram=Telegram(
    #     chat_id=123456789,  # Replace; group IDs are usually negative
    #     token="YOUR_BOT_TOKEN",
    #     events=NOTIFICATION_EVENTS,
    #     disable_notification=False,  # True = deliver silently
    # ),
    # Discord: copy a channel's webhook URL from Server Settings > Integrations.
    # discord=Discord(
    #     webhook_api="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN",
    #     events=NOTIFICATION_EVENTS,
    #     message_format="embed",  # "plain" restores text-only messages
    # ),
    # Gotify: application token, not a client token; include /message in the URL.
    # gotify=Gotify(
    #     endpoint="https://gotify.example.org/message?token=YOUR_APPLICATION_TOKEN",
    #     priority=5,
    #     events=NOTIFICATION_EVENTS,
    # ),
    # Matrix logs in immediately when this block is enabled.
    # Use a password-login account and a room ID, not a #room:server alias.
    # matrix=Matrix(
    #     username="your-matrix-username",
    #     password="YOUR_MATRIX_PASSWORD",
    #     homeserver="matrix.example.org",  # Hostname, without https://
    #     room_id="!YOUR_ROOM_ID:matrix.example.org",
    #     events=NOTIFICATION_EVENTS,
    # ),
    # Pushover: your user key plus the API token for your application.
    # pushover=Pushover(
    #     userkey="YOUR-ACCOUNT-TOKEN",
    #     token="YOUR-APPLICATION-TOKEN",
    #     priority=0,  # Normal priority; emergency priority needs extra API fields
    #     sound="pushover",
    #     events=NOTIFICATION_EVENTS,
    # ),
    # Generic webhook: receives event_name and message as query parameters.
    # webhook=Webhook(
    #     endpoint="https://example.com/webhook",
    #     method="POST",  # GET or POST; this helper does not send a JSON body
    #     events=NOTIFICATION_EVENTS,
    # ),
)

# ---------------------------------------------------------------------------
# 5. Default behavior for all channels
# ---------------------------------------------------------------------------
# These defaults apply to every streamer unless that streamer overrides them.
# `points_limit` skips channels that already have at least that many points.
# Set it to `None` to disable the limit. Pending watch streaks still bypass it.
# `ALWAYS` keeps Twitch HLS playback simulation enabled for Drops/subgift behavior.
DEFAULT_STREAMER_SETTINGS = StreamerSettings(
    make_predictions=True,
    follow_raid=True,
    claim_drops=True,
    claim_moments=True,
    watch_streak=True,
    points_limit=None,
    community_goals=False,
    playback_simulation=PlaybackSimulationMode.ALWAYS,
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
USE_HERMES = True  # False = force the legacy PubSub websocket transport
CLAIM_DROPS_ON_STARTUP = False
ENABLE_ANALYTICS = False
ENABLE_DASHBOARD = False  # Read-only local UI at http://127.0.0.1:5000
DISABLE_SSL_CERT_VERIFICATION = False
MATCH_MENTIONS_WITHOUT_AT = False
DAILY_REPORTS = True
WEEKLY_REPORTS = False
MONTHLY_REPORTS = False
YEARLY_REPORTS = False

twitch_miner = TwitchChannelPointsMiner(
    username=USERNAME,
    password=PASSWORD,
    claim_drops_startup=CLAIM_DROPS_ON_STARTUP,
    priority=PRIORITY_ORDER,
    enable_analytics=ENABLE_ANALYTICS,
    dashboard_settings=DashboardSettings() if ENABLE_DASHBOARD else None,
    disable_ssl_cert_verification=DISABLE_SSL_CERT_VERIFICATION,
    disable_at_in_nickname=MATCH_MENTIONS_WITHOUT_AT,
    use_hermes=USE_HERMES,
    daily_reports=DAILY_REPORTS,
    weekly_reports=WEEKLY_REPORTS,
    monthly_reports=MONTHLY_REPORTS,
    yearly_reports=YEARLY_REPORTS,
    watch_streak_max_parallel=WATCH_STREAK_MAX_PARALLEL,
    watch_streak_min_offline_seconds=WATCH_STREAK_OFFLINE_WAIT_SECONDS,
    logger_settings=LOGGER_SETTINGS,
    streamer_settings=DEFAULT_STREAMER_SETTINGS,
)

# Useful files written under logs/:
# - reports/daily/report_YYYY-MM-DD_<account>.xlsx
# - reports/weekly/weekly_report_YYYY-Www_<account>.xlsx, when WEEKLY_REPORTS=True
# - reports/monthly/monthly_report_Month_YYYY_<account>.xlsx, when MONTHLY_REPORTS=True
# - reports/yearly/yearly_report_YYYY_<account>.xlsx, when YEARLY_REPORTS=True
# - .state/watch_streak_cache.<account>.json
# - .state/daily_points_baseline.<account>.json
# - .state/subscription_notifications.<account>.json
#
# Notifications are configured in LOGGER_SETTINGS before the miner is created.
# Events.SUBSCRIPTION is self-only. IRC notices require chat to be enabled;
# websocket gift-sub notices can arrive without IRC chat presence.

# Settings priority is:
# 1. Settings passed directly in mine(...)
# 2. Settings passed to TwitchChannelPointsMiner(...)
# 3. Default settings

# Optional legacy chart UI; requires ENABLE_ANALYTICS=True and no frontend build.
# Use a different port if ENABLE_DASHBOARD=True.
# twitch_miner.analytics(host="127.0.0.1", port=5001, refresh=5, days_ago=7)

twitch_miner.mine(
    STREAMERS,
    followers=FOLLOWERS_ENABLED,
    followers_order=FOLLOWERS_ORDER,
)
