# -*- coding: utf-8 -*-

import logging, os
from colorama import Fore
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.Webhook import Webhook
from TwitchChannelPointsMiner.classes.Telegram import Telegram
from TwitchChannelPointsMiner.classes.Matrix import Matrix
from TwitchChannelPointsMiner.classes.Pushover import Pushover
from TwitchChannelPointsMiner.classes.Gotify import Gotify
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

telegram = None
discord = None
webhook = None
matrix = None
pushover = None
gotify = None

# Telegram
chat_id = os.environ.get("TELEGRAM_CHAT_ID")
token = os.environ.get("TELEGRAM_TOKEN")
if chat_id and token:
    telegram = Telegram(
        chat_id=int(chat_id),
        token=token,
        events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                Events.BET_LOSE, Events.CHAT_MENTION],
        disable_notification=True,
    )
    
# Discord
discord_webhook = os.environ.get("DISCORD_WEBHOOK_API")
if discord_webhook:
    discord = Discord(
        webhook_api=discord_webhook,
        events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                Events.BET_LOSE, Events.CHAT_MENTION],
    )

# Webhook
webhook_endpoint = os.environ.get("WEBHOOK_ENDPOINT")
webhook_method = os.environ.get("WEBHOOK_METHOD", "GET")
if webhook_endpoint:
    webhook = Webhook(
        endpoint=webhook_endpoint,
        method=webhook_method,
        events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                Events.BET_LOSE, Events.CHAT_MENTION],
    )

# Matrix
matrix_username = os.environ.get("MATRIX_USERNAME")
matrix_password = os.environ.get("MATRIX_PASSWORD")
matrix_homeserver = os.environ.get("MATRIX_HOMESERVER", "matrix.org")
matrix_room_id = os.environ.get("MATRIX_ROOM_ID")
if matrix_username and matrix_password and matrix_room_id:
    matrix = Matrix(
        username=matrix_username,
        password=matrix_password,
        homeserver=matrix_homeserver,
        room_id=matrix_room_id,
        events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE, Events.BET_LOSE],
    )

# Pushover
pushover_userkey = os.environ.get("PUSHOVER_USERKEY")
pushover_token = os.environ.get("PUSHOVER_TOKEN")
if pushover_userkey and pushover_token:
    pushover = Pushover(
        userkey=pushover_userkey,
        token=pushover_token,
        priority=0,
        sound="pushover",
        events=[Events.CHAT_MENTION, Events.DROP_CLAIM],
    )

# Gotify
gotify_endpoint = os.environ.get("GOTIFY_ENDPOINT")
gotify_priority = int(os.environ.get("GOTIFY_PRIORITY", 8))
if gotify_endpoint:
    gotify = Gotify(
        endpoint=gotify_endpoint,
        priority=gotify_priority,
        events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                Events.BET_LOSE, Events.CHAT_MENTION],
    )

# Handle BetSettings or disable it entirely via env
bet_disabled = os.environ.get("BET_DISABLED", "False") == "True"
bet_settings = None

if not bet_disabled:
    bet_settings = BetSettings(
        strategy=Strategy[os.environ.get("BET_STRATEGY", "SMART")],
        percentage=int(os.environ.get("BET_PERCENTAGE", 5)),
        percentage_gap=int(os.environ.get("BET_PERCENTAGE_GAP", 20)),
        max_points=int(os.environ.get("BET_MAX_POINTS", 50000)),
        minimum_points=int(os.environ.get("BET_MIN_POINTS", 20000)),
        stealth_mode=os.environ.get("BET_STEALTH_MODE", "True") == "True",
        delay=float(os.environ.get("BET_DELAY", 6)),
        delay_mode=DelayMode[os.environ.get("BET_DELAY_MODE", "FROM_END")],
        filter_condition=FilterCondition(
            by=getattr(OutcomeKeys, os.environ.get("FILTER_BY", "TOTAL_USERS")),
            where=Condition[os.environ.get("FILTER_WHERE", "LTE")],
            value=int(os.environ.get("FILTER_VALUE", 800))
        )
    )

streamer_settings = StreamerSettings(
    make_predictions=os.environ.get("MAKE_PREDICTIONS", "True") == "True",
    follow_raid=os.environ.get("FOLLOW_RAID", "True") == "True",
    claim_drops=os.environ.get("CLAIM_DROPS", "True") == "True",
    claim_moments=os.environ.get("CLAIM_MOMENTS", "True") == "True",
    watch_streak=os.environ.get("WATCH_STREAK", "True") == "True",
    community_goals=os.environ.get("COMMUNITY_GOALS", "False") == "True",
    chat=ChatPresence[os.environ.get("CHAT_PRESENCE", "ONLINE")],
    bet=bet_settings
)


twitch_miner = TwitchChannelPointsMiner(
    username=os.environ.get("TWITCH_USERNAME"),
    password=os.environ.get("TWITCH_PASSWORD"), # Optional: if missing, it will ask interactively
    claim_drops_startup=os.environ.get("CLAIM_DROPS_STARTUP", "False") == "True",
    priority=[
        Priority[os.environ.get("PRIORITY_1", "STREAK")],
        Priority[os.environ.get("PRIORITY_2", "DROPS")],
        Priority[os.environ.get("PRIORITY_3", "ORDER")],
    ],
    enable_analytics=os.environ.get("ENABLE_ANALYTICS", "False") == "True",
    disable_ssl_cert_verification=os.environ.get("DISABLE_SSL_VERIFY", "False") == "True",
    disable_at_in_nickname=os.environ.get("DISABLE_AT_IN_NICKNAME", "False") == "True",
    logger_settings=LoggerSettings(
        save=os.environ.get("LOG_SAVE", "True") == "True",
        console_level=getattr(logging, os.environ.get("LOG_CONSOLE_LEVEL", "INFO")),
        console_username=os.environ.get("LOG_CONSOLE_USERNAME", "False") == "True",
        auto_clear=os.environ.get("LOG_AUTO_CLEAR", "True") == "True",
        time_zone=os.environ.get("LOG_TIMEZONE", ""),
        file_level=getattr(logging, os.environ.get("LOG_FILE_LEVEL", "DEBUG")),
        emoji=os.environ.get("LOG_EMOJI", "True") == "True",
        less=os.environ.get("LOG_LESS", "False") == "True",
        colored=os.environ.get("LOG_COLORED", "True") == "True",
        color_palette=ColorPalette(
            STREAMER_online=os.environ.get("COLOR_ONLINE", "GREEN"),
            streamer_offline=os.environ.get("COLOR_OFFLINE", "RED"),
            BET_wiN=getattr(Fore, os.environ.get("COLOR_BET_WIN", "MAGENTA"))
        ),
        telegram=telegram,
        discord=discord,
        webhook=webhook,
        matrix=matrix,
        pushover=pushover,
        gotify=gotify
    ),
    streamer_settings=streamer_settings
)

if os.environ.get("ENABLE_ANALYTICS", "False") == "True":
    twitch_miner.analytics(host="127.0.0.1", port=5000, refresh=5, days_ago=7)

# Load streamers from env
streamer_usernames = os.environ.get("STREAMERS", "")
streamers = [s.strip() for s in streamer_usernames.split(",") if s.strip()]

twitch_miner.mine(
    streamers,                               # Streamer list (as strings, use global settings)
    followers=False,                         # Disable auto-follow mining
    followers_order=FollowersOrder.ASC       # Sort followers (if used)
)
