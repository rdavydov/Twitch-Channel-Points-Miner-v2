#!/usr/bin/env python3
"""
Sets up, manages and health-checks the Twitch miner supervisor on Linux (systemd --user)
and macOS (launchd). The Python counterpart of MinerTask.ps1.

  install     : creates a venv (if the repo has none) and installs requirements, checks run.py and
                the login cookie, optionally sets up alerts (Apprise), then registers three jobs (the
                supervisor, a 30-minute health check, a daily points summary) and starts them.
  health      : HEALTHY / WARNING / DOWN report. Exit code 0 / 1 / 2.
                With --notify, sends an alert when the verdict changes (repeats DOWN every 6 h).
  status      : same as health.
  summary     : points earned per streamer, bets and uptime for the last --hours (default 24).
                With --notify, also sends it as a quiet alert.
  test-alert  : sends a test alert.
  start       : starts the supervisor service.
  stop        : stops the supervisor (the miner shuts down cleanly).
  uninstall   : stops everything and removes the three jobs (leaves the miner folder alone).

Linux: run `loginctl enable-linger $USER` (install tries it) so the jobs run without you logged in.
"""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from miner_common import (  # noqa: E402
    ALERT_CONFIG,
    SCRIPT_DIR,
    WRAPPER,
    Paths,
    default_miner_dir,
    find_python,
    format_age,
    iso,
    load_alert_config,
    newest_log,
    now,
    parse_time,
    pid_alive,
    read_json,
    rss_mb,
    send_alert,
    tail_lines,
    write_json,
)

SUPERVISOR = SCRIPT_DIR / "miner_supervisor.py"
CTL = Path(__file__).resolve()
LABEL = "twitch-miner"  # systemd unit prefix / launchd label suffix
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


# ---------------------------------------------------------------- service backends
class Systemd:
    unit_dir = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "systemd"
        / "user"
    )
    sup = f"{LABEL}-supervisor.service"
    health = f"{LABEL}-health"
    summary = f"{LABEL}-summary"

    @staticmethod
    def ctl(*a: str, check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["systemctl", "--user", *a], capture_output=True, text=True, check=check
        )

    def install(
        self,
        python: str,
        miner_dir: Path,
        health_minutes: int,
        summary_time: str,
        summary_hours: int,
    ) -> None:
        self.unit_dir.mkdir(parents=True, exist_ok=True)
        hh, mm = summary_time.split(":")
        q = lambda p: f'"{p}"'  # noqa: E731
        units = {
            self.sup: f"""
                [Unit]
                Description=Twitch Channel Points Miner supervisor
                After=network-online.target
                Wants=network-online.target

                [Service]
                ExecStart={q(python)} {q(SUPERVISOR)} --miner-dir {q(miner_dir)}
                WorkingDirectory={miner_dir}
                Restart=always
                RestartSec=300
                TimeoutStopSec=180
                KillMode=mixed

                [Install]
                WantedBy=default.target
                """,
            f"{self.health}.service": f"""
                [Unit]
                Description=Twitch miner health check

                [Service]
                Type=oneshot
                ExecStart={q(python)} {q(CTL)} health --notify --miner-dir {q(miner_dir)}
                SuccessExitStatus=1 2
                """,
            f"{self.health}.timer": f"""
                [Unit]
                Description=Twitch miner health check every {health_minutes} min

                [Timer]
                OnBootSec=10min
                OnUnitActiveSec={health_minutes}min

                [Install]
                WantedBy=timers.target
                """,
            f"{self.summary}.service": f"""
                [Unit]
                Description=Twitch miner daily summary

                [Service]
                Type=oneshot
                ExecStart={q(python)} {q(CTL)} summary --notify --hours {summary_hours} --miner-dir {q(miner_dir)}
                """,
            f"{self.summary}.timer": f"""
                [Unit]
                Description=Twitch miner daily summary at {summary_time}

                [Timer]
                OnCalendar=*-*-* {int(hh):02d}:{int(mm):02d}:00
                Persistent=true

                [Install]
                WantedBy=timers.target
                """,
        }
        for name, body in units.items():
            (self.unit_dir / name).write_text(
                textwrap.dedent(body).lstrip(), encoding="utf-8"
            )
        self.ctl("daemon-reload", check=True)
        self.ctl(
            "enable",
            "--now",
            self.sup,
            f"{self.health}.timer",
            f"{self.summary}.timer",
            check=True,
        )
        r = subprocess.run(
            ["loginctl", "enable-linger", getpass.getuser()],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(
                f"! Could not enable lingering ({r.stderr.strip()}). Without it the miner stops when you log out.\n"
                f"  Run: sudo loginctl enable-linger {getpass.getuser()}"
            )

    def uninstall(self) -> None:
        self.ctl(
            "disable",
            "--now",
            self.sup,
            f"{self.health}.timer",
            f"{self.summary}.timer",
        )
        for name in (
            self.sup,
            f"{self.health}.service",
            f"{self.health}.timer",
            f"{self.summary}.service",
            f"{self.summary}.timer",
        ):
            (self.unit_dir / name).unlink(missing_ok=True)
        self.ctl("daemon-reload")

    def start(self) -> None:
        self.ctl("start", self.sup, check=True)

    def stop(self) -> None:
        self.ctl("stop", self.sup)

    def state(self) -> tuple[bool | None, str]:
        """(running?, description). None = not installed."""
        if not (self.unit_dir / self.sup).exists():
            return None, f"systemd unit '{self.sup}' not installed"
        r = self.ctl("is-active", self.sup)
        active = r.stdout.strip()
        return active == "active", f"systemd unit '{self.sup}' is {active or 'unknown'}"


class Launchd:
    agent_dir = Path.home() / "Library" / "LaunchAgents"
    sup = f"com.{LABEL}.supervisor"
    health = f"com.{LABEL}.health"
    summary = f"com.{LABEL}.summary"

    @property
    def domain(self) -> str:
        return f"gui/{os.getuid()}"

    def plist(self, label: str) -> Path:
        return self.agent_dir / f"{label}.plist"

    @staticmethod
    def _plist(label: str, args: list[str], log_dir: Path, extra: str) -> str:
        from xml.sax.saxutils import escape

        arg_xml = "\n".join(f"        <string>{escape(a)}</string>" for a in args)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{arg_xml}
    </array>
    <key>StandardOutPath</key><string>{escape(str(log_dir / (label + '.out.log')))}</string>
    <key>StandardErrorPath</key><string>{escape(str(log_dir / (label + '.err.log')))}</string>
{extra}
</dict>
</plist>
"""

    def bootstrap(self, label: str) -> None:
        subprocess.run(
            ["launchctl", "bootout", f"{self.domain}/{label}"], capture_output=True
        )
        subprocess.run(
            ["launchctl", "bootstrap", self.domain, str(self.plist(label))], check=True
        )

    def install(
        self,
        python: str,
        miner_dir: Path,
        health_minutes: int,
        summary_time: str,
        summary_hours: int,
    ) -> None:
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        log_dir = Paths(miner_dir).log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        hh, mm = summary_time.split(":")
        jobs = {
            self.sup: (
                [python, str(SUPERVISOR), "--miner-dir", str(miner_dir)],
                "    <key>RunAtLoad</key><true/>\n    <key>KeepAlive</key><true/>\n"
                "    <key>ThrottleInterval</key><integer>300</integer>\n"
                "    <key>ExitTimeOut</key><integer>180</integer>",
            ),
            self.health: (
                [python, str(CTL), "health", "--notify", "--miner-dir", str(miner_dir)],
                f"    <key>StartInterval</key><integer>{health_minutes * 60}</integer>",
            ),
            self.summary: (
                [
                    python,
                    str(CTL),
                    "summary",
                    "--notify",
                    "--hours",
                    str(summary_hours),
                    "--miner-dir",
                    str(miner_dir),
                ],
                "    <key>StartCalendarInterval</key>\n    <dict><key>Hour</key>"
                f"<integer>{int(hh)}</integer><key>Minute</key><integer>{int(mm)}</integer></dict>",
            ),
        }
        for label, (args, extra) in jobs.items():
            self.plist(label).write_text(
                self._plist(label, args, log_dir, extra), encoding="utf-8"
            )
            self.bootstrap(label)
        print("Note: the jobs run while you are logged in to this Mac (LaunchAgents).")

    def uninstall(self) -> None:
        for label in (self.sup, self.health, self.summary):
            subprocess.run(
                ["launchctl", "bootout", f"{self.domain}/{label}"], capture_output=True
            )
            self.plist(label).unlink(missing_ok=True)

    def start(self) -> None:
        if not self.plist(self.sup).exists():
            sys.exit("Not installed. Run: minerctl.py install")
        self.bootstrap(self.sup)

    def stop(self) -> None:
        # KeepAlive would restart a killed supervisor, so unload it; `start` loads it again.
        subprocess.run(
            ["launchctl", "bootout", f"{self.domain}/{self.sup}"], capture_output=True
        )

    def state(self) -> tuple[bool | None, str]:
        if not self.plist(self.sup).exists():
            return None, f"launchd agent '{self.sup}' not installed"
        r = subprocess.run(
            ["launchctl", "print", f"{self.domain}/{self.sup}"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            return False, f"launchd agent '{self.sup}' is not loaded"
        m = re.search(r"^\s*state = (\S+)", r.stdout, re.M)
        st = m.group(1) if m else "unknown"
        return st == "running", f"launchd agent '{self.sup}' state {st}"


def backend():
    if IS_MAC:
        return Launchd()
    if IS_LINUX and shutil.which("systemctl"):
        return Systemd()
    sys.exit(
        "Unsupported platform: needs Linux with systemd, or macOS. On Windows use MinerTask.ps1."
    )


# ---------------------------------------------------------------- health
def get_health(p: Paths) -> dict:
    down, warn, note, info = [], [], [], []

    running, desc = (
        backend().state() if (IS_MAC or IS_LINUX) else (None, "no service manager")
    )
    if running is None:
        down.append(desc + ".")
    elif not running:
        down.append(desc + ".")

    st = read_json(p.status)
    if not st:
        down.append("No status.json - the supervisor has not written health data.")
    else:
        hb = parse_time(st.get("heartbeat"))
        if not hb or now() - hb > timedelta(minutes=3):
            down.append(
                f"Supervisor heartbeat is stale (last {format_age(hb)} ago) - hung or dead."
            )
        elif not pid_alive(st.get("supervisorPid")):
            down.append(f"Supervisor PID {st.get('supervisorPid')} is gone.")
        info.append(
            f"Supervisor: PID {st.get('supervisorPid')}, up {format_age(parse_time(st.get('supervisorStarted')))}, "
            f"heartbeat {format_age(hb)} ago"
        )

        state = st.get("minerState")
        if state == "running":
            mp = st.get("minerPid")
            if pid_alive(mp):
                ram = rss_mb(mp)
                info.append(
                    f"Miner: running, PID {mp}, up {format_age(parse_time(st.get('minerStarted')))}"
                    + (f", RAM {ram} MB" if ram is not None else "")
                )
            else:
                down.append(f"Miner PID {mp} is not running.")
        elif state == "crashed-waiting":
            since = parse_time(st.get("lastExitTime"))
            msg = f"Miner crashed (exit {st.get('lastExitCode')}) {format_age(since)} ago, waiting to restart."
            (down if since and now() - since > timedelta(minutes=20) else warn).append(
                msg
            )
        elif state == "restarting":
            info.append("Miner: in its scheduled restart.")
        else:
            down.append(f"Miner state: {state}.")

        cutoff = now() - timedelta(hours=24)
        recent = [
            c
            for c in (st.get("crashes") or [])
            if c and (parse_time(c.get("time")) or cutoff) > cutoff
        ]
        if recent:
            last = recent[-1]
            line = (
                f"{len(recent)} crash(es) in the last 24 h - last: exit {last.get('exitCode')} after "
                f"{last.get('ranMinutes')} min, {format_age(parse_time(last.get('time')))} ago."
            )
            (warn if len(recent) >= 3 else note).append(line)

        uc = parse_time(st.get("lastUpdateCheck"))
        if uc:
            res = st.get("lastUpdateResult") or ""
            info.append(f"Last update check: {format_age(uc)} ago - {res}")
            if re.search(r"failed|error|disabled|skipping", res, re.I):
                warn.append(f"Update problem: {res}")
            if now() - uc > timedelta(hours=26):
                warn.append(f"No update check for {format_age(uc)}.")
        if st.get("lastRollback"):
            rb_time, _, rb_what = str(st["lastRollback"]).partition("|")
            rbt = parse_time(rb_time)
            if rbt and rbt > cutoff:
                warn.append(
                    f"Bad update rolled back {format_age(rbt)} ago ({rb_what})."
                )
        if st.get("loginNeeded"):
            warn.append(f"Twitch login: {st['loginNeeded']}")

        la = parse_time(st.get("lastLogActivity"))
        if la:
            dbg = {
                True: "DEBUG level, freeze auto-restart on",
                False: "INFO level, freeze auto-restart off",
            }.get(st.get("logIsDebug"), "level not checked yet")
            info.append(f"Miner log last grew {format_age(la)} ago ({dbg})")
            if (
                now() - la > timedelta(hours=2)
                and state == "running"
                and not st.get("loginNeeded")
            ):
                warn.append(
                    f"Miner log hasn't grown for {format_age(la)} - it may be frozen."
                )
        info.append(
            f"Version: {st.get('version')} (good: {st.get('goodCommit')}) | Restarts: "
            f"{st.get('scheduledRestarts')} scheduled, {st.get('stallRestarts')} freeze | "
            f"Graceful stop: {st.get('gracefulStop')}"
        )
        info.append(f"Python: {st.get('pythonExe')}")

    err_re = re.compile(
        r"Traceback \(most recent call last\)|^\s*[\w.]+(Error|Exception)\b|\b(ERROR|CRITICAL)\b"
    )
    errs = [ln for ln in tail_lines(p.err_log, 500) if err_re.search(ln)]
    if errs:
        note.append(
            f"miner-stderr.log: {len(errs)} error line(s) this run. Latest: {errs[-1].strip()}"
        )

    latest = newest_log(p.miner_log_dir)
    if latest:
        log_errs = [
            ln
            for ln in tail_lines(latest, 1000)
            if re.search(r" - (ERROR|CRITICAL) - ", ln)
        ]
        if log_errs:
            note.append(
                f"{latest.name}: {len(log_errs)} ERROR line(s) in the last 1000. Latest: {log_errs[-1].strip()}"
            )

    verdict = "DOWN" if down else "WARNING" if warn else "HEALTHY"
    return {"verdict": verdict, "down": down, "warn": warn, "note": note, "info": info}


def cmd_health(p: Paths, notify: bool) -> int:
    h = get_health(p)
    if notify:
        prev = read_json(p.health_state) or {}
        prev_verdict = prev.get("verdict") or "HEALTHY"
        last_sent = parse_time(prev.get("lastNotified"))
        cfg = load_alert_config() or {}
        down_prio = int(cfg.get("downPriority", 2))
        send = h["verdict"] != prev_verdict or (
            h["verdict"] == "DOWN"
            and (not last_sent or now() - last_sent >= timedelta(hours=6))
        )
        if send:
            lines = h["down"] + h["warn"]
            if h["verdict"] == "DOWN":
                title, prio, body = "Miner DOWN", down_prio, "\n".join(lines)
            elif h["verdict"] == "WARNING":
                title, prio, body = "Miner warning", 0, "\n".join(lines)
            else:
                title, prio = "Miner recovered", -1
                body = f"Back to healthy (was {prev_verdict}).\n" + "\n".join(
                    h["info"][:2]
                )
            try:
                if send_alert(body, priority=prio, title=title):
                    last_sent = now()
            except Exception as e:
                print(f"Alert send failed: {e}", file=sys.stderr)
        write_json(
            p.health_state,
            {
                "verdict": h["verdict"],
                "checked": iso(),
                "lastNotified": iso(last_sent) if last_sent else None,
            },
        )

    if not notify or sys.stdout.isatty():
        color = {"HEALTHY": "32", "WARNING": "33", "DOWN": "31"}[h["verdict"]]
        tty = sys.stdout.isatty()
        c = (lambda code, s: f"\033[{code}m{s}\033[0m") if tty else (lambda code, s: s)
        print(f"\nMiner health: {c(color, h['verdict'])}")
        for s in h["down"]:
            print(c("31", f"  [X] {s}"))
        for s in h["warn"]:
            print(c("33", f"  [!] {s}"))
        for s in h["note"]:
            print(c("33", f"  [i] {s}"))
        for s in h["info"]:
            print(f"   -  {s}")
        issues = [
            ln
            for ln in tail_lines(p.supervisor_log, 300)
            if re.search(r"\[(WARN|ERROR)\]", ln)
        ][-5:]
        if issues:
            print("\n  Recent supervisor warnings/errors:")
            for ln in issues:
                print(f"    {ln}")
        print(f"\n  Logs: {p.log_dir}/   Miner logs: {p.miner_log_dir}/")
    return {"HEALTHY": 0, "WARNING": 1}.get(h["verdict"], 2)


# ---------------------------------------------------------------- summary
TS_RE = re.compile(r"^(\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
GAIN_RE = re.compile(
    r"\+(\d+) → (?:Streamer\(username=)?([^,\s(]+).*?Reason: ([A-Z_]+)"
)
BET_RE = re.compile(
    r"EventPrediction(?:\(event_id=[^,]*, streamer=Streamer\(username=|: )([^,\s(]+)"
    r".*Result: (WIN|LOSE|REFUND), \w+: ([+-]?[\d.]+)([kKMBT]?)"
)
MULT = {"": 1, "k": 1e3, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def fmt(n: float) -> str:
    s = f"{round(n):,}"
    return s if n < 0 else "+" + s


def get_summary(p: Paths, hours: int) -> str:
    from datetime import datetime

    since = (now() - timedelta(hours=hours)).replace(tzinfo=None)
    try:
        files = sorted(
            (
                f
                for f in p.miner_log_dir.iterdir()
                if f.is_file() and re.search(r"\.log(\.\d{4}-\d{2}-\d{2})?$", f.name)
            ),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[: -(-hours // 24) + 2]
    except OSError:
        files = []
    earned: dict[str, int] = {}
    bet_by: dict[str, float] = {}
    by_reason: dict[str, int] = {}
    wins = losses = refunds = 0
    first = None
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "Reason:" not in line and "Result:" not in line:
                        continue
                    m = TS_RE.match(line)
                    if not m:
                        continue
                    try:
                        t = datetime.strptime(m.group(1), "%d/%m/%y %H:%M:%S")
                    except ValueError:
                        continue
                    if t < since:
                        continue
                    first = t if first is None or t < first else first
                    g = GAIN_RE.search(line)
                    if g:
                        pts, who, why = int(g.group(1)), g.group(2), g.group(3)
                        if why == "PREDICTION":
                            continue  # bet payouts are counted from the Result lines (net of the stake)
                        earned[who] = earned.get(who, 0) + pts
                        by_reason[why] = by_reason.get(why, 0) + pts
                        continue
                    b = BET_RE.search(line)
                    if b:
                        who = b.group(1)
                        bet_by[who] = (
                            bet_by.get(who, 0.0) + float(b.group(3)) * MULT[b.group(4)]
                        )
                        wins += b.group(2) == "WIN"
                        losses += b.group(2) == "LOSE"
                        refunds += b.group(2) == "REFUND"
                        earned.setdefault(who, 0)
        except OSError:
            continue

    sum_earned = sum(earned.values())
    sum_bets = sum(bet_by.values())
    out = []
    window = (
        f"since {first:%a %H:%M} (logs start there)"
        if first and first > since + timedelta(minutes=30)
        else f"last {hours} h"
    )
    out.append(f"Net {fmt(sum_earned + int(sum_bets))} points, {window}")
    bet_line = (
        f"{fmt(sum_bets)} ({wins} won, {losses} lost, {refunds} refunded)"
        if wins + losses + refunds
        else "none"
    )
    out.append(f"Watching/claims: {fmt(sum_earned)}  Bets: {bet_line}")
    if earned:
        out.append("")
        rows = sorted(earned, key=lambda n: earned[n] + bet_by.get(n, 0), reverse=True)
        w = min(16, max(len(n) for n in rows))
        for name in rows[:12]:
            bets = f"  bets {fmt(bet_by[name])}" if bet_by.get(name) else ""
            out.append(f"{name[:w].ljust(w)} {fmt(earned[name]).rjust(8)}{bets}")
        if len(rows) > 12:
            out.append(f"... and {len(rows) - 12} more")
    else:
        out.append("No points logged in this window.")
    if by_reason:
        out.append("")
        out.append(
            "By type: "
            + ", ".join(
                f"{k} {fmt(v)}"
                for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])
            )
        )

    st = read_json(p.status)
    if st:
        aware_since = now() - timedelta(hours=hours)
        crashes = sum(
            1
            for c in (st.get("crashes") or [])
            if c and (parse_time(c.get("time")) or aware_since) > aware_since
        )
        up = (
            f"up {format_age(parse_time(st.get('minerStarted')))}"
            if st.get("minerStarted") and st.get("minerState") == "running"
            else f"state {st.get('minerState')}"
        )
        out.append("")
        out.append(f"Miner {up} | {crashes} crash(es) | version {st.get('version')}")
    return "\n".join(out)


# ---------------------------------------------------------------- install
def ensure_venv(miner_dir: Path) -> str:
    py = find_python(miner_dir)
    if py != sys.executable or (miner_dir / ".venv").exists():
        return py
    venv = miner_dir / ".venv"
    print(f"Creating virtual environment {venv} ...")
    r = subprocess.run([sys.executable, "-m", "venv", str(venv)])
    if r.returncode != 0:
        sys.exit(
            "Could not create the venv. On Debian/Ubuntu: sudo apt install python3-venv"
        )
    return find_python(miner_dir)


def cmd_install(p: Paths, args) -> int:
    be = backend()
    if not shutil.which("git"):
        print("! git not found - the supervisor will run but cannot update the miner.")
    elif not (p.miner_dir / ".git").exists():
        print(
            "! This folder is not a git checkout - automatic updates are disabled. Clone the repo with git to enable them."
        )
    if not p.entry.is_file():
        sys.exit(
            f"run.py not found in {p.miner_dir}. Copy example.py to run.py and set your username/streamers first."
        )
    if not WRAPPER.is_file():
        print(
            "! miner_wrapper.py not found next to this script - stops will use SIGINT directly."
        )

    python = args.python or ensure_venv(p.miner_dir)
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10+ is required.")
    print(f"Python: {python}")
    print("Installing requirements.txt ...")
    r = subprocess.run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-r",
            str(p.requirements),
        ]
    )
    if r.returncode != 0:
        sys.exit("pip install failed - fix the error above and run install again.")

    if not any(p.cookie_dir.glob("*.pkl")):
        print(
            "\nNo Twitch login cookie yet. Either run the miner once by hand to log in:\n"
            f"    cd {p.miner_dir} && {python} run.py\n"
            "or let the supervisor push the twitch.tv/activate code to your phone (needs alerts set up)."
        )

    if not ALERT_CONFIG.exists() and sys.stdin.isatty() and not args.no_prompt:
        print(
            "\nAlerts via Apprise (press Enter to skip). One URL per service, comma-separated, e.g.\n"
            "  pover://USER_KEY@APP_TOKEN   tgram://BOT_TOKEN/CHAT_ID   discord://WEBHOOK_ID/TOKEN   ntfy://topic\n"
            "Formats: https://github.com/caronc/apprise/wiki"
        )
        urls = [u.strip() for u in input("Apprise URL(s): ").split(",") if u.strip()]
        if urls:
            write_json(ALERT_CONFIG, {"appriseUrls": urls})
            os.chmod(ALERT_CONFIG, 0o600)
            print(
                f"Saved {ALERT_CONFIG} (mode 600). Test it with: minerctl.py test-alert"
            )

    p.log_dir.mkdir(parents=True, exist_ok=True)
    be.install(python, p.miner_dir, args.health_minutes, args.summary_time, args.hours)
    print(
        "\nInstalled and started. Checking health in a moment with: minerctl.py health"
    )
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "action",
        choices=[
            "install",
            "health",
            "status",
            "summary",
            "test-alert",
            "start",
            "stop",
            "uninstall",
        ],
    )
    ap.add_argument("--miner-dir", type=Path, default=default_miner_dir())
    ap.add_argument(
        "--python",
        default="",
        help="python for the miner (default: repo venv, created on install)",
    )
    ap.add_argument(
        "--notify",
        action="store_true",
        help="health/summary: send an alert (Apprise or Pushover)",
    )
    ap.add_argument(
        "--hours",
        type=int,
        default=24,
        help="summary window (the miner keeps 7 days of logs)",
    )
    ap.add_argument("--health-minutes", type=int, default=30)
    ap.add_argument(
        "--summary-time", default="08:57", help="HH:MM for the daily summary"
    )
    ap.add_argument(
        "--no-prompt",
        action="store_true",
        help="install: skip the alert setup question",
    )
    args = ap.parse_args()
    p = Paths(args.miner_dir)

    if args.action == "install":
        return cmd_install(p, args)
    if args.action in ("health", "status"):
        return cmd_health(p, args.notify)
    if args.action == "summary":
        text = get_summary(p, args.hours)
        print("\n" + text)
        if args.notify:
            cfg = load_alert_config() or {}
            try:
                if send_alert(
                    text,
                    priority=int(cfg.get("summaryPriority", -1)),
                    title=f"Miner summary ({args.hours} h)",
                    mono=True,
                ):
                    print("\nSent.")
            except Exception as e:
                print(f"Alert send failed: {e}", file=sys.stderr)
        return 0
    if args.action == "test-alert":
        if send_alert(
            f"Test from minerctl.py at {now():%H:%M:%S}.", title="Miner test"
        ):
            print("Sent.")
            return 0
        print(
            f'No alert config. Create {ALERT_CONFIG} with: {{"appriseUrls": ["pover://USER_KEY@APP_TOKEN"]}}'
        )
        return 1
    be = backend()
    if args.action == "start":
        be.start()
        print("Started.")
    elif args.action == "stop":
        be.stop()
        print("Stopped. The health check will report DOWN until you start it again.")
    elif args.action == "uninstall":
        be.uninstall()
        print(
            "Removed the supervisor, health check and summary jobs. Miner folder, cookies, logs and "
            "miner-alerts.json left in place."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
