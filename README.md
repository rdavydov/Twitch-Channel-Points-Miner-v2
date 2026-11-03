# Twitch Channel Points Miner v2

![Twitch Channel Points Miner - v2](https://raw.githubusercontent.com/rdavydov/Twitch-Channel-Points-Miner-v2/master/assets/banner.png)

<p align="center">
<a href="https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/releases"><img alt="Latest Version" src="https://img.shields.io/github/v/release/rdavydov/Twitch-Channel-Points-Miner-v2?style=flat&color=white&logo=github&logoColor=white"></a>
<a href="https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/stargazers"><img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/rdavydov/Twitch-Channel-Points-Miner-v2?style=flat&color=limegreen&logo=github&logoColor=white"></a>
<a href='https://github.com/MShawon/github-clone-count-badge'><img alt='GitHub Traffic' src='https://img.shields.io/badge/dynamic/json?style=flat&color=blue&label=views&query=count&url=https://gist.githubusercontent.com/rdavydov/ad9a3c6a8d9c322f9a6b62781ea94a93/raw/traffic.json&logo=github&logoColor=white'></a>
<a href='https://github.com/MShawon/github-clone-count-badge'><img alt='GitHub Clones' src='https://img.shields.io/badge/dynamic/json?style=flat&color=purple&label=clones&query=count&url=https://gist.githubusercontent.com/rdavydov/fed04b31a250ad522d9ea6547ce87f95/raw/clone.json&logo=github&logoColor=white'></a>
<a href="https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/blob/master/LICENSE"><img alt="License" src="https://img.shields.io/github/license/rdavydov/Twitch-Channel-Points-Miner-v2?style=flat&color=black&logo=unlicense&logoColor=white"></a>
<a href="https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2"><img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/rdavydov/Twitch-Channel-Points-Miner-v2?style=flat&color=lightyellow&logo=github&logoColor=white"></a>
</p>

<p align="center">
<a href="https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2"><img alt="Docker Version" src="https://img.shields.io/docker/v/rdavidoff/twitch-channel-points-miner-v2?style=flat&color=white&logo=docker&logoColor=white&label=release"></a>
<a href="https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2"><img alt="Docker Stars" src="https://img.shields.io/docker/stars/rdavidoff/twitch-channel-points-miner-v2?style=flat&color=limegreen&logo=docker&logoColor=white&label=stars"></a>
<a href="https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2"><img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/rdavidoff/twitch-channel-points-miner-v2?style=flat&color=blue&logo=docker&logoColor=white&label=pulls"></a>
<a href="https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2"><img alt="Docker Images Size AMD64" src="https://img.shields.io/docker/image-size/rdavidoff/twitch-channel-points-miner-v2/latest?arch=amd64&label=AMD64%20image%20size&style=flat&color=purple&logo=amd&logoColor=white"></a>
<a href="https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2"><img alt="Docker Images Size ARM64" src="https://img.shields.io/docker/image-size/rdavidoff/twitch-channel-points-miner-v2/latest?arch=arm64&label=ARM64%20image%20size&style=flat&color=black&logo=arm&logoColor=white"></a>
<a href="https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2"><img alt="Docker Images Size ARMv7" src="https://img.shields.io/docker/image-size/rdavidoff/twitch-channel-points-miner-v2/latest?arch=arm&label=ARMv7%20image%20size&style=flat&color=lightyellow&logo=arm&logoColor=white"></a>
</p>

Watch Twitch streams for you and earn channel points automatically. The miner
claims bonus chests, follows raids, catches watch streaks, claims drops and
moments, and can place predictions with your points. It runs from a small
Python script you configure once.

This project is based on [Tkd-Alex/Twitch-Channel-Points-Miner-v2](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2), which grew from [gottagofaster236/Twitch-Channel-Points-Miner](https://github.com/gottagofaster236/Twitch-Channel-Points-Miner).

## Contents

- [Features](#features)
- [Before you start](#before-you-start)
- [Install](#install)
- [First run](#first-run)
- [Configuration](#configuration)
- [Notifications](#notifications)
- [Streamer and bet settings](#streamer-and-bet-settings)
- [Analytics](#analytics)
- [Docker](#docker)
- [Run unattended (supervisor)](#run-unattended-supervisor)
- [Logs](#logs)
- [Other platforms](#other-platforms)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing) · [License](#license) · [Acknowledgments](#acknowledgments) · [Support](#support) · [Disclaimer](#disclaimer)

## Features

- 🎁 **Channel points on autopilot**: watch time, bonus chests, raids (`+250`) and watch streaks are collected for you
- 🏆 **Priority system**: decide who gets watched first (watch streaks, drops, subscriptions, list order or points)
- 📦 **Drops**: game drops are claimed as soon as Twitch reports them finished, streamers whose drops can still be completed before the campaign ends are watched first, and you get a notification when a finished drop could not be claimed
- 🎰 **Predictions**: bet with your channel points using one of 13 strategies, with filters, delays and a stealth mode
- 💬 **Chat presence**: join IRC chat to appear online, collect StreamElements points and get notified when someone mentions you
- ✨ **Moments and community goals**: claim moments and contribute to streamers' community challenges
- 🔔 **Notifications**: Telegram, Discord, Matrix, Pushover, Gotify, generic webhooks, and [Apprise](https://github.com/caronc/apprise) for 100+ more services
- 📈 **Analytics**: a local web chart of your points over time
- 🧾 **Readable logs**: emoji, colors, a compact mode, log rotation and a final report per session
- 🐳 **Docker images** for `linux/amd64`, `linux/arm64` and `linux/arm/v7`
- 🛡️ **Unattended mode**: an optional supervisor for Windows, Linux and macOS that restarts, updates and health-checks the miner

## Before you start

> [!WARNING]
> - **Use at your own risk:** automating Twitch viewing can get an account
>   soft or hard banned. This project is not affiliated with Twitch.
> - **Two channels at a time:** Twitch only counts watch time for two
>   streams at once. The first two streamers by priority are watched.
> - **Your cookie file is your login:** `cookies/<username>.pkl` lets anyone
>   use your Twitch session. Keep it private and never commit it.
> - **Keep `run.py` private:** it holds your notification tokens. It is
>   git-ignored; keep it that way.

You'll need:

- Python 3.10 or newer, or Docker
- git
- Your Twitch username (you log in once with a code, no password needed)

## Install

```bash
git clone https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2.git
cd Twitch-Channel-Points-Miner-v2
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## First run

1. **Create your runner file.** Copy `example.py` to `run.py` and edit it:
   set your `username`, your streamers and the settings you want
   (see [Configuration](#configuration)).
   ```bash
   cp example.py run.py
   ```
2. **Start the miner:**
   ```bash
   python run.py
   ```
3. **Log in once.** The miner prints a code. Open
   https://www.twitch.tv/activate, enter the code and approve. The login is
   saved to `cookies/<username>.pkl` and reused on the next start.

Stop the miner with **Ctrl+C**. It leaves chat, closes its connections and
prints a [final report](#final-report).

## Configuration

`example.py` is a complete, commented configuration. Every setting has a
default, so the shortest working `run.py` is:

```python
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Settings import FollowersOrder
twitch_miner = TwitchChannelPointsMiner("your-twitch-username")
twitch_miner.mine(["streamer1", "streamer2"])                                                       # Array of streamers OR
twitch_miner.mine(followers=True, followers_order=FollowersOrder.ASC)                               # Automatic use the followers list OR
twitch_miner.mine(["streamer1", "streamer2"], followers=True, followers_order=FollowersOrder.DESC)  # Mixed
```

If you follow many streamers but don't want to mine all of them, exclude
some with `blacklist`:

```python
twitch_miner.mine(followers=True, blacklist=["user1", "user2"])
```

<details>
<summary><b>Full example (<code>example.py</code>)</b></summary>

```python
# -*- coding: utf-8 -*-

import logging
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
from TwitchChannelPointsMiner.classes.Apprise import Apprise
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

twitch_miner = TwitchChannelPointsMiner(
    username="your-twitch-username",
    password="write-your-secure-psw",           # If no password will be provided, the script will ask interactively
    claim_drops_startup=False,                  # If you want to auto claim all drops from Twitch inventory on the startup
    priority=[                                  # Custom priority in this case for example:
        Priority.STREAK,                        # - We want first of all to catch all watch streak from all streamers
        Priority.DROPS,                         # - When we don't have anymore watch streak to catch, wait until all drops are collected over the streamers
        Priority.ORDER                          # - When we have all of the drops claimed and no watch-streak available, use the order priority (POINTS_ASCENDING, POINTS_DESCENDING)
    ],
    enable_analytics=False,                     # Disables Analytics if False. Disabling it significantly reduces memory consumption
    disable_ssl_cert_verification=False,        # Set to True at your own risk and only to fix SSL: CERTIFICATE_VERIFY_FAILED error
    disable_at_in_nickname=False,               # Set to True if you want to check for your nickname mentions in the chat even without @ sign
    logger_settings=LoggerSettings(
        save=True,                              # If you want to save logs in a file (suggested)
        console_level=logging.INFO,             # Level of logs - use logging.DEBUG for more info
        console_username=False,                 # Adds a username to every console log line if True. Also adds it to Telegram, Discord, etc. Useful when you have several accounts
        auto_clear=True,                        # Create a file rotation handler with interval = 1D and backupCount = 7 if True (default)
        time_zone="",                           # Set a specific time zone for console and file loggers. Use tz database names. Example: "America/Denver"
        file_level=logging.DEBUG,               # Level of logs - If you think the log file it's too big, use logging.INFO
        emoji=True,                             # On Windows, we have a problem printing emoji. Set to false if you have a problem
        less=False,                             # If you think that the logs are too verbose, set this to True
        colored=True,                           # If you want to print colored text
        color_palette=ColorPalette(             # You can also create a custom palette color (for the common message).
            STREAMER_online="GREEN",            # Don't worry about lower/upper case. The script will parse all the values.
            streamer_offline="red",             # Read more in README.md
            BET_wiN=Fore.MAGENTA                # Color allowed are: [BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET].
        ),
        telegram=Telegram(                                                          # You can omit or set to None if you don't want to receive updates on Telegram
            chat_id=123456789,                                                      # Chat ID to send messages @getmyid_bot
            token="123456789:shfuihreuifheuifhiu34578347",                          # Telegram API token @BotFather
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                    Events.BET_LOSE, Events.CHAT_MENTION],                          # Only these events will be sent to the chat
            disable_notification=True,                                              # Revoke the notification (sound/vibration)
        ),
        discord=Discord(
            webhook_api="https://discord.com/api/webhooks/0123456789/0a1B2c3D4e5F6g7H8i9J",  # Discord Webhook URL
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                    Events.BET_LOSE, Events.CHAT_MENTION],                                  # Only these events will be sent to the chat
        ),
        webhook=Webhook(
            endpoint="https://example.com/webhook",                                                                    # Webhook URL
            method="GET",                                                                   # GET or POST
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                    Events.BET_LOSE, Events.CHAT_MENTION],                                  # Only these events will be sent to the endpoint
        ),
        matrix=Matrix(
            username="twitch_miner",                                                   # Matrix username (without homeserver)
            password="...",                                                            # Matrix password
            homeserver="matrix.org",                                                   # Matrix homeserver
            room_id="...",                                                             # Room ID
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE, Events.BET_LOSE], # Only these events will be sent
        ),
        pushover=Pushover(
            userkey="YOUR-ACCOUNT-TOKEN",                                             # Login to https://pushover.net/, the user token is on the main page
            token="YOUR-APPLICATION-TOKEN",                                           # Create a application on the website, and use the token shown in your application
            priority=0,                                                               # Read more about priority here: https://pushover.net/api#priority
            sound="pushover",                                                         # A list of sounds can be found here: https://pushover.net/api#sounds
            events=[Events.CHAT_MENTION, Events.DROP_CLAIM],                          # Only these events will be sent
        ),
        gotify=Gotify(
            endpoint="https://example.com/message?token=TOKEN",
            priority=8,
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                    Events.BET_LOSE, Events.CHAT_MENTION],
        ),
        apprise=Apprise(                                                            # One notifier for 100+ services (Discord, Telegram, ntfy, email, ...)
            urls=["discord://WEBHOOK_ID/WEBHOOK_TOKEN", "ntfy://my-topic"],          # URL formats: https://github.com/caronc/apprise/wiki
            events=[Events.DROP_CLAIM, Events.DROP_UNCLAIMED,
                    Events.CHAT_MENTION],                                           # Only these events will be sent
        )
    ),
    streamer_settings=StreamerSettings(
        make_predictions=True,                  # If you want to Bet / Make prediction
        follow_raid=True,                       # Follow raid to obtain more points
        claim_drops=True,                       # We can't filter rewards base on stream. Set to False for skip viewing counter increase and you will never obtain a drop reward from this script. Issue #21
        claim_moments=True,                     # If set to True, https://help.twitch.tv/s/article/moments will be claimed when available
        watch_streak=True,                      # If a streamer go online change the priority of streamers array and catch the watch screak. Issue #11
        community_goals=False,                  # If True, contributes the max channel points per stream to the streamers' community challenge goals
        chat=ChatPresence.ONLINE,               # Join irc chat to increase watch-time [ALWAYS, NEVER, ONLINE, OFFLINE]
        bet=BetSettings(
            strategy=Strategy.SMART,            # Choose you strategy!
            percentage=5,                       # Place the x% of your channel points
            percentage_gap=20,                  # Gap difference between outcomesA and outcomesB (for SMART strategy)
            max_points=50000,                   # If the x percentage of your channel points is gt bet_max_points set this value
            stealth_mode=True,                  # If the calculated amount of channel points is GT the highest bet, place the highest value minus 1-2 points Issue #33
            delay_mode=DelayMode.FROM_END,      # When placing a bet, we will wait until `delay` seconds before the end of the timer
            delay=6,
            minimum_points=20000,               # Place the bet only if we have at least 20k points. Issue #113
            filter_condition=FilterCondition(
                by=OutcomeKeys.TOTAL_USERS,     # Where apply the filter. Allowed [PERCENTAGE_USERS, ODDS_PERCENTAGE, ODDS, TOP_POINTS, TOTAL_USERS, TOTAL_POINTS]
                where=Condition.LTE,            # 'by' must be [GT, LT, GTE, LTE] than value
                value=800
            )
        )
    )
)

# You can customize the settings for each streamer. If not settings were provided, the script would use the streamer_settings from TwitchChannelPointsMiner.
# If no streamer_settings are provided in TwitchChannelPointsMiner the script will use default settings.
# The streamers array can be a String -> username or Streamer instance.

# The settings priority are: settings in mine function, settings in TwitchChannelPointsMiner instance, default settings.
# For example, if in the mine function you don't provide any value for 'make_prediction' but you have set it on TwitchChannelPointsMiner instance, the script will take the value from here.
# If you haven't set any value even in the instance the default one will be used

#twitch_miner.analytics(host="127.0.0.1", port=5000, refresh=5, days_ago=7)   # Start the Analytics web-server

twitch_miner.mine(
    [
        Streamer("streamer-username01", settings=StreamerSettings(make_predictions=True  , follow_raid=False , claim_drops=True  , watch_streak=True , community_goals=False , bet=BetSettings(strategy=Strategy.SMART      , percentage=5 , stealth_mode=True,  percentage_gap=20 , max_points=234   , filter_condition=FilterCondition(by=OutcomeKeys.TOTAL_USERS,      where=Condition.LTE, value=800 ) ) )),
        Streamer("streamer-username02", settings=StreamerSettings(make_predictions=False , follow_raid=True  , claim_drops=False ,                                             bet=BetSettings(strategy=Strategy.PERCENTAGE , percentage=5 , stealth_mode=False, percentage_gap=20 , max_points=1234  , filter_condition=FilterCondition(by=OutcomeKeys.TOTAL_POINTS,     where=Condition.GTE, value=250 ) ) )),
        Streamer("streamer-username03", settings=StreamerSettings(make_predictions=True  , follow_raid=False ,                     watch_streak=True , community_goals=True  , bet=BetSettings(strategy=Strategy.SMART      , percentage=5 , stealth_mode=False, percentage_gap=30 , max_points=50000 , filter_condition=FilterCondition(by=OutcomeKeys.ODDS,             where=Condition.LT,  value=300 ) ) )),
        Streamer("streamer-username04", settings=StreamerSettings(make_predictions=False , follow_raid=True  ,                     watch_streak=True ,                                                                                                                                                                                                                                                       )),
        Streamer("streamer-username05", settings=StreamerSettings(make_predictions=True  , follow_raid=True  , claim_drops=True ,  watch_streak=True , community_goals=True  , bet=BetSettings(strategy=Strategy.HIGH_ODDS  , percentage=7 , stealth_mode=True,  percentage_gap=20 , max_points=90    , filter_condition=FilterCondition(by=OutcomeKeys.PERCENTAGE_USERS, where=Condition.GTE, value=300 ) ) )),
        Streamer("streamer-username06"),
        Streamer("streamer-username07"),
        Streamer("streamer-username08"),
        "streamer-username09",
        "streamer-username10",
        "streamer-username11"
    ],                                  # Array of streamers (order = priority)
    followers=False,                    # Automatic download the list of your followers
    followers_order=FollowersOrder.ASC  # Sort the followers list by follow date. ASC or DESC
)
```

</details>

Settings are applied in this order: settings on a `Streamer(...)` in
`mine()`, then `streamer_settings` on `TwitchChannelPointsMiner`, then the
defaults.

### Miner options

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `username` | str | | Your Twitch username |
| `password` | str | `None` | Not used. Login is the twitch.tv/activate code flow |
| `claim_drops_startup` | bool | `False` | Claim every finished drop in your inventory when the miner starts |
| `enable_analytics` | bool | `False` | Record data for the [analytics](#analytics) chart. Off saves memory and disk |
| `disable_ssl_cert_verification` | bool | `False` | Only to work around `SSL: CERTIFICATE_VERIFY_FAILED`. Makes connections unsafe |
| `disable_at_in_nickname` | bool | `False` | Detect chat mentions of your name even without `@` |
| `priority` | list | `[STREAK, DROPS, ORDER]` | Who to watch first (below) |
| `logger_settings` | LoggerSettings | | [Logging and notifications](#loggersettings) |
| `streamer_settings` | StreamerSettings | | [Defaults for every streamer](#streamersettings) |

`mine()` takes the streamer list (order = priority), `followers`,
`followers_order` (`FollowersOrder.ASC` or `DESC`, by follow date) and
`blacklist`.

### Priority

Only two streams count at a time, so `priority` decides which two. Combine
several values; use at least one of `ORDER`, `POINTS_ASCENDING` or
`POINTS_DESCENDING`, otherwise the miner stops watching once, for example,
all watch streaks are caught.

| Value | Watches first |
| :-- | :-- |
| `STREAK` | Streamers whose watch streak can still be caught |
| `DROPS` | Streamers with drops enabled for a game you have an active campaign for; those with a drop that can still be finished before it ends come first |
| `SUBSCRIBED` | Streamers you are subscribed to (higher tiers first) |
| `ORDER` | The order of your streamer list |
| `POINTS_ASCENDING` | Streamers where you have the fewest points |
| `POINTS_DESCENDING` | Streamers where you have the most points |

`ORDER` and `POINTS_ASCENDING` together don't make sense.

### LoggerSettings

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `save` | bool | `True` | Save logs to `logs/` |
| `less` | bool | `False` | Shorter log lines ([compare](#logs)) |
| `console_level` | level | `logging.INFO` | Console log level |
| `console_username` | bool | `False` | Prefix lines (and notifications) with your username. Useful with several accounts |
| `time_zone` | str | `None` | tz database name, e.g. `"America/Denver"` |
| `file_level` | level | `logging.DEBUG` | Log file level. Use `logging.INFO` for smaller files |
| `emoji` | bool | `False` on Windows, else `True` | Emoji in logs |
| `colored` | bool | `False` | Colored console output |
| `auto_clear` | bool | `True` | Rotate the log file daily, keep 7 days |
| `color_palette` | ColorPalette | `RESET`, `BET_WIN` green, `BET_LOSE` red | [Custom colors](#color-palette) |
| `telegram`, `discord`, `webhook`, `matrix`, `pushover`, `gotify`, `apprise` | notifier | `None` | [Notifications](#notifications) |

#### Color palette

Every [event](#events) can have its own color. Allowed colors are the
Colorama `Fore` colors: `BLACK`, `RED`, `GREEN`, `YELLOW`, `BLUE`,
`MAGENTA`, `CYAN`, `WHITE`, `RESET`. Names are case-insensitive.

```python
from colorama import Fore
ColorPalette(
    STREAMER_ONLINE = Fore.GREEN,
    STREAMER_OFFLINE = Fore.RED,
    GAIN_FOR_RAID = Fore.YELLOW,
    GAIN_FOR_CLAIM = Fore.YELLOW,
    GAIN_FOR_WATCH = Fore.YELLOW,
    GAIN_FOR_WATCH_STREAK = Fore.YELLOW,
    BET_WIN = Fore.GREEN,
    BET_LOSE = Fore.RED,
    BET_REFUND = Fore.RESET,
    BET_FILTERS = Fore.MAGENTA,
    BET_GENERAL = Fore.BLUE,
    BET_FAILED = Fore.RED,
)
```

## Notifications

Each notifier sends only the [events](#events) in its `events` list. Add the
ones you want to `LoggerSettings` in `run.py`; leave the others out or set
them to `None`.

### Apprise (100+ services)

One notifier for Discord, Telegram, Matrix, Pushover, Gotify, ntfy, Slack,
email and [many more](https://github.com/caronc/apprise/wiki). Each service
is one URL.

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `urls` | list or str | | Apprise URLs |
| `events` | list | | Events to send |
| `title` | str | `"Twitch Channel Points Miner"` | Notification title |

```python
Apprise(
    urls=["discord://WEBHOOK_ID/WEBHOOK_TOKEN", "tgram://BOT_TOKEN/CHAT_ID", "ntfy://my-topic"],
    events=[Events.DROP_CLAIM, Events.DROP_UNCLAIMED, Events.CHAT_MENTION],
)
```

| Service | URL format |
| :-- | :-- |
| Discord | `discord://webhook_id/webhook_token` |
| Telegram | `tgram://bot_token/chat_id` |
| Pushover | `pover://user_key@app_token` |
| ntfy | `ntfy://topic` |
| Gotify | `gotify://hostname/token` |
| Matrix | `matrix://user:password@hostname/#room` |

### Telegram

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your `chat_id` with [@getmyid_bot](https://t.me/getmyid_bot)

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `chat_id` | int | | Chat to send to |
| `token` | str | | Bot token from @BotFather |
| `events` | list | | Events to send |
| `disable_notification` | bool | `False` | Send silently (no sound or vibration) |

```python
Telegram(
    chat_id=123456789,
    token="123456789:shfuihreuifheuifhiu34578347",
    events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE, Events.BET_LOSE, Events.CHAT_MENTION],
    disable_notification=True,
)
```

### Discord

In your server: **Edit Channel** → **Integrations** → **Webhooks** →
**New Webhook** → **Copy Webhook URL**.

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `webhook_api` | str | | Discord webhook URL |
| `events` | list | | Events to send |

```python
Discord(
    webhook_api="https://discord.com/api/webhooks/0123456789/0a1B2c3D4e5F6g7H8i9J",
    events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE, Events.BET_LOSE, Events.CHAT_MENTION],
)
```

### Generic webhook

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `endpoint` | str | | Webhook URL |
| `method` | str | | `GET` or `POST` |
| `events` | list | | Events to send |

```python
Webhook(
    endpoint="https://example.com/webhook",
    method="GET",
    events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE, Events.BET_LOSE, Events.CHAT_MENTION],
)
```

### Matrix, Pushover and Gotify

| Notifier | Keys |
| :-- | :-- |
| `Matrix` | `username` (without homeserver), `password`, `homeserver`, `room_id`, `events` |
| `Pushover` | `userkey`, `token` (application token), [`priority`](https://pushover.net/api#priority), [`sound`](https://pushover.net/api#sounds), `events` |
| `Gotify` | `endpoint` (`https://example.com/message?token=TOKEN`), `priority`, `events` |

See `example.py` for a filled-in example of each.

### Events

| Event | Sent when |
| :-- | :-- |
| `STREAMER_ONLINE` / `STREAMER_OFFLINE` | A streamer goes live or offline |
| `GAIN_FOR_WATCH`, `GAIN_FOR_CLAIM`, `GAIN_FOR_RAID`, `GAIN_FOR_WATCH_STREAK` | Points are earned |
| `BET_START`, `BET_GENERAL`, `BET_FILTERS`, `BET_FAILED` | A prediction is considered, placed, filtered out or fails |
| `BET_WIN`, `BET_LOSE`, `BET_REFUND` | A prediction ends |
| `BONUS_CLAIM` | A bonus chest is claimed |
| `MOMENT_CLAIM` | A moment is claimed |
| `JOIN_RAID` | A raid is followed |
| `DROP_CLAIM` | A drop is claimed |
| `DROP_STATUS` | Drop progress changes |
| `DROP_UNCLAIMED` | A finished drop could not be claimed. Drops whose campaign needs a linked game account (Twitch shows **Connect** instead of **Claim**) are skipped |
| `CHAT_MENTION` | Someone mentions you in chat |

## Streamer and bet settings

### StreamerSettings

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `make_predictions` | bool | `True` | Place predictions |
| `follow_raid` | bool | `True` | Follow raids for extra points |
| `claim_drops` | bool | `True` | Watch for drops and claim them from your inventory |
| `claim_moments` | bool | `True` | Claim moments |
| `watch_streak` | bool | `True` | Raise this streamer's priority to catch the watch streak |
| `community_goals` | bool | `False` | Contribute points to the streamer's community challenges |
| `chat` | ChatPresence | `ONLINE` | When to join IRC chat (below) |
| `bet` | BetSettings | | [Prediction rules](#betsettings) |

`chat` values: `ALWAYS` (join and never leave), `NEVER`, `ONLINE` (join
while the streamer is live), `OFFLINE` (join while the streamer is offline).

### BetSettings

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `strategy` | Strategy | `SMART` | How to pick an outcome (below) |
| `percentage` | int | `5` | Bet this % of your channel points |
| `percentage_gap` | int | `20` | Gap between outcomes for the `SMART` strategy |
| `max_points` | int | `50000` | Never bet more than this |
| `minimum_points` | int | `None` | Only bet when you have at least this many points |
| `stealth_mode` | bool | `False` | If your bet would be the highest, bet 1-2 points below the current highest instead |
| `delay_mode` | DelayMode | `FROM_END` | How `delay` is measured (below) |
| `delay` | float | `6` | When to place the bet |
| `filter_condition` | FilterCondition | `None` | Only bet when a [condition](#filtercondition) matches |

### Strategies

| Strategy | Picks |
| :-- | :-- |
| `MOST_VOTED` | The outcome most users chose |
| `HIGH_ODDS` | The outcome with the highest odds |
| `PERCENTAGE` | The outcome with the highest percentage based on odds (as Twitch shows it) |
| `SMART_MONEY` | The outcome with the most points placed |
| `SMART` | Follows the majority when the user split is bigger than `percentage_gap`, otherwise the highest odds |
| `NUMBER_1` … `NUMBER_8` | Always the 1st … 8th outcome (`NUMBER_1` is blue, `NUMBER_2` is pink when there are two) |

![Prediction example](assets/prediction.png)

For this prediction: `MOST_VOTED` picks **over 7.5** (21 users vs 9),
`HIGH_ODDS` picks **over 7.5** (2.27 vs 1.79), `PERCENTAGE` picks
**under 7.5** (56%), and `SMART` sees a 70% / 30% user split. With
`percentage_gap=20`, 70 − 30 = 40 > 20, so it picks **over 7.5**.

### DelayMode

| Mode | `delay` means | Example: 10-minute prediction |
| :-- | :-- | :-- |
| `FROM_START` | Seconds after it opens | `delay=20` → bets at 0:20 |
| `FROM_END` | Seconds before it closes | `delay=20` → bets at 9:40 |
| `PERCENTAGE` | Fraction of the timer elapsed | `delay=0.2` → bets at 2:00 |

### FilterCondition

Only bet when `by` compared with `value` using `where` is true.

| Key | Type | Description |
| :-- | :-- | :-- |
| `by` | OutcomeKeys | What to compare (below) |
| `where` | Condition | `GT`, `LT`, `GTE` or `LTE` |
| `value` | number | Value to compare with |

`by` values: `PERCENTAGE_USERS`, `ODDS_PERCENTAGE`, `ODDS`,
`DECISION_USERS`, `DECISION_POINTS` and `TOP_POINTS` look at the chosen
outcome; `TOTAL_USERS` and `TOTAL_POINTS` add up both sides.

```python
FilterCondition(by=OutcomeKeys.TOTAL_USERS, where=Condition.GT, value=200)   # more than 200 people bet
FilterCondition(by=OutcomeKeys.ODDS, where=Condition.GTE, value=1.3)         # chosen odds at least 1.3
FilterCondition(by=OutcomeKeys.TOP_POINTS, where=Condition.LT, value=2000)   # highest bet under 2000
```

## Analytics

A small local web page charts your points over time, with annotations for
predictions and watch streaks, tooltips per point, and a dark theme.

| Light theme | Dark theme |
| :-- | :-- |
| ![Light theme](assets/chart-analytics-light.png) | ![Dark theme](assets/chart-analytics-dark.png) |

Set `enable_analytics=True` on `TwitchChannelPointsMiner`, then call
`analytics()` before `mine()`:

```python
twitch_miner = TwitchChannelPointsMiner("your-twitch-username", enable_analytics=True)
twitch_miner.analytics(host="127.0.0.1", port=5000, refresh=5, days_ago=7)
twitch_miner.mine(followers=True)
```

The page refreshes every `refresh` minutes and shows `days_ago` days by
default. Use `host="0.0.0.0"` to open it from another machine. Data is
stored in `analytics/`.

## Docker

Images: [`rdavidoff/twitch-channel-points-miner-v2`](https://hub.docker.com/r/rdavidoff/twitch-channel-points-miner-v2)
for `linux/amd64`, `linux/arm64` and `linux/arm/v7`.

| Mount | Purpose |
| :-- | :-- |
| `run.py` | Your configuration. **Required** |
| `cookies/` | Your saved login |
| `logs/` | Log files |
| `analytics/` | Analytics data |

Folders you don't mount are lost when the container stops.

```yml
services:
  miner:
    image: rdavidoff/twitch-channel-points-miner-v2
    stdin_open: true
    tty: true
    environment:
      - TERM=xterm-256color
    volumes:
      - ./analytics:/usr/src/app/analytics
      - ./cookies:/usr/src/app/cookies
      - ./logs:/usr/src/app/logs
      - ./run.py:/usr/src/app/run.py:ro
    ports:
      - "5000:5000"
```

```bash
docker run \
    -v $(pwd)/analytics:/usr/src/app/analytics \
    -v $(pwd)/cookies:/usr/src/app/cookies \
    -v $(pwd)/logs:/usr/src/app/logs \
    -v $(pwd)/run.py:/usr/src/app/run.py:ro \
    -p 5000:5000 \
    rdavidoff/twitch-channel-points-miner-v2
```

- **First login:** start with `-it` (or `docker attach`) to see the
  twitch.tv/activate code.
- **Windows (cmd):** `$(pwd)` doesn't work; use absolute paths, e.g.
  `-v C:\Path\To\run.py:/usr/src/app/run.py:ro`.
- **Several accounts:** one container each, with its own `run.py` and port:
  `docker run --name user1 -v $(pwd)/user1.py:/usr/src/app/run.py:ro -p 5001:5000 rdavidoff/twitch-channel-points-miner-v2`
- **Portainer:** see the [illustrated guide](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/wiki/Deploy-Docker-container-in-Portainer).

## Run unattended (supervisor)

`supervisor/` has an optional supervisor that keeps the miner running
without a terminal: Task Scheduler on Windows, systemd on Linux, launchd on
macOS. It:

- 🔄 **Updates** from git every 24 h and rolls back an update that keeps
  crashing (your local edits are kept)
- ♻️ **Restarts** cleanly every 24 h, after a crash (with backoff) and when
  the log stops moving for 20 minutes (needs `file_level=logging.DEBUG`)
- 🔑 **Handles login**: sends you the twitch.tv/activate code when the
  saved login expires
- 🩺 **Checks health** every 30 minutes and sends a daily points summary

### Linux and macOS

```bash
python3 supervisor/minerctl.py install   # creates .venv, installs requirements, registers the jobs
python3 supervisor/minerctl.py health    # HEALTHY / WARNING / DOWN (exit 0 / 1 / 2)
python3 supervisor/minerctl.py summary --hours 168
python3 supervisor/minerctl.py test-alert
python3 supervisor/minerctl.py start | stop | uninstall
```

On Linux, install enables lingering so the miner runs while you're logged
out. On macOS the jobs are LaunchAgents and run while you're logged in. On
Debian/Ubuntu install `python3-venv` first.

### Windows

In an admin PowerShell:

```powershell
.\supervisor\MinerTask.ps1                                     # install: three scheduled tasks
.\supervisor\MinerTask.ps1 -Action Health
.\supervisor\MinerTask.ps1 -Action Summary -SummaryHours 168
.\supervisor\MinerTask.ps1 -Action TestAlert
.\supervisor\MinerTask.ps1 -Action Start | Stop | Uninstall
```

`-LogonMode` sets how the tasks run: `Password` (default, runs at boot),
`S4U` (no stored password; may not work with Microsoft accounts) or
`AtLogon`.

### Supervisor alerts

Copy `supervisor/miner-alerts.example.json` to
`supervisor/miner-alerts.json` (git-ignored):

```json
{
  "appriseUrls": ["tgram://BOT_TOKEN/CHAT_ID"],
  "appriseUrgentUrls": ["pover://USER_KEY@APP_TOKEN?priority=emergency"]
}
```

`appriseUrgentUrls` is optional: crashes, DOWN and login-code alerts go
there instead. A Pushover-only config (`pushoverToken`, `pushoverUser`)
also works.

### Supervisor files

| File | Platform | Purpose |
| :-- | :-- | :-- |
| `minerctl.py` | Linux, macOS | Install and control (systemd user units or LaunchAgents) |
| `miner_supervisor.py` | Linux, macOS | The supervisor |
| `MinerTask.ps1` | Windows | Install and control (Task Scheduler) |
| `MinerSupervisor.ps1` | Windows | The supervisor (PowerShell 5.1 or 7) |
| `miner_wrapper.py` | all | Runs `run.py` and stops it cleanly on request |
| `notify.py`, `miner_common.py` | all | Alert sending and shared helpers |

## Logs

Logs go to the console and, with `save=True`, to `logs/<username>.log`.

<details>
<summary><b>Full logs</b></summary>

```
%d/%m/%y %H:%M:%S - INFO - [run]: 💣  Start session: '9eb934b0-1684-4a62-b3e2-ba097bd67d35'
%d/%m/%y %H:%M:%S - INFO - [run]: 🤓  Loading data for x streamers. Please wait ...
%d/%m/%y %H:%M:%S - INFO - [set_offline]: 😴  Streamer(username=streamer-username1, channel_id=0000000, channel_points=67247) is Offline!
%d/%m/%y %H:%M:%S - INFO - [set_offline]: 😴  Streamer(username=streamer-username2, channel_id=0000000, channel_points=4240) is Offline!
%d/%m/%y %H:%M:%S - INFO - [set_offline]: 😴  Streamer(username=streamer-username3, channel_id=0000000, channel_points=61365) is Offline!
%d/%m/%y %H:%M:%S - INFO - [set_offline]: 😴  Streamer(username=streamer-username4, channel_id=0000000, channel_points=3760) is Offline!
%d/%m/%y %H:%M:%S - INFO - [set_online]: 🥳  Streamer(username=streamer-username, channel_id=0000000, channel_points=61365) is Online!
%d/%m/%y %H:%M:%S - INFO - [start_bet]: 🔧  Start betting for EventPrediction(event_id=xxxx-xxxx-xxxx-xxxx, title=Please star this repo) owned by Streamer(username=streamer-username, channel_id=0000000, channel_points=61365)
%d/%m/%y %H:%M:%S - INFO - [on_message]: ⏰  Place the bet after: 89.99s for: EventPrediction(event_id=xxxx-xxxx-xxxx-xxxx-15c61914ef69, title=Please star this repo)
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +12 → Streamer(username=streamer-username, channel_id=0000000, channel_points=61377) - Reason: WATCH.
%d/%m/%y %H:%M:%S - INFO - [make_predictions]: 🍀  Going to complete bet for EventPrediction(event_id=xxxx-xxxx-xxxx-xxxx-15c61914ef69, title=Please star this repo) owned by Streamer(username=streamer-username, channel_id=0000000, channel_points=61377)
%d/%m/%y %H:%M:%S - INFO - [make_predictions]: 🍀  Place 5k channel points on: SI (BLUE), Points: 848k, Users: 190 (70.63%), Odds: 1.24 (80.65%)
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +6675 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64206) - Reason: PREDICTION.
%d/%m/%y %H:%M:%S - INFO - [on_message]: 📊  EventPrediction(event_id=xxxx-xxxx-xxxx-xxxx, title=Please star this repo) - Result: WIN, Points won: 6675
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +12 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64218) - Reason: WATCH.
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +12 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64230) - Reason: WATCH.
%d/%m/%y %H:%M:%S - INFO - [claim_bonus]: 🎁  Claiming the bonus for Streamer(username=streamer-username, channel_id=0000000, channel_points=64230)!
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +60 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64290) - Reason: CLAIM.
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +12 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64326) - Reason: WATCH.
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +400 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64326) - Reason: WATCH_STREAK.
%d/%m/%y %H:%M:%S - INFO - [claim_bonus]: 🎁  Claiming the bonus for Streamer(username=streamer-username, channel_id=0000000, channel_points=64326)!
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +60 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64386) - Reason: CLAIM.
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +12 → Streamer(username=streamer-username, channel_id=0000000, channel_points=64398) - Reason: WATCH.
%d/%m/%y %H:%M:%S - INFO - [update_raid]: 🎭  Joining raid from Streamer(username=streamer-username, channel_id=0000000, channel_points=64398) to another-username!
%d/%m/%y %H:%M:%S - INFO - [on_message]: 🚀  +250 → Streamer(username=streamer-username, channel_id=0000000, channel_points=6845) - Reason: RAID.
```

</details>

<details>
<summary><b>Less logs</b> (<code>less=True</code>)</summary>

```
%d/%m %H:%M:%S - 💣  Start session: '9eb934b0-1684-4a62-b3e2-ba097bd67d35'
%d/%m %H:%M:%S - 🤓  Loading data for 13 streamers. Please wait ...
%d/%m %H:%M:%S - 😴  streamer-username1 (xxx points) is Offline!
%d/%m %H:%M:%S - 😴  streamer-username2 (xxx points) is Offline!
%d/%m %H:%M:%S - 😴  streamer-username3 (xxx points) is Offline!
%d/%m %H:%M:%S - 😴  streamer-username4 (xxx points) is Offline!
%d/%m %H:%M:%S - 🥳  streamer-username (xxx points) is Online!
%d/%m %H:%M:%S - 🔧  Start betting for EventPrediction: Please star this repo owned by streamer-username (xxx points)
%d/%m %H:%M:%S - ⏰  Place the bet after: 89.99s EventPrediction: Please star this repo
%d/%m %H:%M:%S - 🚀  +12 → streamer-username (xxx points) - Reason: WATCH.
%d/%m %H:%M:%S - 🍀  Going to complete bet for EventPrediction: Please star this repo owned by streamer-username (xxx points)
%d/%m %H:%M:%S - 🍀  Place 5k channel points on: SI (BLUE), Points: 848k, Users: 190 (70.63%), Odds: 1.24 (80.65%)
%d/%m %H:%M:%S - 🚀  +6675 → streamer-username (xxx points) - Reason: PREDICTION.
%d/%m %H:%M:%S - 📊  EventPrediction: Please star this repo - Result: WIN, Points won: 6675
%d/%m %H:%M:%S - 🚀  +12 → streamer-username (xxx points) - Reason: WATCH.
%d/%m %H:%M:%S - 🚀  +12 → streamer-username (xxx points) - Reason: WATCH.
%d/%m %H:%M:%S - 🚀  +60 → streamer-username (xxx points) - Reason: CLAIM.
%d/%m %H:%M:%S - 🚀  +12 → streamer-username (xxx points) - Reason: WATCH.
%d/%m %H:%M:%S - 🚀  +400 → streamer-username (xxx points) - Reason: WATCH_STREAK.
%d/%m %H:%M:%S - 🚀  +60 → streamer-username (xxx points) - Reason: CLAIM.
%d/%m %H:%M:%S - 🚀  +12 → streamer-username (xxx points) - Reason: WATCH.
%d/%m %H:%M:%S - 🎭  Joining raid from streamer-username (xxx points) to another-username!
%d/%m %H:%M:%S - 🚀  +250 → streamer-username (xxx points) - Reason: RAID.
```

</details>

### Final report

<details>
<summary><b>Example</b></summary>

```
%d/%m/%y %H:%M:%S - 🛑  End session 'f738d438-cdbc-4cd5-90c4-1517576f1299'
%d/%m/%y %H:%M:%S - 📄  Logs file: /.../path/Twitch-Channel-Points-Miner-v2/logs/username.timestamp.log
%d/%m/%y %H:%M:%S - ⌛  Duration 10:29:19.547371

%d/%m/%y %H:%M:%S - 📊  BetSettings(strategy=SMART, percentage=7, percentage_gap=20, max_points=7500, minimum_points=None, stealth_mode=False)
%d/%m/%y %H:%M:%S - 📊  EventPrediction(event_id=xxxx-xxxx-xxxx-xxxx, title="Event Title1")
		Streamer(username=streamer-username, channel_id=0000000, channel_points=67247)
		Bet(TotalUsers=1k, TotalPoints=11M), Decision={'choice': 'B', 'amount': 5289, 'id': 'xxxx-yyyy-zzzz'})
		Outcome0(YES (BLUE) Points: 7M, Users: 641 (58.49%), Odds: 1.6, (5}%)
		Outcome1(NO (PINK),Points: 4M, Users: 455 (41.51%), Odds: 2.65 (37.74%))
		Result: {'type': 'LOSE', 'won': 0}
%d/%m/%y %H:%M:%S - 📊  EventPrediction(event_id=yyyy-yyyy-yyyy-yyyy, title="Event Title2")
		Streamer(username=streamer-username, channel_id=0000000, channel_points=3453464)
		Bet(TotalUsers=921, TotalPoints=11M), Decision={'choice': 'A', 'amount': 4926, 'id': 'xxxx-yyyy-zzzz'})
		Outcome0(YES (BLUE) Points: 9M, Users: 562 (61.02%), Odds: 1.31 (76.34%))
		Outcome1(YES (PINK) Points: 3M, Users: 359 (38.98%), Odds: 4.21 (23.75%))
		Result: {'type': 'WIN', 'won': 6531}
%d/%m/%y %H:%M:%S - 📊  EventPrediction(event_id=ad152117-251b-4666-b683-18e5390e56c3, title="Event Title3")
		Streamer(username=streamer-username, channel_id=0000000, channel_points=45645645)
		Bet(TotalUsers=260, TotalPoints=3M), Decision={'choice': 'A', 'amount': 5054, 'id': 'xxxx-yyyy-zzzz'})
		Outcome0(YES (BLUE) Points: 689k, Users: 114 (43.85%), Odds: 4.24 (23.58%))
		Outcome1(NO (PINK) Points: 2M, Users: 146 (56.15%), Odds: 1.31 (76.34%))
		Result: {'type': 'LOSE', 'won': 0}

%d/%m/%y %H:%M:%S - 🤖  Streamer(username=streamer-username, channel_id=0000000, channel_points=67247), Total points gained (after farming - before farming): -7838
%d/%m/%y %H:%M:%S - 💰  CLAIM(11 times, 550 gained), PREDICTION(1 times, 6531 gained), WATCH(35 times, 350 gained)
%d/%m/%y %H:%M:%S - 🤖  Streamer(username=streamer-username2, channel_id=0000000, channel_points=61365), Total points gained (after farming - before farming): 977
%d/%m/%y %H:%M:%S - 💰  CLAIM(4 times, 240 gained), REFUND(1 times, 605 gained), WATCH(11 times, 132 gained)
%d/%m/%y %H:%M:%S - 🤖  Streamer(username=streamer-username5, channel_id=0000000, channel_points=25960), Total points gained (after farming - before farming): 1680
%d/%m/%y %H:%M:%S - 💰  CLAIM(17 times, 850 gained), WATCH(53 times, 530 gained)
%d/%m/%y %H:%M:%S - 🤖  Streamer(username=streamer-username6, channel_id=0000000, channel_points=9430), Total points gained (after farming - before farming): 1120
%d/%m/%y %H:%M:%S - 💰  CLAIM(14 times, 700 gained), WATCH(42 times, 420 gained), WATCH_STREAK(1 times, 450 gained)
```

</details>

## Other platforms

### Windows

- Set `emoji=False` in `LoggerSettings` if the console shows garbled
  characters.
- More tips: [gottagofaster236 #31](https://github.com/gottagofaster236/Twitch-Channel-Points-Miner/issues/31),
  [Tkd-Alex #55](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2/issues/55),
  and this [video tutorial](https://www.youtube.com/watch?v=0VkM7NOZkuA).

### Termux (Android)

```bash
pkg upgrade
pkg install python git rust libjpeg-turbo libcrypt ndk-sysroot clang zlib binutils tur-repo python-cryptography
LDFLAGS="-L${PREFIX}/lib/" CFLAGS="-I${PREFIX}/include/" pip install --upgrade wheel pillow
pkg install python-pandas   # pre-built, from the tur-repo user repository
git clone https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2.git
cd Twitch-Channel-Points-Miner-v2
cp example.py run.py && nano run.py
pip install -r requirements.txt
python run.py
```

Installing `pandas`, `maturin` and `cryptography` takes a long time. If
`cryptography` fails to build:

```bash
export RUSTFLAGS=" -C lto=no" && export CARGO_BUILD_TARGET="$(rustc -vV | sed -n 's|host: ||p')" && pip install cryptography
```

More: [#92](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2/issues/92), [#76](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2/issues/76).

### Migrating from the original repository

Copy your old `twitch-cookies.pkl` to `cookies/your-twitch-username.pkl`.
If Twitch rejects it, delete it and log in again.

## Troubleshooting

| Symptom | What to do |
| :-- | :-- |
| `No username, exiting...` | Set `username` in `run.py` (not the `example.py` placeholder). |
| The miner waits for a code | Open https://www.twitch.tv/activate and enter the code it printed. With Docker, start with `-it`. |
| `ERR_BADAUTH` | Your saved login expired. Delete `cookies/<username>.pkl` and start again to log in. |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Update your system certificates (macOS: run *Install Certificates.command* for your Python). `disable_ssl_cert_verification=True` is a last resort. |
| Garbled characters on Windows | Set `emoji=False` in `LoggerSettings`. |
| Only two streamers earn watch points | Expected: Twitch counts two streams at a time. Adjust [priority](#priority). |
| A drop shows **Connect** and is never claimed | The campaign needs your game account linked. Link it on the campaign page; these drops are skipped by `DROP_UNCLAIMED`. |
| `Persisted query hash for ... is no longer valid` | Twitch changed an internal API ID. Drop operations switch to a built-in fallback automatically; for other operations, update the miner or open an issue. |
| Drops progress but are not claimed | Look for `Drop claim failed` warnings in the log: they show the status and error Twitch returned. |
| `analytics()` shows nothing | Set `enable_analytics=True` on `TwitchChannelPointsMiner`. |
| Apprise notifications don't arrive | Check the URL format in the [Apprise wiki](https://github.com/caronc/apprise/wiki); invalid URLs are logged as errors at startup. |

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first:
Python code must be formatted with [Black](https://github.com/psf/black), and
the pre-commit hooks (isort, Black, flake8) run on `TwitchChannelPointsMiner/`:

```bash
pip install pre-commit
pre-commit install
```

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).

## Acknowledgments

- [gottagofaster236/Twitch-Channel-Points-Miner](https://github.com/gottagofaster236/Twitch-Channel-Points-Miner) - the original idea
- [Tkd-Alex/Twitch-Channel-Points-Miner-v2](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2) - the v2 this project continues
- [ClementRoyer/TwitchAutoCollect-AutoBet](https://github.com/ClementRoyer/TwitchAutoCollect-AutoBet) - the first betting system
- [Apprise](https://github.com/caronc/apprise) - notifications to 100+ services

## Support

If you find this project helpful, please give it a ⭐️ and share it!

For questions or problems, open an [issue](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/issues).

If you'd like to buy the maintainer a coffee:

| | |
| :-- | :-- |
|<a href="https://bitcoin.org" target="_blank"><img src="https://dynamic-assets.coinbase.com/e785e0181f1a23a30d9476038d9be91e9f6c63959b538eabbc51a1abc8898940383291eede695c3b8dfaa1829a9b57f5a2d0a16b0523580346c6b8fab67af14b/asset_icons/b57ac673f06a4b0338a596817eb0a50ce16e2059f327dc117744449a47915cb2.png" alt="Donate BTC" height="16" width="16"></a>|`bc1qq49mvgda2zw4f9kta0a85xztwuxewqwac5eckd` _(<a href="https://bitcoin.org" target="_blank">BTC</a>)_|
|<a href="https://dogechain.info" target="_blank"><img src="https://dynamic-assets.coinbase.com/3803f30367bb3972e192cd3fdd2230cd37e6d468eab12575a859229b20f12ff9c994d2c86ccd7bf9bc258e9bd5e46c5254283182f70caf4bd02cc4f8e3890d82/asset_icons/1597d628dd19b7885433a2ac2d7de6ad196c519aeab4bfe679706aacbf1df78a.png" alt="Donate DOGE" height="16" width="16"></a>|`DAKzncwKkpfPCm1xVU7u2pConpXwX7HS3D` _(<a href="https://dogechain.info" target="_blank">DOGE</a>)_|
|<a href="https://www.donationalerts.com/r/rdavydov" target="_blank"><img src="https://www.donationalerts.com/static/donations/dist/favicon.ico" alt="Donate via DonationAlerts" height="16" width="16"></a>|https://www.donationalerts.com/r/rdavydov|
|<a href="https://boosty.to/rdavydov/donate" target="_blank"><img src="https://static.boosty.to/static/favicon.png?v=11" alt="Donate via Boosty" height="16" width="16"></a>|https://boosty.to/rdavydov/donate|

## Disclaimer

This project comes with no guarantee or warranty. You are responsible for
whatever happens from using it. It is possible to get soft or hard banned by
using this project if you are not careful. This is a personal project and is
in no way affiliated with Twitch.
