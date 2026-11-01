"""One asynchronous SQLite writer; bounded reads never scan the miner log."""

import hashlib
import json
import logging
import queue
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class DashboardStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Opening/migrating must fail visibly rather than replace an existing database.
        self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
        self.lock = threading.RLock()
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
        except Exception:
            self.db.close()
            raise
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise ValueError("Unsupported dashboard database version")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, at REAL NOT NULL, channel TEXT, kind TEXT NOT NULL,
                message TEXT NOT NULL, details TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_at ON events(at DESC);
            CREATE INDEX IF NOT EXISTS events_channel ON events(channel, at DESC);
            CREATE TABLE IF NOT EXISTS samples (
                channel TEXT NOT NULL, bucket INTEGER NOT NULL, resolution TEXT NOT NULL,
                first_at REAL NOT NULL, last_at REAL NOT NULL, first_balance INTEGER NOT NULL,
                balance INTEGER NOT NULL, low INTEGER NOT NULL, high INTEGER NOT NULL,
                PRIMARY KEY(channel,bucket,resolution));
            CREATE TABLE IF NOT EXISTS gains (
                id TEXT PRIMARY KEY, at REAL NOT NULL, channel TEXT NOT NULL,
                reason TEXT NOT NULL, amount INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS gains_at ON gains(at);
            PRAGMA user_version=1;
        """
        )
        self.db.commit()
        self.tasks = queue.Queue(maxsize=10000)
        self.failure = None
        self.closed = False
        self.thread = threading.Thread(
            target=self._writer, name="Dashboard history", daemon=True
        )
        self.thread.start()

    def enqueue(self, action, *args):
        if self.closed:
            return
        try:
            self.tasks.put_nowait((action, args))
        except queue.Full:
            self.failure = "History queue is full; some observations were not saved"

    def _writer(self):
        while True:
            item = self.tasks.get()
            try:
                if item is None:
                    return
                action, args = item
                with self.lock, self.db:
                    getattr(self, "_" + action)(*args)
            except Exception as exc:
                self.failure = f"History write failed ({type(exc).__name__})"
                logger.warning(self.failure)
            finally:
                self.tasks.task_done()

    def _metadata(self, key, value):
        self.db.execute(
            "INSERT OR REPLACE INTO metadata VALUES (?,?)", (key, json.dumps(value))
        )

    def metadata(self, key, default=None):
        with self.lock:
            row = self.db.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else default

    def event(
        self, kind, message, *, channel=None, details=None, at=None, identity=None
    ):
        at = time.time() if at is None else at
        identity = (
            identity
            or hashlib.sha256(f"{at}:{channel}:{kind}:{message}".encode()).hexdigest()
        )
        self.enqueue("event", identity, at, channel, kind, message, details or {})

    def _event(self, identity, at, channel, kind, message, details):
        self.db.execute(
            "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
            (identity, at, channel, kind, message, json.dumps(details)),
        )

    def gain(self, identity, at, channel, reason, amount):
        if (
            isinstance(amount, int)
            and not isinstance(amount, bool)
            and isinstance(reason, str)
            and reason not in {"PREDICTION", "REFUND"}
        ):
            self.enqueue("gain", identity, at, channel, reason, amount)

    def _gain(self, *values):
        self.db.execute("INSERT OR IGNORE INTO gains VALUES (?,?,?,?,?)", values)

    def sample(self, channel, balance, at=None):
        if isinstance(balance, int) and not isinstance(balance, bool):
            self.enqueue("sample", channel, balance, time.time() if at is None else at)

    def _sample(self, channel, balance, at):
        self.db.execute(
            """INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(channel,bucket,resolution) DO UPDATE SET
            first_balance=CASE WHEN excluded.first_at < first_at THEN excluded.first_balance ELSE first_balance END,
            balance=CASE WHEN excluded.last_at >= last_at THEN excluded.balance ELSE balance END,
            first_at=min(first_at,excluded.first_at), last_at=max(last_at,excluded.last_at),
            low=min(low,excluded.low), high=max(high,excluded.high)
        """,
            (
                channel,
                int(at // 60 * 60),
                "minute",
                at,
                at,
                balance,
                balance,
                balance,
                balance,
            ),
        )

    def compact(self, now=None):
        self.enqueue("compact", time.time() if now is None else now)

    def _compact(self, now):
        cutoff = int((now - 90 * 86400) // 3600 * 3600)
        # Keep real first/last values and exact extrema, never invent observations.
        rows = self.db.execute(
            "SELECT channel,first_at,last_at,first_balance,balance,low,high FROM samples WHERE resolution='minute' AND bucket<? ORDER BY first_at",
            (cutoff,),
        ).fetchall()
        groups = {}
        for channel, first, last, start, end, low, high in rows:
            key = (channel, int(first // 3600 * 3600))
            previous = groups.get(key)
            if previous:
                previous[1] = last
                previous[3] = end
                previous[4] = min(previous[4], low)
                previous[5] = max(previous[5], high)
            else:
                groups[key] = [first, last, start, end, low, high]
        for (channel, bucket), values in groups.items():
            previous = self.db.execute(
                "SELECT first_at,last_at,first_balance,balance,low,high FROM samples WHERE channel=? AND bucket=? AND resolution='hour'",
                (channel, bucket),
            ).fetchone()
            if previous:
                values = [
                    min(values[0], previous[0]),
                    max(values[1], previous[1]),
                    values[2] if values[0] < previous[0] else previous[2],
                    values[3] if values[1] >= previous[1] else previous[3],
                    min(values[4], previous[4]),
                    max(values[5], previous[5]),
                ]
            self.db.execute(
                "INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?)",
                (channel, bucket, "hour", *values),
            )
        # Daily records keep the same actual observation boundaries.
        rows = []
        for channel, day in {
            (channel, int(bucket // 86400 * 86400)) for channel, bucket in groups
        }:
            rows.extend(
                self.db.execute(
                    "SELECT channel,first_at,last_at,first_balance,balance,low,high FROM samples WHERE channel=? AND resolution='hour' AND bucket>=? AND bucket<? ORDER BY first_at",
                    (channel, day, day + 86400),
                ).fetchall()
            )
        days = {}
        for channel, first, last, start, end, low, high in rows:
            key = (channel, int(first // 86400 * 86400))
            if key in days:
                v = days[key]
                v[1] = last
                v[3] = end
                v[4] = min(v[4], low)
                v[5] = max(v[5], high)
            else:
                days[key] = [first, last, start, end, low, high]
        for (channel, bucket), values in days.items():
            self.db.execute(
                "INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?)",
                (channel, bucket, "day", *values),
            )
        self.db.execute(
            "DELETE FROM samples WHERE resolution='minute' AND bucket<?", (cutoff,)
        )

    def history(self, channel, start, end, limit=1200):
        with self.lock:
            # Bound chart resolution before transferring a long history.
            rows = self.db.execute(
                """WITH ranked AS (
                SELECT *, CAST(last_at / ? AS INTEGER) AS slot,
                    row_number() OVER (PARTITION BY CAST(last_at / ? AS INTEGER) ORDER BY last_at DESC) AS rank
                FROM samples WHERE channel=? AND last_at>=? AND last_at<=? AND resolution!='day'
                ) SELECT min(first_at),max(last_at),max(CASE WHEN rank=1 THEN balance END),min(low),max(high)
                  FROM ranked GROUP BY slot ORDER BY min(first_at) LIMIT ?""",
                (max(60, int((end - start) / max(1, limit))),) * 2
                + (channel, start, end, limit),
            ).fetchall()
        return [
            dict(at=r[1], start=r[0], balance=round(r[2]), low=r[3], high=r[4])
            for r in rows
        ]

    def events(self, *, channel=None, start=0, end=None, search="", limit=150):
        where = ["at>=?", "at<=?"]
        args = [start, time.time() if end is None else end]
        if channel:
            where.append("channel=?")
            args.append(channel)
        if search:
            where.append("(message LIKE ? OR kind LIKE ?)")
            args.extend(["%" + search[:200] + "%"] * 2)
        with self.lock:
            rows = self.db.execute(
                "SELECT id,at,channel,kind,message,details FROM events WHERE "
                + " AND ".join(where)
                + " ORDER BY at DESC LIMIT ?",
                (*args, min(500, limit)),
            ).fetchall()
        return [
            dict(
                id=r[0],
                at=r[1],
                channel=r[2],
                kind=r[3],
                message=r[4],
                details=json.loads(r[5]),
            )
            for r in rows
        ]

    def gains(self, start, end):
        with self.lock:
            return dict(
                self.db.execute(
                    "SELECT channel,sum(amount) FROM gains WHERE at>=? AND at<? GROUP BY channel",
                    (start, end),
                ).fetchall()
            )

    def balance_changes(self, start, end):
        with self.lock:
            rows = self.db.execute(
                """WITH ordered AS (
                SELECT channel,first_balance,first_at,balance,last_at,
                    row_number() OVER (PARTITION BY channel ORDER BY first_at) AS earliest,
                    row_number() OVER (PARTITION BY channel ORDER BY last_at DESC) AS latest
                FROM samples WHERE last_at>=? AND last_at<? AND resolution!='day'
                ) SELECT channel, max(CASE WHEN latest=1 THEN balance END)-max(CASE WHEN earliest=1 THEN first_balance END),
                    min(first_at),max(last_at) FROM ordered GROUP BY channel""",
                (start, end),
            ).fetchall()
        return {r[0]: dict(delta=r[1], since=r[2], until=r[3]) for r in rows}

    def flush(self):
        self.tasks.join()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.tasks.put(None)
        self.thread.join(timeout=10)
        if not self.thread.is_alive():
            with self.lock:
                self.db.close()
