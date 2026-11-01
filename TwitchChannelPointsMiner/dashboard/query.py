"""Shared read cache, single-flight requests, and observable Twitch backoff."""

import copy
import json
import logging
import threading
import time
from contextlib import contextmanager
from email.utils import parsedate_to_datetime

import requests

READS = {
    "ChannelPointsContext",
    "RewardList",
    "WeeklyVisitRewardsQuery",
    "VideoPlayerStreamInfoOverlayChannel",
    "WithIsStreamLiveQuery",
    "Inventory",
    "ViewerDropsDashboard",
    "DropCampaignDetails",
    "ChatRoomBanStatus",
    "ChannelFollows",
    "PredictionRecovery",
    "GetIDFromLogin",
}


def successful(result):
    return (
        isinstance(result, dict)
        and isinstance(result.get("data"), dict)
        and not result.get("errors")
    )


class ReadCoordinator:
    def __init__(
        self, interval=1, *, on_result=None, persisted=None, clock=time.time, wait=None
    ):
        self.interval = interval
        self.on_result = on_result
        self.clock = clock
        self.stopping = threading.Event()
        self.wait = wait or self.stopping.wait
        self.lock = threading.RLock()
        self.local = threading.local()
        self.cache = {}
        self.inflight = {}
        self.last_observer_request = 0
        self.backoff_until = float((persisted or {}).get("backoff_until", 0))
        self.strikes = int((persisted or {}).get("strikes", 0))
        self.requests = 0
        self.observer_requests = 0
        self.cache_hits = 0
        self.on_backoff = None
        self.last_miner_request = 0

    @contextmanager
    def observation(self):
        previous = getattr(self.local, "observing", False)
        self.local.observing = True
        try:
            yield
        finally:
            self.local.observing = previous

    def run(self, payload, callback):
        if (
            isinstance(payload, list)
            and payload
            and all(
                isinstance(p, dict) and p.get("operationName") in READS for p in payload
            )
        ):
            if getattr(self.local, "observing", False):
                raise ValueError("Dashboard reads must be individually rate limited")
            started = self.clock()
            result = callback()
            if isinstance(result, list) and len(result) == len(payload):
                for query, item in zip(payload, result):
                    if successful(item):
                        with self.lock:
                            self.cache[json.dumps(query, sort_keys=True)] = (
                                self.clock(),
                                copy.deepcopy(item),
                            )
                    if self.on_result:
                        try:
                            self.on_result(query, item, started, self.clock())
                        except Exception:
                            logging.getLogger(__name__).debug(
                                "Dashboard batch observation deferred", exc_info=True
                            )
            return result
        if not isinstance(payload, dict) or payload.get("operationName") not in READS:
            if getattr(self.local, "observing", False):
                raise ValueError("Dashboard request is not an allowlisted read")
            return callback()
        key = json.dumps(payload, sort_keys=True)
        with self.lock:
            entry = self.cache.get(key)
            if entry and self.clock() - entry[0] < 15:
                self.cache_hits += 1
                return copy.deepcopy(entry[1])
            pending = self.inflight.get(key)
            if pending is None:
                pending = self.inflight[key] = threading.Event()
                owner = True
            else:
                owner = False
        if not owner:
            while not pending.wait(0.1):
                if self.stopping.is_set():
                    raise requests.exceptions.ConnectionError("Dashboard is stopping")
            with self.lock:
                entry = self.cache.get(key)
                return copy.deepcopy(entry[1]) if entry else {}
        started = self.clock()
        try:
            result = callback()
            if successful(result):
                with self.lock:
                    self.cache[key] = (self.clock(), copy.deepcopy(result))
                    if len(self.cache) > 2000:
                        self.cache = {
                            k: v
                            for k, v in self.cache.items()
                            if self.clock() - v[0] < 60
                        }
            if self.on_result:
                try:
                    self.on_result(payload, result, started, self.clock())
                except Exception:
                    logging.getLogger(__name__).debug(
                        "Dashboard read observation deferred", exc_info=True
                    )
            return result
        finally:
            with self.lock:
                self.inflight.pop(key, None)
                pending.set()

    def before_request(self):
        observing = getattr(self.local, "observing", False)
        while not self.stopping.is_set():
            with self.lock:
                now = self.clock()
                delay = max(0, self.backoff_until - now)
                if observing:
                    delay = max(
                        delay,
                        self.last_observer_request + self.interval - now,
                        self.last_miner_request + 0.15 - now,
                    )
                if delay <= 0:
                    self.requests += 1
                    if observing:
                        self.last_observer_request = now
                        self.observer_requests += 1
                    else:
                        self.last_miner_request = now
                    return
            if self.wait(min(delay, 0.25)):
                break
        raise requests.exceptions.ConnectionError("Dashboard requests stopped")

    def response(self, response):
        if response.status_code == 429:
            now = self.clock()
            with self.lock:
                self.strikes += 1
                until = now + min(900, 60 * 2 ** min(self.strikes - 1, 10))
                retry = response.headers.get("Retry-After")
                if retry:
                    try:
                        until = max(until, now + float(retry))
                    except ValueError:
                        try:
                            until = max(until, parsedate_to_datetime(retry).timestamp())
                        except (TypeError, ValueError, OverflowError):
                            pass
                try:
                    until = max(
                        until, float(response.headers.get("Ratelimit-Reset", 0))
                    )
                except (TypeError, ValueError):
                    pass
                self.backoff_until = max(self.backoff_until, until)
            if self.on_backoff:
                self.on_backoff(self.status())

    def decoded(self, result):
        if successful(result):
            self.strikes = 0
            return
        if isinstance(result, dict) and any(
            (e.get("extensions") or {}).get("code")
            in {"RATE_LIMITED", "TOO_MANY_REQUESTS", "RATE_LIMIT_EXCEEDED"}
            for e in result.get("errors", [])
            if isinstance(e, dict)
        ):
            self.response(type("RateLimit", (), {"status_code": 429, "headers": {}})())

    def status(self):
        with self.lock:
            return dict(
                backoff_until=self.backoff_until,
                strikes=self.strikes,
                requests=self.requests,
                observer_requests=self.observer_requests,
                cache_hits=self.cache_hits,
            )

    def stop(self):
        self.stopping.set()
