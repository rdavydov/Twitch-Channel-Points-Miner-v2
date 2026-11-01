# Twitch Channel Points Miner

Armi1014's fork of `Twitch-Channel-Points-Miner-v2`, with reliable watch streak tracking, channel priorities, drop claiming, reports, and formatted notifications.

This project is not affiliated with Twitch. Use it at your own risk and make sure you understand the platform rules before using automation tools.

## Requirements

- Python `>=3.10`
- Git
- `uv` recommended for setup
- `pip`/venv fallback supported through `requirements.txt`

## Quick start

```sh
git clone https://github.com/Armi1014/Twitch-Channel-Points-Miner-v2
cd Twitch-Channel-Points-Miner-v2
cp example.py run.py
uv sync
uv run run.py
```

Edit `run.py` before the first run. Set `USERNAME` and `STREAMERS`, or enable followed channels with `FOLLOWERS_ENABLED = True`. Leave `PASSWORD = None`: the first login uses a Twitch activation code, and later runs reuse the saved session.

Hermes is the default WebSocket backend. To force the legacy PubSub transport, set `USE_HERMES = False` in `run.py`.

## Pip fallback

```sh
python -m venv .venv
source .venv/bin/activate
cp example.py run.py
pip install -r requirements.txt
python run.py
```

On Windows, activate the venv with `.venv\Scripts\activate`.

## Configuration checklist

- Set your Twitch account in `USERNAME`.
- Leave `PASSWORD = None` and follow the activation instructions on the first login.
- Add channels to `STREAMERS`.
- Mark important channels with `StreamerSettings(favorite=True)` if `Priority.FAVORITE` is in your priority order.
- Drops are enabled by default through `claim_drops=True`.
- Daily reports are enabled by default; weekly, monthly, and yearly reports can be enabled separately.
- Keep `USE_HERMES = True` unless you need to troubleshoot with the legacy PubSub transport.

See [example.py](example.py) for a complete starter config.

## Notifications

All six providers have commented-out examples inside `LOGGER_SETTINGS` in
[example.py](example.py). Copy the file to `run.py`, uncomment the provider's
import and its configuration block, and replace the placeholders. Do this
before creating `TwitchChannelPointsMiner`; changing `LOGGER_SETTINGS` afterwards
does not reconfigure an existing miner. Several providers can be enabled together.

`NOTIFICATION_EVENTS` controls which messages are sent. The example selects
streamer-online, your-account subscription, and drop-claim events. Remove entries
or add others such as `Events.STREAMER_OFFLINE`, `Events.BET_PLACED`, and
`Events.CHAT_MENTION`. A provider can use its own `events=[...]` list instead.
An empty list sends no events. Notifications remain disabled until you uncomment
a provider block.

Discord uses English embed cards by default, with event emojis, colored sidebars,
timestamps, and structured drop, subscription, and prediction details. Prediction
results show the original stake, total payout, and net gain/loss; refunds show
the returned stake and zero net gain. Available channel names link to Twitch.
Set `message_format="plain"` in `Discord(...)` to restore text-only messages.
Discord emojis work independently of the console's `emoji` setting. Mentions are
disabled, and long text is shortened to fit Discord's message limits.

Prediction cards use Twitch's confirmed stake, outcome, and payout rather than
the miner's planned decision. The source distinguishes miner bets from manual
or external bets. Manual bets are observed even with `make_predictions=False`;
that setting still prevents the miner from submitting automatic bets.

Open predictions and notification delivery receipts are saved per account in
`logs/.state/predictions.<account>.json`. A background worker checks pending bets
with read-only Twitch queries after a restart or a missed socket message. It
never submits another bet while recovering a result. Notifications that fail
are retried only for the providers that have not acknowledged delivery.

The complete captured history is exported to
`logs/reports/predictions/predictions.<account>.csv`, including Twitch timestamps,
source, stake, outcome, payout, and net result. This is the reference for results
recovered from earlier days; old Excel files are not retroactively rewritten.
Existing state is needed for bets that started in a previous session. Twitch
API failures leave those bets pending for another check.

Normal replayed events and restarts do not repeat acknowledged notifications.
A crash exactly between a provider accepting a message and saving its receipt
can still repeat that message; external providers do not offer a shared
transaction with the local state file.

| Event | Discord card | Sent when |
|---|---|---|
| `DROP_CLAIM` | 🎁 Drop claimed | Twitch inventory confirms a new claim |
| `SUBSCRIPTION` | 🎉 Subscription | Your account subscribes, renews, receives a gift subscription, or upgrades |
| `BET_PLACED` | 🎯 Prediction placed | Twitch confirms your bet, with the channel, prediction, outcome, and stake |
| `BET_WIN` | ✅ Prediction won | Your bet wins |
| `BET_LOSE` | ❌ Prediction lost | Your bet loses |
| `BET_REFUND` | ↩️ Prediction refunded | Your stake is returned |
| `BET_FAILED` | ⚠️ Prediction failed | A bet attempt fails |

Use the `Events.` prefix in Python, for example `Events.BET_PLACED`.
`BET_START` is a scheduling notice; it does not confirm that a bet was placed.

Drop notifications are sent only after Twitch confirms a new successful claim.
Already-claimed drops and unsuccessful attempts do not produce a claim card.
An accepted claim without inventory confirmation stays pending and is retried
at most once every 15 minutes. Claim state survives restarts in
`cookies/<account>.drop-claims.json`, preventing repeated success notifications.
The event selection still controls what is sent; ordinary point gains and
stream-online messages are not added automatically.

Custom integrations can call `Discord.send(message, event, details=...)` with
structured data. Without details, an embed containing the original message is
used. Telegram, Matrix, and the other providers keep their existing formatting.

| Provider | Required configuration and setup |
|---|---|
| Telegram | Create a bot with [BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token), copy its token into `token`, and send `/start` to your bot. Use your destination's numeric `chat_id`; after sending a message, the Bot API's [`getUpdates`](https://core.telegram.org/bots/api#getupdates) response exposes it in `message.chat.id`. Group IDs may be negative; the bot must be a member with permission to send messages. `disable_notification=True` sends silently. |
| Discord | In **Server Settings → Integrations → Webhooks**, create a webhook for the destination channel and copy its full URL into `webhook_api`. See [Discord's guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks). |
| Gotify | Create an **application** in your Gotify server and use its application token in `endpoint="https://YOUR_HOST/message?token=YOUR_TOKEN"`. `priority=5` sets the message priority. See [Gotify's guide](https://gotify.net/docs/pushmsg). |
| Matrix | Set `username`, `password`, the `homeserver` hostname without `https://`, and the destination's internal `room_id` such as `!abc:example.org`, available in your client's room information. The account must already be joined to the room and support [password login](https://spec.matrix.org/latest/client-server-api/#password-based). This helper sends plain room messages and does not implement encrypted-room messaging. It attempts login as soon as its configuration is constructed. |
| Pushover | Copy your account's user key into `userkey`; create an application and put its API token in `token`. The example uses normal `priority=0` and `sound="pushover"`. Emergency priority requires fields this helper does not expose. See [Pushover's API guide](https://pushover.net/api). |
| Generic webhook | Set `endpoint` and `method="GET"` or `"POST"`. The receiver must accept `event_name` and `message` as URL query parameters; this helper does not send JSON. Use the dedicated Discord helper for Discord webhooks. |

Keep real tokens, webhook URLs, passwords, and your configured `run.py` private.
Restart the miner after changing its configuration. If a notification does not
arrive, check the selected event, credentials, destination permissions, and miner
logs. Matrix startup also reports unsuccessful login. Subscription notices are
about your own Twitch account; see [Subscription notifications](#subscription-notifications)
for the IRC and WebSocket paths.

## Docker and Docker Compose

Use Docker with the Compose v2 plugin. Run these commands from this repository
on the Docker host; Python does not need to be installed on that host. Compose
downloads the ready-to-run image from GitHub Container Registry:
`ghcr.io/armi1014/twitch-channel-points-miner-v2:latest`.
The published image supports 64-bit PCs/servers (`linux/amd64`) and 64-bit ARM
devices (`linux/arm64`). Each version is built and checked on its native platform.

```sh
cp example.py run.py
mkdir -p cookies logs
```

Edit `run.py`: set your Twitch username and channels or enable followed channels.
Leave optional notification blocks disabled until configured. Existing sessions
can be reused by copying `cookies/YOUR_USERNAME.pkl` into the new `cookies/`
directory. It must match the username in `run.py`.

Download the image, validate the Compose configuration,
then start in the foreground so you can see the first-login activation code:

```sh
docker compose pull
docker compose config --quiet
docker compose up
```

If there is no saved session, follow the activation instructions printed by the
miner. After login, cookies are saved in the mounted directory. Press Ctrl+C to
stop this foreground run, then start it in the background:

```sh
docker compose up -d
docker compose logs --tail 100 -f miner
```

On Windows PowerShell, use `Copy-Item example.py run.py` and
`New-Item -ItemType Directory -Force cookies, logs` for the preparation commands;
the Docker commands are the same.

The supplied [docker-compose.yml](docker-compose.yml) uses the published image,
which also supports Portainer deployments. Its persistent paths are:

| Host path | Container path | Access |
|---|---|---|
| `run.py` | `/usr/src/app/run.py` | Read-only configuration |
| `cookies/` | `/usr/src/app/cookies/` | Read/write saved login and drop claim state |
| `logs/` | `/usr/src/app/logs/` | Read/write logs, reports, and `logs/.state/` |

By default the host paths are beside the Compose file. Set `MINER_DATA_DIR` to
an existing data directory to use another location, or `MINER_IMAGE` to change
the image tag. Create `run.py`, `cookies/`, and `logs/` before starting; the mounts
deliberately fail on missing paths rather than turning a missing `run.py` into
a directory. The data directories must be writable by the container. Cookies
and logs are not baked into the image. Analytics is disabled in the example and
no inbound port is required for ordinary mining.

To stop or remove the container:

```sh
docker compose stop
docker compose down
```

Both commands preserve the host's cookies and logs. To install a newly published
image, download it and recreate the container without removing those directories:

```sh
docker compose pull
docker compose up -d --force-recreate
```

To build your own local changes instead, run
`docker build -t twitch-channel-points-miner:local .` and set
`MINER_IMAGE=twitch-channel-points-miner:local` before using Compose or Portainer.
Do not request a registry pull when using this local tag.

The **Publish Docker image** GitHub Actions workflow publishes images on pushes
to `master`, on `v*` version tags, or when started manually. It uses GitHub's
automatic token; no Docker Hub account or repository secrets are needed. A new
GHCR package initially has private visibility: its owner must change the package
to public once to allow downloads without signing in.

For a direct Docker run on Linux/macOS, using the same prepared files:

```sh
docker run --rm -it --init --stop-timeout 120 \
  --mount "type=bind,source=$PWD/run.py,target=/usr/src/app/run.py,readonly" \
  --mount "type=bind,source=$PWD/cookies,target=/usr/src/app/cookies" \
  --mount "type=bind,source=$PWD/logs,target=/usr/src/app/logs" \
  ghcr.io/armi1014/twitch-channel-points-miner-v2:latest
```

## Portainer

Use a **Docker Standalone** environment. Prepare a data directory on the Docker
host selected in Portainer, for example `/opt/twitch-miner`, containing configured `run.py`, `cookies/`,
and `logs/`. Paths refer to that Docker host, even when Portainer runs elsewhere
or you access it from your own PC. See [Docker's bind-mount documentation](https://docs.docker.com/engine/storage/bind-mounts/).

1. Open **Stacks → Add stack** and name it `twitch-miner`.
2. Paste the contents of [docker-compose.yml](docker-compose.yml) into the editor.
3. Add `MINER_DATA_DIR=/opt/twitch-miner` under the stack's environment variables.
   Keep the image's default GHCR tag, or set `MINER_IMAGE` to a specific version.
4. Deploy the stack and open the miner container's **Logs** to complete Twitch
   activation if needed. Portainer's **Console** is available for troubleshooting;
   no interactive console is required for device-code activation.
5. To update, pull the latest image and recreate the stack's container with the
   same environment values and mounts.

The Compose file has no `build` directive because Portainer's remote-environment
stack deployment does not support those steps. See [Portainer's known issue](https://docs.portainer.io/faqs/known-issues/docker-compose-files-including-build-steps-fail).
The same image and Compose configuration can be checked first with the CLI
before deploying through Portainer.

## What this fork improves

- Faster startup on medium and large channel lists.
- More resilient Twitch API, GQL, and WebSocket handling.
- Better watch streak behavior for already-online channels and delayed Twitch signals.
- Predictable favorite priority behavior.
- Drops inventory claiming and campaign matching that keep working through flaky Twitch campaign discovery.
- Cleaner Excel reports with daily, weekly, monthly, and yearly folders.
- Hidden local state files under `logs/.state/` so the root `logs/` folder stays cleaner.
- Notifications for your own subscriptions, confirmed bets, prediction results, and confirmed drop claims.

For feature details, see [FORK_FEATURES.md](FORK_FEATURES.md).

## Watch streaks

The miner now treats Twitch watch streaks conservatively:

- `WATCH` means normal watch points were awarded.
- A `WATCH_STREAK` reward or a milestone timestamp belonging to the current
  broadcast confirms completion, including after a miner restart.
- Otherwise, completion requires an increase in Twitch's streak day count.

Normal watch rewards alone do not confirm a streak. Unverified attempts are
limited to two per broadcast, with a cooldown between attempts.

More streak details are in [FAQ.md](FAQ.md).

## Weekly rewards and streak recovery

Weekly visits and missed-stream recovery are enabled by default, adapted from
[mpforce1's fork](https://github.com/mpforce1/Twitch-Channel-Points-Miner).
One background worker tries a clip first, then an accessible VOD for offline
channels. Successful playback requests alone never count as success: Twitch
must confirm the visit or restored streak.

- Weekly visits run only when Twitch reports an active event for your account
  and channel, with an unearned visit today. Completed or expired events stay
  idle. `Priority.WEEKLY_REWARDS` prioritizes eligible live channels; put it after
  `Priority.DROPS` to keep drop progress first.
- Recovery requires a streak of at least three broadcasts and an unexpired
  recovery window reported by Twitch. Only clips/VODs from the missed broadcast
  qualify. Recovery preserves the previous count and never claims the current
  live broadcast. Live channels continue through the normal streak watcher.
- Attempts are limited to 30 seconds for a clip and eight minutes for a VOD,
  with one job at a time and a one-hour cooldown per unsuccessful job. Deleted,
  unavailable, and subscriber-only VODs are skipped.

Disable either feature globally with `TwitchChannelPointsMiner(...,
weekly_rewards=False, watch_streak_recovery=False)`, or per channel with
`StreamerSettings(weekly_rewards=False, watch_streak_recovery=False)`.
Advanced limits use `RewardAutomationSettings` from
`TwitchChannelPointsMiner.classes.RewardAutomation`, passed as
`reward_automation_settings=RewardAutomationSettings(...)`.

These features depend on Twitch's eligibility and private APIs. See Twitch's
[weekly rewards rules](https://help.twitch.tv/s/article/weekly-rewards) and
[watch streak recovery rules](https://help.twitch.tv/s/article/recover-watch-streaks).

## Drops

Drops depend on two things:

- Twitch accepting playback/watch activity for the stream.
- Twitch GQL queries returning current inventory, campaign, and claim data.

This fork keeps drops claiming running when `claim_drops=True`, treats common Twitch campaign discovery failures as non-fatal, and uses fallback campaign matching when highlighted campaign IDs are missing.

The current drops-related Twitch GQL hashes are checked against live Twitch behavior and compared with [mpforce's working implementation](https://github.com/mpforce1/Twitch-Channel-Points-Miner). Twitch can still return transient `service timeout` or backend errors; those are Twitch-side and the miner should continue running.

## Subscription notifications

This fork can send `Events.SUBSCRIPTION` notifications to Discord or other webhook-style integrations.

It listens for:

- Twitch IRC `USERNOTICE` events.
- Twitch WebSocket gift-sub signals that can arrive even when the account is not present in chat.

It alerts only for subscription events about your own account:

- you subscribe
- you renew a subscription
- you receive a sub gift
- you upgrade a gift or Prime subscription

It ignores subscription events for other viewers.

Notes:

- IRC subscription notices still require chat to be enabled for that streamer.
- `chat=ChatPresence.NEVER` disables only the IRC subscription path for that channel.
- Websocket gift-sub notices use the same `Events.SUBSCRIPTION` message format and are locally deduped.

## Reports and state files

Reports are written under `logs/reports/` by period:

- `logs/reports/daily/`
- `logs/reports/weekly/`
- `logs/reports/monthly/`
- `logs/reports/yearly/`

Daily reports keep all point columns. Weekly, monthly, and yearly reports show only the point columns relevant to that period.

Local state files are kept in `logs/.state/`, including:

- watch streak cache
- daily points baselines
- subscription notification dedupe data
- pending predictions, confirmed results, and per-provider delivery receipts

Drop claim confirmation and duplicate protection are stored separately in
`cookies/<account>.drop-claims.json`, alongside the saved login session.

On first startup after updating, legacy state files from `logs/` are copied into `logs/.state/` automatically. The old files are left in place as backups.

Do not delete files inside `logs/.state/` unless you intentionally want to reset local report and watch streak history.

## Troubleshooting

- For setup and config questions, see [FAQ.md](FAQ.md).
- For feature details and reliability notes, see [FORK_FEATURES.md](FORK_FEATURES.md).
- For a complete runnable config, see [example.py](example.py).
- For contribution notes, see [CONTRIBUTING.md](CONTRIBUTING.md).

Common runtime notes:

- Occasional `503`, `service timeout`, or Twitch backend errors can happen and are usually transient.
- For debug logs, set `LoggerSettings` to `logging.DEBUG` and inspect the newest file under `logs/`.
- If drops stop progressing, first check whether Twitch is accepting playback and whether recent GQL hashes are still valid.

### View a background miner's live log

From the repository directory, open a separate terminal and run:

```sh
python scripts/watch_logs.py logs/YOUR_USERNAME.log
```

The viewer shows recent INFO messages, warnings, and errors, then follows new
records. Add `--debug` to include DEBUG records. It follows log rotation and miner
restarts. Closing the viewer leaves the background miner running; the viewer does
not start a second miner or send notifications.

## Links

- [Latest Releases](https://github.com/Armi1014/Twitch-Channel-Points-Miner-v2/releases)
- [Example Config](example.py)
- [FAQ](FAQ.md)
- [Fork Features](FORK_FEATURES.md)
- [Contributing](CONTRIBUTING.md)
- [License](LICENSE)

## Credits

This fork builds on the work of [Tkd-Alex](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2),
[rdavydov](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2), and
[mpforce1](https://github.com/mpforce1/Twitch-Channel-Points-Miner).
