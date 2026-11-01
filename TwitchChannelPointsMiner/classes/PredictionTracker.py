"""Durable, account-scoped bookkeeping for Twitch-confirmed predictions."""

import copy
import csv
import io
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, RLock, Thread

from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.utils import _millify

logger = logging.getLogger(__name__)
PROVIDERS = ("telegram", "discord", "webhook", "matrix", "pushover", "gotify")
RESULTS = {"WIN", "LOSE", "REFUND"}


def _points(value):
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _csv_value(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def _atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class PredictionTracker(Thread):
    def __init__(
        self, twitch, account, *, state_path=None, events=None, streamers=None
    ):
        super().__init__(name="Prediction reconciliation", daemon=True)
        self.twitch = twitch
        self.account = account.lower()
        self.account_id = None
        self.path = Path(state_path) if state_path else None
        self.events = events if events is not None else {}
        self.streamers = streamers if streamers is not None else []
        self.lock = RLock()
        self.wake = Event()
        self.stopping = Event()
        self.inflight = set()
        self.read_only = False
        self.reconcile_cursor = 0
        self.state = {
            "version": 1,
            "account": self.account,
            "events": {},
            "predictions": {},
            "intents": {},
        }
        if self.path and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if (
                    loaded.get("version") != 1
                    or loaded.get("account") != self.account
                    or any(
                        not isinstance(loaded.get(k), dict)
                        for k in ("events", "predictions", "intents")
                    )
                ):
                    raise ValueError("Invalid prediction state")
                if any(
                    not isinstance(v, dict)
                    for key in ("events", "predictions", "intents")
                    for v in loaded[key].values()
                ):
                    raise ValueError("Invalid prediction entry")
                for entry in loaded["predictions"].values():
                    if (
                        not all(
                            entry.get(k)
                            for k in ("event_id", "channel_id", "outcome_id", "source")
                        )
                        or _points(entry.get("points")) is None
                        or (
                            entry.get("result") is not None
                            and (
                                not isinstance(entry["result"], dict)
                                or entry["result"].get("type") not in RESULTS
                                or _points(entry["result"].get("points_won")) is None
                            )
                        )
                    ):
                        raise ValueError("Invalid prediction record")
                self.state = loaded
            except (OSError, ValueError, AttributeError):
                # Do not destroy an unreadable file, even when new events arrive.
                self.read_only = True
                logger.error(
                    "Cannot load prediction state; preserving the file and tracking in memory only"
                )

    def bind(self, streamers):
        self.streamers = streamers

    def _save(self):
        if not self.path or self.read_only:
            return
        try:
            _atomic_write(
                self.path, json.dumps(self.state, ensure_ascii=False, indent=2)
            )
        except OSError:
            logger.error(
                "Cannot save prediction state; restart recovery is not guaranteed"
            )
            return
        output = io.StringIO(newline="")
        columns = (
            "placed_at",
            "resolved_at",
            "channel",
            "prediction",
            "outcome",
            "stake",
            "result",
            "payout",
            "net",
            "source",
        )
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for record in self.state["predictions"].values():
            details = self._details(record)
            values = {
                "placed_at": record.get("predicted_at", ""),
                "resolved_at": record.get("resolved_at", ""),
                "channel": details.get("channel"),
                "prediction": details.get("prediction"),
                "outcome": details.get("outcome"),
                "stake": record["points"],
                "result": (record.get("result") or {}).get("type", "PENDING"),
                "payout": details.get("payout"),
                "net": details.get("net_points"),
                "source": details["source"],
            }
            writer.writerow({key: _csv_value(value) for key, value in values.items()})
        report = (
            self.path.parent.parent
            / "reports"
            / "predictions"
            / f"predictions.{self.path.stem.removeprefix('predictions.')}.csv"
        )
        try:
            _atomic_write(report, "\ufeff" + output.getvalue())
        except OSError:
            logger.warning("Cannot update prediction CSV; the durable state is saved")

    def remember_event(self, event_id, data, streamer=None):
        with self.lock:
            previous = self.state["events"].get(event_id, {})
            channel_id = str(
                data.get("channel_id")
                or (data.get("channel") or {}).get("id")
                or getattr(streamer, "channel_id", "")
                or previous.get("channel_id", "")
            )
            known_streamer = streamer or self._streamer(channel_id)
            updated = {
                "id": event_id,
                "channel_id": channel_id,
                "channel": data.get("channel_login")
                or getattr(known_streamer, "username", None)
                or previous.get("channel"),
                "title": data.get("title") or previous.get("title"),
                "status": data.get("status") or previous.get("status"),
                "outcomes": [
                    {k: outcome[k] for k in ("id", "title", "color") if k in outcome}
                    for outcome in (
                        data.get("outcomes") or previous.get("outcomes") or []
                    )
                    if isinstance(outcome, dict)
                ],
            }
            if updated != previous:
                self.state["events"][event_id] = updated
                self._save()

    def _remember_local_event(self, event_id):
        event = self.events.get(event_id)
        if event:
            self.remember_event(
                event_id,
                {
                    "title": event.title,
                    "status": event.status,
                    "outcomes": event.bet.outcomes,
                },
                event.streamer,
            )

    def register_intent(self, event, decision):
        with self.lock:
            if self.has_prediction(event.event_id):
                return False
            self.remember_event(
                event.event_id,
                {
                    "title": event.title,
                    "status": event.status,
                    "outcomes": event.bet.outcomes,
                },
                event.streamer,
            )
            self.state["intents"][event.event_id] = {
                "channel_id": str(event.streamer.channel_id),
                "points": decision["amount"],
                "outcome_id": decision["id"],
                "at": datetime.now(timezone.utc).isoformat(),
            }
            self._save()
            self.wake.set()
            return True

    def has_prediction(self, event_id):
        with self.lock:
            return event_id in self.state["predictions"]

    def _streamer(self, channel_id):
        return next(
            (s for s in self.streamers if str(s.channel_id) == str(channel_id)), None
        )

    def handle_user(self, payload, kind, *, recovered=False, notify=True):
        if not isinstance(payload, dict) or kind not in (
            "prediction-made",
            "prediction-result",
        ):
            return False
        event_id, outcome_id, channel_id = (
            payload.get(key) for key in ("event_id", "outcome_id", "channel_id")
        )
        stake = _points(payload.get("points"))
        if (
            not isinstance(event_id, str)
            or not event_id
            or not isinstance(outcome_id, str)
            or not outcome_id
            or isinstance(channel_id, bool)
            or not str(channel_id).isdigit()
            or stake is None
            or stake == 0
        ):
            logger.warning(
                "Ignoring incomplete Twitch prediction data; waiting for an authoritative snapshot"
            )
            return False
        if self.account_id is not None and payload.get("user_id") is not None:
            if str(payload["user_id"]) != str(self.account_id):
                return False
        result = payload.get("result")
        if result is not None:
            if not isinstance(result, dict) or result.get("type") not in RESULTS:
                return False
            payout = _points(result.get("points_won"))
            if result["type"] == "REFUND":
                payout = stake
            elif result["type"] == "LOSE":
                payout = 0
            elif payout is None:
                logger.warning(
                    "Prediction win is missing its payout; keeping it pending"
                )
                return False
            result = {"type": result["type"], "points_won": payout}
        elif kind == "prediction-result":
            return False

        with self.lock:
            previous = self.state["predictions"].get(event_id, {})
            # A delayed placement must never undo a settled result.
            if previous.get("result"):
                self.emit_pending()
                return True
            old_time, new_time = _timestamp(previous.get("updated_at")), _timestamp(
                payload.get("updated_at")
            )
            if old_time is not None and new_time is not None and new_time < old_time:
                return True
            self._remember_local_event(event_id)
            intent = self.state["intents"].get(event_id, {})
            origin = previous.get("source") or (
                "Miner"
                if intent.get("points") == stake
                and intent.get("outcome_id") == outcome_id
                else "Manual / external"
            )
            if previous and (
                previous.get("points") != stake
                or previous.get("outcome_id") != outcome_id
            ):
                if origin == "Miner":
                    origin = "Miner + manual / external"
            record = {
                **previous,
                "id": payload.get("id") or previous.get("id"),
                "event_id": event_id,
                "channel_id": str(channel_id),
                "outcome_id": str(outcome_id),
                "points": stake,
                "predicted_at": payload.get("predicted_at")
                or previous.get("predicted_at"),
                "updated_at": payload.get("updated_at") or previous.get("updated_at"),
                "source": origin,
            }
            if kind == "prediction-made" and result is None:
                record["placement_observed"] = True
                if not notify:
                    record["placement_suppressed"] = True
            if result:
                record["result"] = result
                record["resolved_at"] = (
                    payload.get("updated_at") or datetime.now(timezone.utc).isoformat()
                )
                record["result_recovered"] = recovered
                if not notify:
                    record["result_suppressed"] = True
                self.state["intents"].pop(event_id, None)
            self.state["predictions"][event_id] = record
            event = self.events.get(event_id)
            if event:
                event.bet_confirmed = event.bet_placed = True
                choice = next(
                    (
                        index
                        for index, outcome in enumerate(event.bet.outcomes)
                        if str(outcome.get("id")) == str(outcome_id)
                    ),
                    None,
                )
                event.bet.decision = {
                    "id": str(outcome_id),
                    "amount": stake,
                    "choice": choice,
                }
            self._save()
            if result:
                self._account_result(record, recovered)
            if notify:
                self.emit_pending()
            if not recovered:
                self.wake.set()
        return True

    def _account_result(self, record, recovered):
        streamer = self._streamer(record["channel_id"])
        # Catch-up from an earlier day belongs in the ledger, not today's session report.
        same_day = False
        try:
            settled = datetime.fromisoformat(
                record["resolved_at"].replace("Z", "+00:00")
            )
            same_day = settled.astimezone().date() == datetime.now().astimezone().date()
        except (KeyError, ValueError, TypeError):
            pass
        if streamer is not None and (not recovered or same_day):
            net = record["result"]["points_won"] - record["points"]
            streamer.update_history("PREDICTION", net)
        event = self.events.get(record["event_id"])
        if event:
            result = record["result"]
            net = result["points_won"] - record["points"]
            event.result = {
                "type": result["type"],
                "gained": net,
                "string": f"{result['type']}, Net: {_millify(net)}",
            }

    def _details(self, record):
        event = self.state["events"].get(record["event_id"], {})
        outcome = next(
            (
                o.get("title")
                for o in event.get("outcomes", [])
                if str(o.get("id")) == record["outcome_id"]
            ),
            None,
        )
        details = {
            "channel": event.get("channel"),
            "prediction": event.get("title"),
            "outcome": outcome,
            "stake": record["points"],
            "source": record["source"],
        }
        if record.get("result"):
            details.update(
                payout=record["result"]["points_won"],
                net_points=record["result"]["points_won"] - record["points"],
                recovered=record.get("result_recovered", False),
            )
        return details

    def _targets(self, event):
        settings = getattr(Settings, "logger", None)
        return [
            name
            for name in PROVIDERS
            if (provider := getattr(settings, name, None)) is not None
            and str(event) in getattr(provider, "events", [])
        ]

    def _ack(self, event_id, phase, provider):
        with self.lock:
            record = self.state["predictions"][event_id]
            sent = record.setdefault(phase + "_sent", [])
            if provider not in sent:
                sent.append(provider)
                self._save()

    def _finished(self, key):
        with self.lock:
            self.inflight.discard(key)

    def emit_pending(self):
        with self.lock:
            for event_id, record in list(self.state["predictions"].items()):
                details = self._details(record)
                if (
                    not details["channel"]
                    or not details["prediction"]
                    or not details["outcome"]
                ):
                    continue
                phases = []
                if record.get("placement_observed") and not record.get(
                    "placement_suppressed"
                ):
                    phases.append(("placement", Events.BET_PLACED))
                if record.get("result") and not record.get("result_suppressed"):
                    phases.append(
                        ("result", Events.get("BET_" + record["result"]["type"]))
                    )
                for phase, event in phases:
                    key = (event_id, phase)
                    if key in self.inflight:
                        continue
                    interested = self._targets(event)
                    expected = record.setdefault(phase + "_targets", interested)
                    targets = (set(expected) & set(interested)) - set(
                        record.get(phase + "_sent", [])
                    )
                    if record.get(phase + "_logged") and not targets:
                        continue
                    snapshot = copy.deepcopy(details)
                    if phase == "placement":
                        for field in ("payout", "net_points", "recovered"):
                            snapshot.pop(field, None)
                    first_log = not record.get(phase + "_logged")
                    record[phase + "_logged"] = True
                    self._save()
                    streamer = self._streamer(record["channel_id"])
                    if (
                        first_log
                        and streamer is not None
                        and getattr(Settings, "enable_analytics", False)
                        and not (phase == "result" and record.get("result_recovered"))
                    ):
                        try:
                            streamer.persistent_annotations(
                                "PREDICTION_MADE"
                                if phase == "placement"
                                else record["result"]["type"],
                                f"{details['prediction']} — {details['outcome']}",
                            )
                        except (OSError, ValueError) as error:
                            logger.warning(
                                "Prediction analytics update failed (%s)",
                                type(error).__name__,
                            )
                    self.inflight.add(key)
                    logger.info(
                        "Twitch prediction %s for %s: %s — %s, stake %s%s",
                        "confirmed"
                        if phase == "placement"
                        else record["result"]["type"],
                        details["channel"],
                        details["prediction"],
                        details["outcome"],
                        record["points"],
                        f", net {details['net_points']:+d}"
                        if phase == "result"
                        else "",
                        extra={
                            "event": event,
                            "emoji": ":dart:"
                            if phase == "placement"
                            else ":bar_chart:",
                            "discord_details": snapshot,
                            "notification_targets": targets,
                            "notification_ack": lambda provider, eid=event_id, p=phase: self._ack(
                                eid, p, provider
                            ),
                            "notification_finished": lambda k=key: self._finished(k),
                        },
                    )
                    if not targets:
                        self.inflight.discard(key)

    def reconcile_once(self):
        with self.lock:
            pending = {
                key: value["channel_id"]
                for key, value in self.state["predictions"].items()
                if not value.get("result")
                or any(
                    not self._details(value).get(field)
                    for field in ("channel", "prediction", "outcome")
                )
            }
            pending.update(
                {
                    key: value["channel_id"]
                    for key, value in self.state["intents"].items()
                    if key not in self.state["predictions"]
                }
            )
        candidates = list(pending.items())
        if candidates:
            start = self.reconcile_cursor % len(candidates)
            candidates = candidates[start:] + candidates[:start]
        deadline = time.monotonic() + 30
        for event_id, channel_id in candidates[:20]:
            if self.stopping.is_set():
                break
            self.reconcile_cursor += 1
            snapshot = self.twitch.get_prediction_snapshot(event_id, channel_id)
            if not isinstance(snapshot, dict) or snapshot.get("id") != event_id:
                if time.monotonic() >= deadline:
                    break
                continue
            self.remember_event(event_id, snapshot)
            prediction = snapshot.get("prediction")
            if isinstance(prediction, dict):
                self.handle_user(
                    prediction,
                    "prediction-result"
                    if prediction.get("result")
                    else "prediction-made",
                    recovered=True,
                )
            elif snapshot.get("status") in {"RESOLVED", "CANCELED"}:
                with self.lock:
                    self.state["intents"].pop(event_id, None)
                    self._save()
            if time.monotonic() >= deadline:
                break
        self.emit_pending()

    def summary(self, *, channel=None, source=None):
        with self.lock:
            records = [
                r
                for r in self.state["predictions"].values()
                if r.get("result")
                and (source is None or r["source"] == source)
                and (channel is None or self._details(r)["channel"] == channel)
            ]
            wins = sum(r["result"]["type"] == "WIN" for r in records)
            losses = sum(r["result"]["type"] == "LOSE" for r in records)
            return {
                "closed": len(records),
                "wins": wins,
                "losses": losses,
                "refunds": len(records) - wins - losses,
                "net": sum(r["result"]["points_won"] - r["points"] for r in records),
                "win_rate": wins / (wins + losses) if wins + losses else None,
            }

    def stop(self):
        self.stopping.set()
        self.wake.set()

    def run(self):
        while self.twitch.running and not self.stopping.is_set():
            self.wake.clear()
            try:
                self.reconcile_once()
            except Exception as error:
                logger.warning(
                    "Prediction reconciliation deferred (%s)", type(error).__name__
                )
            self.wake.wait(60)
            if not self.stopping.is_set():
                # Bursts of socket updates must not turn reconciliation into a tight API loop.
                self.stopping.wait(1)
