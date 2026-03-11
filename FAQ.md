# FAQ

Common questions for this fork. For a full config example, see [example.py](example.py).

## Setup

### Where do I set favorites?

Inside `StreamerSettings`, for example:

```python
Streamer("name", settings=StreamerSettings(favorite=True))
```

### Where do I set streak wait time?

Set `watch_streak_min_offline_seconds` in `TwitchChannelPointsMiner(...)`.

- Default: `1800`
- Disable the offline wait: `0`

### Where do I set a points limit for watching?

Use `points_limit` inside `StreamerSettings`.

Global default in `run.py`:

```python
DEFAULT_STREAMER_SETTINGS = StreamerSettings(points_limit=50000)
```

Per-streamer override:

```python
Streamer("name", settings=StreamerSettings(points_limit=150000))
```

When a channel is already at or above its limit, the miner skips it and moves to the next eligible channel.
Pending watch streaks still bypass the limit so streak rewards are not missed.

## Startup And Streaks

### What happens to streamers already online at startup?

They are still checked. The miner can probe already-online channels for watch streak state, so startup does not skip them.

### Why is someone missing in `watch_streak_cache.<account>.json`?

That file is not a full streamer list. Entries appear when the miner creates or updates watch streak state for that streamer.

### Where do `Watchstreaks` values come from?

The export uses this order:

- cached Twitch streak days from the watch streak cache
- live Twitch data from `RewardList` when the cache has no day count yet
- cached local claimed streak session data as the final fallback

### Why might `Watchstreaks` be `0`?

Usually one of these:

- Twitch returned no streak day count
- There is no claimed streak session yet
- The channel currently has no active streak progress

## Export And Reporting

### Where is the Excel export written?

By default, the report is written to:

`logs/report_YYYY-MM-DD_<account>.xlsx`

### What do the main export columns mean?

- `Last Stream`: latest known stream date from live data or cached streak status
- `Banned`: whether your account is currently chat-banned in that channel
- `Watchstreaks`: the streak day count Twitch reports when available
- `Points gained`: points gained for the current day relative to that day's first seen total

### Does `Points gained` reset after restart?

Not on the same day. The miner stores the daily baseline in:

`logs/daily_points_baseline.<account>.json`

That lets the report keep counting forward across same-day restarts.
After updating from an older build, the first export rewrites that file into the new format, and then same-day restart carry-forward works from that point on.

### When does `Points gained` reset to `0`?

When the date changes and the miner rolls over to the new daily report file after midnight.

### Can ban detection work for offline channels?

Yes. The export can query Twitch directly for chat ban status, so a banned offline channel can still show `yes` in the startup export.

## Troubleshooting

### Why do I still see occasional `503` or `service timeout`?

Those are usually Twitch-side backend issues. The miner retries and suppresses common noise, but it cannot eliminate all upstream outages.

### How do I enable debug logging?

Set `LoggerSettings` to use `logging.DEBUG`, then inspect the newest file in `logs/`.
