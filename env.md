# Environment Variables Guide

This document describes all environment variables available to configure the Twitch Channel Points Miner without modifying the code. You can define these variables in a `.env` file or directly in your environment.

---

## Twitch Credentials

| Variable              | Description                                         | Required |
|-----------------------|-----------------------------------------------------|----------|
| `TWITCH_USERNAME`     | Your Twitch username                                | ✅       |
| `TWITCH_PASSWORD`     | Your Twitch OAuth password (or leave empty to prompt) | ❌       |

---

## General Configuration

| Variable                    | Description                                           | Default   |
|-----------------------------|-------------------------------------------------------|-----------|
| `CLAIM_DROPS_STARTUP`       | Auto-claim drops on startup                           | `False`   |
| `ENABLE_ANALYTICS`          | Enable built-in analytics webserver                   | `False`   |
| `DISABLE_SSL_VERIFY`        | Skip SSL certificate verification (not recommended)   | `False`   |
| `DISABLE_AT_IN_NICKNAME`    | Detect mentions even without `@`                      | `False`   |
| `STREAMERS`                 | Comma-separated list of streamer usernames to mine    | *(none)*  |

---

## Priority Configuration

| Variable         | Description                                 | Default     |
|------------------|---------------------------------------------|-------------|
| `PRIORITY_1`     | First priority (`STREAK`, `DROPS`, `ORDER`) | `STREAK`    |
| `PRIORITY_2`     | Second priority                              | `DROPS`     |
| `PRIORITY_3`     | Third priority                               | `ORDER`     |

---

## Logger Settings

| Variable              | Description                                 | Default      |
|-----------------------|---------------------------------------------|--------------|
| `LOG_SAVE`            | Save logs to file                           | `True`       |
| `LOG_CONSOLE_LEVEL`   | Console log level (`DEBUG`, `INFO`, etc.)  | `INFO`       |
| `LOG_CONSOLE_USERNAME`| Include username in logs                    | `False`      |
| `LOG_AUTO_CLEAR`      | Enable daily log rotation                   | `True`       |
| `LOG_TIMEZONE`        | Timezone for logs (e.g., `America/Denver`) | `""`         |
| `LOG_FILE_LEVEL`      | File log level                              | `DEBUG`      |
| `LOG_EMOJI`           | Use emoji in logs                           | `True`       |
| `LOG_LESS`            | Less verbose logging                        | `False`      |
| `LOG_COLORED`         | Enable colored output                       | `True`       |
| `COLOR_ONLINE`        | Color for streamer online messages          | `GREEN`      |
| `COLOR_OFFLINE`       | Color for streamer offline messages         | `RED`        |
| `COLOR_BET_WIN`       | Color for bet win messages                  | `MAGENTA`    |

---

## Chat Presence

| Variable           | Description                                           | Default  |
|--------------------|-------------------------------------------------------|----------|
| `CHAT_PRESENCE`    | Chat presence mode (`ALWAYS`, `NEVER`, `ONLINE`, `OFFLINE`) | `ONLINE` |

---

## Notifications

These are not necessarily required. Just, if you use Telegram notifications, note that BOTH `TELEGRAM_CHAT_ID` and `TELEGRAM_TOKEN` are required..

### Telegram

| Variable              | Description             | Required |
|-----------------------|-------------------------|----------|
| `TELEGRAM_CHAT_ID`    | Telegram chat ID        | ✅       |
| `TELEGRAM_TOKEN`      | Telegram bot token      | ✅       |

### Discord

| Variable               | Description            | Required |
|------------------------|------------------------|----------|
| `DISCORD_WEBHOOK_API`  | Discord webhook URL    | ✅       |

### Webhook

| Variable              | Description                          | Default |
|-----------------------|--------------------------------------|---------|
| `WEBHOOK_ENDPOINT`    | URL for sending events               | ✅      |
| `WEBHOOK_METHOD`      | HTTP method (`GET` or `POST`)        | `GET`   |

### Matrix

| Variable              | Description                         | Required |
|-----------------------|-------------------------------------|----------|
| `MATRIX_USERNAME`     | Matrix username (no homeserver)     | ✅       |
| `MATRIX_PASSWORD`     | Matrix account password             | ✅       |
| `MATRIX_HOMESERVER`   | Matrix homeserver                   | `matrix.org` |
| `MATRIX_ROOM_ID`      | Room ID to send events to           | ✅       |

### Pushover

| Variable              | Description                         | Required |
|-----------------------|-------------------------------------|----------|
| `PUSHOVER_USERKEY`    | Your Pushover user token            | ✅       |
| `PUSHOVER_TOKEN`      | Your app token                      | ✅       |
| `PUSHOVER_PRIORITY`   | Message priority                    | `0`      |
| `PUSHOVER_SOUND`      | Notification sound                  | `pushover` |

### Gotify

| Variable             | Description                          | Required |
|----------------------|--------------------------------------|----------|
| `GOTIFY_ENDPOINT`     | Gotify message endpoint              | ✅       |
| `GOTIFY_PRIORITY`     | Priority of message                  | `8`      |

---

## Betting Settings

| Variable               | Description                                              | Default      |
|------------------------|----------------------------------------------------------|--------------|
| `BET_DISABLED`         | Set to `True` to disable betting entirely                | `False`      |
| `BET_STRATEGY`         | Betting strategy (`SMART`, `PERCENTAGE`, `HIGH_ODDS`)    | `SMART`      |
| `BET_PERCENTAGE`       | Percentage of points to bet                              | `5`          |
| `BET_PERCENTAGE_GAP`   | Minimum gap between outcomes (for SMART)                 | `20`         |
| `BET_MAX_POINTS`       | Max points allowed per bet                               | `50000`      |
| `BET_MIN_POINTS`       | Only bet if you have this many points                    | `20000`      |
| `BET_STEALTH_MODE`     | Bet slightly under the top bet to avoid notice           | `True`       |
| `BET_DELAY`            | Seconds to wait before bet ends to place bet             | `6`          |
| `BET_DELAY_MODE`       | When to delay (`FROM_END`, etc.)                         | `FROM_END`   |
| `FILTER_BY`            | Filter condition field (`TOTAL_USERS`, etc.)             | `TOTAL_USERS`|
| `FILTER_WHERE`         | Comparison operator (`GTE`, `LTE`, etc.)                 | `LTE`        |
| `FILTER_VALUE`         | Value to compare with                                    | `800`        |

---

## Followers

| Variable                  | Description                              | Default |
|---------------------------|------------------------------------------|---------|
| `FOLLOWERS_ORDER`         | Sort order for followers (`ASC`, `DESC`) | `ASC`   |

---

## Example `.env`

```env
TWITCH_USERNAME=mytwitchuser
TWITCH_PASSWORD=mypass123
TELEGRAM_CHAT_ID=123456789
TELEGRAM_TOKEN=abcd1234:ABCDEF
DISCORD_WEBHOOK_API=https://discord.com/api/webhooks/...
WEBHOOK_ENDPOINT=https://example.com/webhook
WEBHOOK_METHOD=POST
MATRIX_USERNAME=myuser
MATRIX_PASSWORD=mypassword
MATRIX_ROOM_ID=!roomid:matrix.org

BET_DISABLED=False
BET_STRATEGY=SMART
BET_PERCENTAGE=5
BET_PERCENTAGE_GAP=20
BET_MAX_POINTS=50000
BET_MIN_POINTS=20000
BET_STEALTH_MODE=True
BET_DELAY=6
BET_DELAY_MODE=FROM_END
FILTER_BY=TOTAL_USERS
FILTER_WHERE=LTE
FILTER_VALUE=800
```
