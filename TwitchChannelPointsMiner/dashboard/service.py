"""Observation lifecycle, snapshots, history, and account-wide refresh jobs."""

import copy
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psutil

from .query import ReadCoordinator
from .reader import normalize, operation, timestamp
from .security import redact
from .store import DashboardStore

logger = logging.getLogger(__name__)
GROUPS = {
    "ChannelPointsContext": "points",
    "VideoPlayerStreamInfoOverlayChannel": "stream",
    "RewardList": "streak",
    "WeeklyVisitRewardsQuery": "weekly",
    "ChatRoomBanStatus": "chat",
    "Inventory": "inventory",
    "ViewerDropsDashboard": "campaigns",
    "DropCampaignDetails": "campaign_details",
    "ChannelFollows": "follows",
}
FEATURES = (
    "make_predictions",
    "watch_streak",
    "watch_streak_recovery",
    "claim_drops",
    "weekly_rewards",
    "claim_moments",
    "follow_raid",
    "community_goals",
)


def plain(value):
    return getattr(value, "name", value) if value is not None else None


def safe_settings(settings):
    result = {
        key: getattr(settings, key, None)
        for key in (*FEATURES, "favorite", "points_limit")
    }
    result.update(
        chat=plain(getattr(settings, "chat", None)),
        playback_simulation=plain(getattr(settings, "playback_simulation", None)),
    )
    bet = getattr(settings, "bet", None)
    result["bet"] = {
        key: plain(getattr(bet, key, None))
        for key in (
            "strategy",
            "percentage",
            "percentage_gap",
            "max_points",
            "minimum_points",
            "stealth_mode",
            "delay",
            "delay_mode",
        )
    }
    condition = getattr(bet, "filter_condition", None)
    result["bet"]["filter"] = {
        key: plain(getattr(condition, key, None)) for key in ("by", "where", "value")
    }
    return result


class ActivityHandler(logging.Handler):
    def __init__(self, service):
        super().__init__(logging.INFO)
        self.service = service

    def emit(self, record):
        if record.name.startswith("TwitchChannelPointsMiner.dashboard"):
            return
        try:
            message = redact(record.getMessage())[:1500]
            details = getattr(record, "discord_details", {}) or {}
            channel = details.get("channel")
            self.service.store.event(
                str(getattr(record, "event", record.levelname)),
                message,
                channel=channel if isinstance(channel, str) else None,
                at=record.created,
                identity=hashlib.sha256(
                    f"{record.created}:{record.name}:{message}".encode()
                ).hexdigest(),
            )
        except Exception:
            # Logging and notification delivery must survive dashboard failure.
            pass


class DashboardService:
    def __init__(self, miner, settings, *, state_path=None, clock=time.time):
        self.miner = miner
        self.settings = settings
        self.clock = clock
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self.account = miner.username.lower()
        self.store = DashboardStore(
            state_path or Path("logs/.state") / f"dashboard.{self.account}.sqlite3"
        )
        self.remote = self.store.metadata("remote", {})
        self.remote_dirty = False
        self.refresh = self.store.metadata("refresh", {})
        if self.refresh.get("state") in {"running", "queued"}:
            self.refresh.update(
                state="interrupted",
                completed_at=self.clock(),
                next_manual_at=self.clock() + settings.cooldown_seconds,
                next_auto_at=self.clock() + settings.refresh_seconds,
            )
        self.refresh.setdefault("state", "idle")
        self.refresh.setdefault("next_manual_at", 0)
        self.refresh.setdefault("next_auto_at", 0)
        self.coordinator = ReadCoordinator(
            settings.request_interval_seconds,
            on_result=self.observe_response,
            persisted=self.store.metadata("backoff", {}),
            clock=clock,
        )
        self.coordinator.on_backoff = lambda state: self.store.enqueue(
            "metadata", "backoff", state
        )
        self.selection = []
        self.last_selection_at = None
        self.recovery_jobs = self.store.metadata("recovery_jobs", {})
        for job in self.recovery_jobs.values():
            if job.get("state") in {"trying", "clip", "vod", "verifying"}:
                job["state"] = "interrupted"
        self.prediction_reads = {}
        self.gain_baselines = self.store.metadata("gain_baselines", {})
        self.cached = {}
        self.last_live = {}
        self.process = psutil.Process()
        self.process.cpu_percent()
        self.started_at = self.clock()
        self.collector = threading.Thread(
            target=self._collect_loop, name="Dashboard snapshots", daemon=True
        )
        self.refresher = threading.Thread(
            target=self._refresh_loop, name="Dashboard Twitch refresh", daemon=True
        )
        self.log_handler = ActivityHandler(self)
        self.server = None
        self.last_failure = None
        self.last_watch_activity = {}

    def start(self):
        logging.getLogger().addHandler(self.log_handler)
        self.collector.start()
        self.refresher.start()

    def stop(self):
        if self.stopping.is_set():
            return
        self.stopping.set()
        self.wake.set()
        self.coordinator.stop()
        logging.getLogger().removeHandler(self.log_handler)
        if self.server:
            self.server.close()
        for thread in (self.refresher, self.collector):
            if thread.ident and thread is not threading.current_thread():
                thread.join(timeout=25)
        self.store.enqueue("metadata", "remote", self.remote)
        self.store.enqueue("metadata", "recovery_jobs", self.recovery_jobs)
        self.store.close()

    def observe_response(self, payload, response, started, finished):
        name = payload.get("operationName")
        group = GROUPS.get(name)
        if not group:
            return
        variables = payload.get("variables") or {}
        login = variables.get("channelLogin") or variables.get("channel")
        if not login:
            channel_id = str(
                variables.get("channelID") or variables.get("channelId") or ""
            )
            login = next(
                (
                    s.username
                    for s in list(self.miner.streamers)
                    if str(s.channel_id) == channel_id
                ),
                None,
            )
        login = str(login or "_account").lower()
        if name == "DropCampaignDetails":
            group += ":" + str(variables.get("dropID"))
            login = "_account"
        try:
            values = normalize(name, response)
        except (ValueError, TypeError, AttributeError, KeyError):
            with self.lock:
                self.remote_dirty = True
                entry = self.remote.setdefault(login, {}).setdefault(group, {})
                entry.update(error="Twitch data unavailable", attempted_at=finished)
            return
        with self.lock:
            # A later socket event wins over an older in-flight response.
            if started < self.last_live.get((login, group), 0):
                return
            self.remote.setdefault(login, {})[group] = dict(
                values, fetched_at=finished, source="Twitch", error=None
            )
            self.remote_dirty = True
        if group == "points":
            self.store.sample(login, values.get("points"), finished)

    def live_message(self, message, streamer=None):
        if streamer is None:
            return
        now = self.clock()
        login = streamer.username
        if message.topic == "community-points-user-v1" and message.type in {
            "points-earned",
            "points-spent",
        }:
            data = message.data
            balance = (data.get("balance") or {}).get("balance")
            if isinstance(balance, int):
                with self.lock:
                    self.remote_dirty = True
                    self.last_live[(login, "points")] = now
                    entry = self.remote.setdefault(login, {}).setdefault("points", {})
                    entry.update(
                        points=balance,
                        fetched_at=now,
                        source="Twitch live event",
                        error=None,
                    )
                at = timestamp(message.timestamp) or now
                self.store.sample(login, balance, at)
                gain = data.get("point_gain") or {}
                identity = hashlib.sha256(
                    json.dumps(
                        [login, message.timestamp, data], sort_keys=True
                    ).encode()
                ).hexdigest()
                if message.type == "points-earned":
                    self.store.gain(
                        identity,
                        at,
                        login,
                        gain.get("reason_code"),
                        gain.get("total_points"),
                    )
        if message.topic == "video-playback-by-id" and message.type in {
            "stream-up",
            "stream-down",
        }:
            with self.lock:
                self.remote_dirty = True
                self.last_live[(login, "stream")] = now
                entry = self.remote.setdefault(login, {}).setdefault("stream", {})
                entry.update(
                    online=message.type == "stream-up",
                    fetched_at=now,
                    source="Twitch live event",
                    error=None,
                )

    def event(self, kind, **details):
        now = self.clock()
        if kind == "watch_selection":
            self.selection = copy.deepcopy(details.get("channels", []))
            self.last_selection_at = now
            return
        if kind == "watch_request":
            self.last_watch_activity[details["channel"]] = now
            return
        channel = details.get("channel")
        message = details.pop("message", kind.replace("_", " ").capitalize())
        if kind.startswith("recovery_") or kind.startswith("weekly_"):
            with self.lock:
                key = f"{details.get('job_kind', 'recovery')}:{channel}"
                job = self.recovery_jobs.setdefault(key, {"channel": channel})
                job.update(details, at=now, state=kind.split("_", 1)[1])
                self.store.enqueue(
                    "metadata", "recovery_jobs", copy.deepcopy(self.recovery_jobs)
                )
        self.store.event(
            kind, redact(message), channel=channel, details=details, at=now
        )

    def request_refresh(self, automatic=False):
        with self.lock:
            if self.refresh["state"] in {"queued", "running"}:
                return copy.deepcopy(self.refresh)
            if self.clock() < self.refresh.get("next_manual_at", 0):
                return copy.deepcopy(self.refresh)
            self.refresh.update(
                id=str(uuid.uuid4()),
                state="queued",
                requested_at=self.clock(),
                automatic=automatic,
                completed=0,
                total=0,
                errors=[],
                current=None,
            )
            self.store.enqueue("metadata", "refresh", copy.deepcopy(self.refresh))
            self.wake.set()
            return copy.deepcopy(self.refresh)

    def refresh_status(self):
        with self.lock:
            return dict(copy.deepcopy(self.refresh), **self.coordinator.status())

    def _queue_automatic_refresh(self):
        ready = bool(
            self.miner.running
            and self.miner.streamers
            and self.miner.twitch.twitch_login.get_user_id()
        )
        if (
            ready
            and self.refresh["state"] not in {"running", "queued"}
            and self.clock() >= self.refresh.get("next_auto_at", 0)
        ):
            self.request_refresh(automatic=True)
        return ready

    def _refresh_loop(self):
        while not self.stopping.is_set():
            ready = self._queue_automatic_refresh()
            if ready and self.refresh["state"] == "queued":
                try:
                    self.refresh_once()
                except Exception as exc:
                    self._finish_refresh(f"Refresh interrupted ({type(exc).__name__})")
            self.wake.wait(1)
            self.wake.clear()

    def refresh_once(self):
        with self.lock:
            self.refresh.update(state="running", started_at=self.clock())
        selected = {s["channel"] for s in self.selection}
        channels = list(self.miner.streamers)

        def order(s):
            recovery = getattr(s, "streak_recovery", None)
            observed = (
                self.remote.get(s.username, {}).get("streak", {}).get("recovery") or {}
            )
            expiry = observed.get("expires_at") or getattr(recovery, "expires_at", None)
            eligible = observed.get("recoverable") or (
                recovery and recovery.recoverable()
            )
            return (
                0 if s.username in selected else 1 if eligible else 2,
                expiry or float("inf"),
                s.username,
            )

        tasks = []
        for streamer in sorted(channels, key=order):
            for name, variables in (
                ("ChannelPointsContext", {"channelLogin": streamer.username}),
                ("VideoPlayerStreamInfoOverlayChannel", {"channel": streamer.username}),
                ("RewardList", {"channelID": streamer.channel_id}),
                ("WeeklyVisitRewardsQuery", {"channelID": streamer.channel_id}),
                (
                    "ChatRoomBanStatus",
                    {
                        "channelID": streamer.channel_id,
                        "targetUserID": str(
                            self.miner.twitch.twitch_login.get_user_id()
                        ),
                    },
                ),
            ):
                tasks.append((streamer.username, name, operation(name, variables)))
        tasks.extend(
            ("_account", name, operation(name))
            for name in ("Inventory", "ViewerDropsDashboard")
        )
        # Campaign progress comes from Inventory. Also retrieve details for known active campaigns.
        campaign_ids = {
            c.id for s in channels for c in getattr(s.stream, "campaigns", [])
        }
        for campaign_id in sorted(campaign_ids):
            tasks.append(
                (
                    "_account",
                    "DropCampaignDetails",
                    operation(
                        "DropCampaignDetails",
                        {
                            "dropID": campaign_id,
                            "channelLogin": str(
                                self.miner.twitch.twitch_login.get_user_id()
                            ),
                        },
                    ),
                )
            )
        tracker = self.miner.prediction_tracker
        with tracker.lock:
            pending = [
                copy.deepcopy(r)
                for r in tracker.state["predictions"].values()
                if not r.get("result")
            ]
        with self.lock:
            self.refresh["total"] = len(tasks) + len(pending)
        with self.coordinator.observation():
            for login, name, payload in tasks:
                if self.stopping.is_set():
                    break
                with self.lock:
                    self.refresh["current"] = {
                        "channel": login,
                        "group": GROUPS.get(name, name),
                    }
                try:
                    result = self.miner.twitch.post_gql_request(payload)
                    # Validate semantic completeness, including a successful HTTP response with missing data.
                    normalize(name, result)
                except Exception as exc:
                    with self.lock:
                        self.refresh["errors"].append(
                            {
                                "channel": login,
                                "group": GROUPS.get(name, name),
                                "message": f"Data unavailable ({type(exc).__name__})",
                            }
                        )
                with self.lock:
                    self.refresh["completed"] += 1
            for record in pending:
                if self.stopping.is_set():
                    break
                try:
                    snapshot = self.miner.twitch.get_prediction_snapshot(
                        record["event_id"], record["channel_id"]
                    )
                    if not snapshot:
                        raise ValueError("Prediction unavailable")
                    with self.lock:
                        self.prediction_reads[record["event_id"]] = snapshot
                except Exception as exc:
                    with self.lock:
                        self.refresh["errors"].append(
                            {
                                "channel": record["channel_id"],
                                "group": "prediction",
                                "message": f"Data unavailable ({type(exc).__name__})",
                            }
                        )
                with self.lock:
                    self.refresh["completed"] += 1
            cursor = ""
            for _ in range(20):
                if self.stopping.is_set():
                    break
                with self.lock:
                    self.refresh["total"] += 1
                    self.refresh["current"] = {
                        "channel": "_account",
                        "group": "follows",
                    }
                try:
                    response = self.miner.twitch.post_gql_request(
                        operation(
                            "ChannelFollows",
                            {"limit": 100, "order": "ASC", "cursor": cursor},
                        )
                    )
                    follows = normalize("ChannelFollows", response)
                    self.follow_dates = {
                        **getattr(self, "follow_dates", {}),
                        **follows["follow_dates"],
                    }
                    if (
                        not follows["has_next"]
                        or not follows["cursor"]
                        or follows["cursor"] == cursor
                    ):
                        break
                    cursor = follows["cursor"]
                except Exception as exc:
                    with self.lock:
                        self.refresh["errors"].append(
                            {
                                "group": "follows",
                                "message": f"Follow dates unavailable ({type(exc).__name__})",
                            }
                        )
                    break
                finally:
                    with self.lock:
                        self.refresh["completed"] += 1
        self._finish_refresh()

    def _finish_refresh(self, error=None):
        with self.lock:
            now = self.clock()
            if error:
                self.refresh.setdefault("errors", []).append(
                    {"group": "refresh", "message": error}
                )
            self.refresh.update(
                state="interrupted"
                if self.stopping.is_set()
                else "partial"
                if self.refresh.get("errors")
                else "complete",
                completed_at=now,
                next_manual_at=now + self.settings.cooldown_seconds,
                next_auto_at=now + self.settings.refresh_seconds,
                current=None,
            )
            self.store.enqueue("metadata", "refresh", copy.deepcopy(self.refresh))
            self.store.enqueue("metadata", "remote", copy.deepcopy(self.remote))

    def _collect_loop(self):
        try:
            self.import_history()
        except Exception as exc:
            self.last_failure = f"History import incomplete ({type(exc).__name__})"
        last_compact = 0
        while not self.stopping.is_set():
            try:
                snapshot = self.build_snapshot()
                with self.lock:
                    self.cached = snapshot
                if self.last_failure and self.last_failure.startswith(
                    "Snapshot delayed"
                ):
                    self.last_failure = None
                if self.clock() - last_compact > 3600:
                    self.store.compact(self.clock())
                    last_compact = self.clock()
                with self.lock:
                    if self.remote_dirty:
                        self.store.enqueue(
                            "metadata", "remote", copy.deepcopy(self.remote)
                        )
                        self.remote_dirty = False
            except Exception as exc:
                self.last_failure = f"Snapshot delayed ({type(exc).__name__})"
            self.stopping.wait(self.settings.sample_seconds)

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.cached)
        result["refresh"] = self.refresh_status()
        return result

    def build_snapshot(self):
        now = self.clock()
        zone = ZoneInfo(self.settings.timezone)
        day = datetime.fromtimestamp(now, zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        gains = self.store.gains(day.timestamp(), (day + timedelta(days=1)).timestamp())
        balance_changes = self.store.balance_changes(
            day.timestamp(), (day + timedelta(days=1)).timestamp()
        )
        rows = []
        with self.lock:
            remote = copy.deepcopy(self.remote)
            jobs = copy.deepcopy(self.recovery_jobs)
        selection = {r["channel"]: r for r in self.selection}
        selection_current = (
            self.last_selection_at is not None and now - self.last_selection_at < 90
        )
        for streamer in list(self.miner.streamers):
            login = streamer.username
            groups = remote.get(login, {})
            values = {
                k: v
                for group in groups.values()
                for k, v in group.items()
                if k not in {"fetched_at", "source", "error", "attempted_at"}
            }
            cache = getattr(self.miner, "watch_streak_cache", None)
            status = (
                cache.get_streamer_status(login, account_name=self.account)
                if cache
                else None
            )
            session = (
                cache.latest_session_for_streamer(login, account_name=self.account)
                if cache
                else None
            )
            points = values.get("points")
            if points is None and streamer.channel_points_context_at:
                points = streamer.channel_points
            online = values.get("online", streamer.is_online)
            streak = values.get("streak", getattr(status, "watch_streak_days", None))
            recovery = values.get("recovery")
            r = getattr(streamer, "streak_recovery", None)
            if "recovery" not in values and r:
                recovery = dict(
                    days=r.streak_days,
                    expires_at=r.expires_at,
                    missed_broadcasts=sorted(r.missed_broadcasts),
                    recoverable=r.recoverable(now),
                )
            recoverable = bool(
                recovery
                and recovery.get("missed_broadcasts")
                and recovery.get("expires_at", 0) > now
                and recovery.get("days", 0) >= 3
            )
            if recovery:
                recovery["recoverable"] = recoverable
            broadcast = values.get("broadcast_id") or streamer.stream.broadcast_id
            fulfilled = bool(
                online
                and broadcast
                and broadcast == streamer.stream.broadcast_id
                and streamer.stream.watch_streak_missing is False
            )
            achieved = values.get("streak_achieved_at")
            started = values.get("stream_started_at") or streamer.stream.created_at
            if online and achieved and started and achieved > started:
                fulfilled = True
            if (
                online
                and broadcast
                and session
                and session.claimed
                and session.broadcast_id == broadcast
            ):
                fulfilled = True
            watching = login in selection and selection_current and self.miner.running
            baseline_key = day.strftime("%Y-%m-%d") + ":" + login
            baseline = self.gain_baselines.get(baseline_key, 0)
            # Captured watch/claim/raid gains exclude prediction payouts and manual spending.
            earned = gains.get(login, 0) + baseline
            row = dict(
                channel=login,
                channel_id=str(streamer.channel_id),
                points=points,
                earned_today=earned,
                online=online,
                watching=watching,
                balance_change=balance_changes.get(login, {}).get("delta"),
                balance_observed_since=balance_changes.get(login, {}).get("since"),
                reported_period_points={
                    period: values.get(login)
                    for period, values in getattr(
                        self.miner, "period_points_snapshot", {}
                    ).items()
                },
                reason=selection.get(login, {}).get("reason")
                if watching
                else "Offline"
                if not online
                else "Waiting for a watch slot",
                favorite=bool(streamer.settings.favorite),
                streak=streak,
                streak_status="Confirmed"
                if fulfilled
                else "In progress"
                if online and watching and streamer.settings.watch_streak
                else "Pending"
                if online and streamer.settings.watch_streak
                else "Offline"
                if not online
                else "Disabled",
                recovery=recovery,
                recoverable=recoverable,
                recovery_job=jobs.get("recovery:" + login),
                weekly=values.get("weekly"),
                subscription_tier=values.get(
                    "subscription_tier", streamer.subscription_tier
                ),
                chat_banned=values.get("chat_banned", streamer.chat_banned),
                points_limit=streamer.settings.points_limit,
                last_activity=self.last_watch_activity.get(login),
                follow_date=getattr(self, "follow_dates", {}).get(
                    login,
                    (getattr(self.miner, "streamer_follow_dates", {}) or {}).get(login),
                ),
                title=values.get("title", streamer.stream.title),
                game=values.get("game", (streamer.stream.game or {}).get("name")),
                viewers=values.get("viewers", streamer.stream.viewers_count),
                stream_started_at=values.get(
                    "stream_started_at", streamer.stream.created_at
                ),
                settings=safe_settings(streamer.settings),
                freshness={
                    g: dict(
                        checked_at=v.get("fetched_at"),
                        source=v.get("source", "Twitch"),
                        error=v.get("error"),
                        stale=not v.get("fetched_at")
                        or now - v.get("fetched_at", 0)
                        > self.settings.refresh_seconds + 60,
                    )
                    for g, v in groups.items()
                },
                attempts=getattr(session, "attempts", 0),
                verified_streak=getattr(session, "verified_streak_days", None),
                last_verification_at=getattr(session, "last_verification_at", None),
            )
            row["needs_attention"] = (
                recoverable
                or bool(online and streamer.settings.watch_streak and not fulfilled)
                or any(v["error"] for v in row["freshness"].values())
            )
            rows.append(row)
        predictions = self.predictions()
        closed = [p for p in predictions if p.get("result")]
        wins = sum(p["result"] == "WIN" for p in closed)
        losses = sum(p["result"] == "LOSE" for p in closed)
        account_data = remote.get("_account", {})
        drops = {
            str(d["id"]): d
            for g, v in account_data.items()
            if g.startswith("campaign_details:")
            for d in v.get("drops", [])
        }
        drops.update(
            {
                str(d["id"]): d
                for d in account_data.get("inventory", {}).get("drops", [])
            }
        )
        pools = (
            getattr(self.miner.ws_pool, "clients", [])
            if getattr(self.miner, "ws_pool", None)
            else []
        )
        connections = [
            dict(
                name=f"Twitch connection {i+1}",
                state=plain(getattr(c, "state", "Unknown")),
            )
            for i, c in enumerate(list(pools))
        ]
        settings = safe_settings(
            getattr(
                __import__(
                    "TwitchChannelPointsMiner.classes.Settings", fromlist=["Settings"]
                ),
                "Settings",
            ).streamer_settings
        )
        return dict(
            account=self.account,
            generated_at=now,
            timezone=self.settings.timezone,
            running=bool(self.miner.running),
            session_id=self.miner.session_id,
            uptime=now - self.miner.start_datetime.timestamp()
            if self.miner.start_datetime
            else 0,
            channels=rows,
            predictions=predictions,
            drops=list(drops.values()),
            campaigns=account_data.get("campaigns", {}).get("campaigns", []),
            account_freshness={
                g: {k: v.get(k) for k in ("fetched_at", "error", "source")}
                for g, v in account_data.items()
            },
            summary=dict(
                online=sum(bool(r["online"]) for r in rows),
                watching=sum(r["watching"] for r in rows),
                balance=sum(r["points"] for r in rows if r["points"] is not None),
                earned_today=sum(r["earned_today"] for r in rows),
                recoverable=sum(r["recoverable"] for r in rows),
                confirmed=sum(r["streak_status"] == "Confirmed" for r in rows),
                wins=wins,
                losses=losses,
                refunds=len(closed) - wins - losses,
                net=sum(p["net"] for p in closed),
                win_rate=wins / (wins + losses) if wins + losses else None,
            ),
            system=dict(
                cpu_percent=self.process.cpu_percent(),
                memory_mb=round(self.process.memory_info().rss / 1024**2, 1),
                threads=self.process.num_threads(),
                connections=connections,
                history_error=self.store.failure or self.last_failure,
                refresh_seconds=self.settings.refresh_seconds,
                cooldown_seconds=self.settings.cooldown_seconds,
                request_interval_seconds=self.settings.request_interval_seconds,
                selection_at=self.last_selection_at,
                priorities=[plain(p) for p in self.miner.priority],
                streak_slots=self.miner.watch_streak_max_parallel,
                settings=settings,
                capture_started_at=self.store.metadata(
                    "capture_started_at", self.started_at
                ),
            ),
        )

    def predictions(self):
        tracker = self.miner.prediction_tracker
        with tracker.lock:
            state = copy.deepcopy(tracker.state)
        rows = []
        for event_id, record in state["predictions"].items():
            event = state["events"].get(event_id, {})
            read = self.prediction_reads.get(event_id) or {}
            result = record.get("result") or (read.get("prediction") or {}).get(
                "result"
            )
            outcome = next(
                (
                    o.get("title")
                    for o in event.get("outcomes", [])
                    if str(o.get("id")) == record["outcome_id"]
                ),
                None,
            )
            rows.append(
                dict(
                    id=event_id,
                    channel=event.get("channel"),
                    prediction=event.get("title"),
                    outcome=outcome,
                    stake=record["points"],
                    result=result.get("type") if result else None,
                    payout=result.get("points_won") if result else None,
                    net=result["points_won"] - record["points"] if result else None,
                    source=record["source"],
                    placed_at=timestamp(record.get("predicted_at")),
                    resolved_at=timestamp(record.get("resolved_at")),
                    recovered=record.get("result_recovered", False),
                    notification_sent="discord" in record.get("result_sent", []),
                )
            )
        return sorted(rows, key=lambda p: p["placed_at"] or 0, reverse=True)

    def import_history(self):
        if self.store.metadata("history_imported"):
            return
        self.store.enqueue("metadata", "capture_started_at", self.clock())
        # The source files are read only. No notification or claim path is called.
        folder = Path("analytics") / self.account
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            if path.stat().st_size > 50 * 1024 * 1024:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for point in data.get("series", []):
                if isinstance(point.get("y"), int) and isinstance(
                    point.get("x"), (int, float)
                ):
                    self.store.sample(path.stem, point["y"], point["x"] / 1000)
            for point in data.get("annotations", []):
                if isinstance(point.get("x"), (int, float)):
                    text = redact(
                        (point.get("label") or {}).get("text", "Historical event")
                    )
                    self.store.event(
                        "imported",
                        text,
                        channel=path.stem,
                        at=point["x"] / 1000,
                        identity=f"analytics:{path.stem}:{point['x']}:{hashlib.sha256(text.encode()).hexdigest()}",
                    )
        for prediction in self.predictions():
            self.store.event(
                "prediction_" + (prediction["result"] or "pending").lower(),
                f"{prediction['prediction'] or 'Prediction'}: {prediction['outcome'] or 'Unknown outcome'}",
                channel=prediction["channel"],
                at=prediction["resolved_at"] or prediction["placed_at"] or self.clock(),
                details=prediction,
                identity="prediction:" + prediction["id"],
            )
        cache = getattr(self.miner, "watch_streak_cache", None)
        if cache:
            for session in cache.snapshot_sessions(account_name=self.account):
                at = (
                    (
                        session.get("last_verification_at")
                        or session.get("last_evidence_at")
                    )
                    if session.get("claimed")
                    else session.get("last_attempt_at")
                )
                if at:
                    self.store.event(
                        "streak_confirmed"
                        if session.get("claimed")
                        else "streak_attempt",
                        "Imported Twitch-confirmed watch streak"
                        if session.get("claimed")
                        else "Imported watch streak attempt",
                        channel=session["streamer_login"],
                        at=at,
                        details=session,
                        identity=f"streak:{session['broadcast_id']}:{session['streamer_login']}:{bool(session.get('claimed'))}",
                    )
        self.store.enqueue("metadata", "history_imported", True)

    def logs(self, cursor="", debug=False):
        path = Path(self.miner.logs_file) if self.miner.logs_file else None
        if path is None or not path.exists():
            return dict(lines=[], cursor="", message="No log file is available")
        stat = path.stat()
        identity = f"{stat.st_dev}.{stat.st_ino}"
        try:
            old_identity, offset, previous_level = cursor.split(":")
            offset = int(offset)
            if old_identity != identity or offset < 0 or offset > stat.st_size:
                raise ValueError()
        except (ValueError, AttributeError):
            offset = max(0, stat.st_size - 128 * 1024)
            previous_level = "DEBUG"
        # Same sharing flags as the desktop console; Windows rotation remains possible.
        from .files import open_log

        with open_log(path) as source:
            source.seek(offset)
            data = source.read(128 * 1024)
        read_size = len(data)
        if offset and not cursor:
            data = data.partition(b"\n")[2]
        complete, _, partial = data.rpartition(b"\n")
        new_offset = offset + read_size - len(partial)
        lines = []
        for line in complete.decode("utf-8", "replace").splitlines():
            match = re.match(
                r"^(\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - .*? - \[[^]]+\]: (.*)$",
                line,
            )
            if match:
                at, previous_level, message = match.groups()
            else:
                at, message = None, line
            if debug or previous_level in {"INFO", "WARNING", "ERROR", "CRITICAL"}:
                lines.append(
                    dict(at=at, level=previous_level, message=redact(message)[:4000])
                )
        return dict(
            lines=lines[-300:], cursor=f"{identity}:{new_offset}:{previous_level}"
        )
