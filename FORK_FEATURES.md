# Fork features

Armi1014's fork of Twitch Channel Points Miner focuses on reliable daily use.
Start with the [README](README.md) and [example configuration](example.py).

## Startup and connection handling

- Parallel channel initialization, with timeouts scaled to the channel count.
- Early exit when no valid channels remain after initialization.
- Hermes as the default WebSocket transport, with legacy PubSub available for troubleshooting.
- Retries and throttled logging for transient Twitch and connection failures.
- Defensive parsing of missing or incomplete GraphQL responses.

## Channel priorities

- `Priority.FAVORITE` and `StreamerSettings(favorite=True)` give important channels explicit priority.
- Watch streak candidates rotate to give other eligible channels a turn.
- Channel point limits skip completed targets while still allowing pending streak rewards.
- Priority order and per-channel settings remain configurable in `run.py`.

## Watch streaks and weekly rewards

- Watch streak state persists across restarts in `logs/.state/`.
- Twitch must provide qualifying evidence before a streak is marked complete.
  Normal watch points alone are insufficient.
- Unverified streak attempts are limited to two per broadcast, with cooldowns.
- Weekly visit rewards and missed-stream recovery use eligible clips or VODs,
  with time limits and cooldowns. Playback requests alone do not confirm success.
- Recovery preserves the previous streak; current live broadcasts use the normal watcher.

See [watch streaks](README.md#watch-streaks) and
[weekly rewards and streak recovery](README.md#weekly-rewards-and-streak-recovery)
for settings and Twitch-side limitations.

## Drops

- Inventory claiming continues when campaign discovery fails or channels are offline.
- Game and channel matching can use inventory campaigns when highlighted IDs are missing.
- Accepted claims remain pending until Twitch inventory confirms the claim.
- Pending claims retry at most once every 15 minutes.
- Per-account claim state in `cookies/<account>.drop-claims.json` prevents repeated
  success notifications across inventory syncs and restarts.

## Notifications

- Discord embed cards use English titles, event emojis, colors, timestamps,
  channel links, and structured fields. Plain text remains optional.
- Confirmed bets show the prediction, selected outcome, and stake.
- Results show stake, total payout, and net result; refunds preserve the original stake.
- Subscription notifications concern your own account and filter duplicate signals.
- Telegram, Gotify, Matrix, Pushover, and generic webhooks remain available.

See the [notification reference](README.md#notifications) for events and setup.

## Reports and deployment

- Optional local, read-only dashboard with channel tables, streak/recovery status,
  drops, predictions, redacted logs, saved views, and process resource usage.
- Twitch-backed refresh jobs shared across tabs, persisted cooldown, bounded
  extra reads, and visible rate-limit backoff.
- Dashboard history uses account-scoped SQLite storage and imports available
  legacy history without replaying notifications.

- Excel reports are grouped into daily, weekly, monthly, and yearly folders.
- Watch streak, report baseline, and subscription state live under `logs/.state/`.
- Python 3.10 or later is required; dependencies are declared in `pyproject.toml`.
- Prebuilt Docker images support 64-bit PCs, servers, and ARM devices through GHCR.
- Docker Compose preserves configuration, cookies, logs, and state on the host.

## Credits

This fork builds on [Tkd-Alex](https://github.com/Tkd-Alex/Twitch-Channel-Points-Miner-v2),
[rdavydov](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2), and
[mpforce1](https://github.com/mpforce1/Twitch-Channel-Points-Miner).
