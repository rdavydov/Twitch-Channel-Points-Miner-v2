# Feedback Audit (Armi1014 Mentions)

Date: 2026-03-01

Scope reviewed:
- https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/pull/753
- https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/pull/759
- https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/pull/785
- https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/pull/788
- https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2/issues/782
- Mention-linked legacy issues: #739, #748
- Mention-linked discussion: https://github.com/mpforce1/Twitch-Channel-Points-Miner/discussions/2

## Status Summary

- Fixed / implemented: 6
- Partially mitigated (Twitch-side limits): 1
- Unresolved review threads on #753/#759/#785/#788: 0

## Item-by-item

1) PR #753: reviewability + runtime stability
- Status: Fixed
- What was done:
  - Added line-ending guard to reduce mixed-format diffs: `.gitattributes`
  - Hardened runtime request handling and retry/backoff for transient DNS/connection-setup failures.
  - Added defensive websocket/pubsub behavior and watch-streak fallback logic.
  - Resolved all review threads on #753.
- Key files:
  - `TwitchChannelPointsMiner/classes/Twitch.py`
  - `TwitchChannelPointsMiner/classes/WebSocketsPool.py`
  - `.gitattributes`

2) PR #759: typed GQL feedback points
- Status: Covered for active code path / non-applicable for unmerged typed-layer specifics
- Notes:
  - Current fork path does not rely on the typed GQL integration from #759.
  - Stability concerns that apply to active path are implemented (HTTP status handling, invalid JSON handling, safer operation naming, retry/backoff, defensive parsing/logging).
  - Unmerged typed-layer-specific concerns (e.g., PEP 695 syntax in that branch, typed pagination model specifics) are not part of this fork runtime path.

3) PR #785: persisted query hash refresh
- Status: Fixed
- What was done:
  - Hash updates from #785 are already present in this fork constants.
- Key file:
  - `TwitchChannelPointsMiner/constants.py`

4) Issue #782: watch streak reliability
- Status: Fixed with mitigation limits
- What was done:
  - Added milestone-aware streak inference using `RewardList` + stream start timestamps.
  - Added reward-evidence completion (`2x WATCH`) for streak-state transitions.
  - Added rotation among eligible streak candidates to reduce starvation when many streamers go live at once.
  - Added/updated targeted tests.
- Key files:
  - `TwitchChannelPointsMiner/constants.py` (`RewardList`)
  - `TwitchChannelPointsMiner/classes/Twitch.py`
  - `TwitchChannelPointsMiner/classes/entities/Stream.py`
  - `TwitchChannelPointsMiner/classes/entities/Streamer.py`
  - `tests/test_watch_streak_milestones.py`
  - `tests/test_watch_streak_fallback.py`

5) PR #788 + user request for priority behavior and log noise
- Status: Fixed
- What was done:
  - Reduced watch-loop log spam and stabilized retry behavior.
  - Startup behavior improvements and safer initialization already in fork.
  - Implemented explicit favorite tier:
    - `Priority.FAVORITE`
    - `StreamerSettings.favorite`
  - Ensures requested policy can be configured directly: `STREAK -> FAVORITE -> ...`
- Key files:
  - `TwitchChannelPointsMiner/classes/Settings.py`
  - `TwitchChannelPointsMiner/classes/entities/Streamer.py`
  - `TwitchChannelPointsMiner/classes/Twitch.py`
  - `tests/test_priority_favorite.py`

6) Legacy mention-linked issues #739 and #748
- Status: Fixed/mitigated in current fork behavior
- Notes:
  - #739 (`NoneType`/stream info crash path): defensive stream info parsing and guards in active code path.
  - #748 (priority slot behavior): selection and tie-breaking logic has been reworked and regression-tested.

## Remaining limitation (external)

- Twitch watch-streak observability is still not fully deterministic for all channels/sessions.
- When milestone signals are unavailable/ambiguous, fallback heuristics are used (`WATCH` counters + bounded attempts/timeout).

## Verification

- Unit tests:
  - `python -m unittest discover -s tests -p 'test_*.py'`
  - Current status: passing
