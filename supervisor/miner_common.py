"""
Shared helpers for the Linux/macOS miner supervisor (miner_supervisor.py) and its
control script (minerctl.py). Standard library only; Python 3.10+.

The files written here (supervisor-logs/status.json, update-state.json, health-state.json)
use the same layout as the Windows PowerShell scripts, so either side can read them.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ALERT_CONFIG = SCRIPT_DIR / "miner-alerts.json"
WRAPPER = SCRIPT_DIR / "miner_wrapper.py"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def default_miner_dir() -> Path:
    """The repo this supervisor folder lives in, if it looks like the miner; else ~/Twitch-Channel-Points-Miner-v2."""
    parent = SCRIPT_DIR.parent
    if (parent / "TwitchChannelPointsMiner").is_dir():
        return parent
    return Path.home() / "Twitch-Channel-Points-Miner-v2"


class Paths:
    def __init__(self, miner_dir: Path, entry: str = "run.py"):
        self.miner_dir = Path(miner_dir).expanduser().resolve()
        self.entry = self.miner_dir / entry
        self.requirements = self.miner_dir / "requirements.txt"
        self.cookie_dir = self.miner_dir / "cookies"
        self.miner_log_dir = self.miner_dir / "logs"
        self.log_dir = self.miner_dir / "supervisor-logs"
        self.supervisor_log = self.log_dir / "supervisor.log"
        self.out_log = self.log_dir / "miner-stdout.log"
        self.err_log = self.log_dir / "miner-stderr.log"
        self.status = self.log_dir / "status.json"
        self.update_state = self.log_dir / "update-state.json"
        self.health_state = self.log_dir / "health-state.json"
        self.stop_flag = self.log_dir / "stop.flag"
        self.lock = self.log_dir / "supervisor.lock"


# ---------------------------------------------------------------- time / json
def now() -> datetime:
    return datetime.now().astimezone()


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat(timespec="seconds")


def parse_time(value) -> datetime | None:
    """Parses ISO timestamps from either the Python or the PowerShell scripts."""
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # PowerShell writes 7 fractional digits; Python accepts at most 6.
    if "." in s:
        head, _, rest = s.partition(".")
        digits = "".join(c for c in rest if c.isdigit())
        tz = rest[len(digits) :]
        s = f"{head}.{digits[:6]}{tz}" if digits else head + tz
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()


def format_age(since: datetime | None) -> str:
    if not since:
        return "?"
    s = now() - since
    secs = max(int(s.total_seconds()), 0)
    if secs >= 86400:
        return f"{secs // 86400}d {(secs % 86400) // 3600}h"
    if secs >= 3600:
        return f"{secs // 3600}h {(secs % 3600) // 60}m"
    return f"{secs // 60}m {secs % 60}s"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def write_json(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- Pushover
def load_alert_config() -> dict | None:
    cfg = read_json(ALERT_CONFIG)
    return cfg if isinstance(cfg, dict) else None


def _ssl_context() -> ssl.SSLContext:
    # python.org macOS builds ship without system CA certs; certifi comes with requests.
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v) for v in (value or []) if str(v).strip()]


def send_apprise(
    cfg: dict, msg: str, priority: int, title: str, url: str | None
) -> bool | None:
    """Sends through Apprise when miner-alerts.json has "appriseUrls". None = Apprise not configured.

    priority >= 1 goes to "appriseUrgentUrls" when set (e.g. pover://user@token?priority=emergency),
    otherwise to "appriseUrls".
    """
    normal = _as_list(cfg.get("appriseUrls"))
    urgent = _as_list(cfg.get("appriseUrgentUrls"))
    if not normal and not urgent:
        return None
    try:
        import apprise  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "appriseUrls is set but the 'apprise' package is missing (pip install apprise)"
        ) from e
    targets = urgent if priority >= 1 and urgent else (normal or urgent)
    client = apprise.Apprise()
    for u in targets:
        client.add(u)
    if len(client) == 0:
        raise RuntimeError("no valid Apprise URL in miner-alerts.json")
    notify_type = {2: apprise.NotifyType.FAILURE, 1: apprise.NotifyType.WARNING}.get(
        min(priority, 2), apprise.NotifyType.INFO
    )
    body = f"{msg}\n\n{url}" if url else msg
    if not client.notify(title=title, body=body, notify_type=notify_type):
        raise RuntimeError("Apprise could not deliver to one or more services")
    return True


def send_alert(
    msg: str,
    priority: int = 0,
    title: str = "Twitch miner",
    mono: bool = False,
    url: str | None = None,
    url_title: str | None = None,
) -> bool:
    """Sends an alert via Apprise ("appriseUrls") or Pushover ("pushoverToken"/"pushoverUser").
    Returns False when nothing is configured; raises on delivery errors.

    Priority: -1 quiet, 0 normal, 1 high (bypasses quiet hours),
    2 emergency (Pushover: repeats every 5 min for up to 1 h until acknowledged).
    """
    cfg = load_alert_config()
    if not cfg:
        return False
    if len(msg) > 1000:
        msg = msg[:1000] + "..."
    title = f"{title} ({socket.gethostname()})"
    sent = send_apprise(cfg, msg, priority, title, url)
    if sent is not None:
        return sent
    if not cfg.get("pushoverToken") or not cfg.get("pushoverUser"):
        return False
    body = {
        "token": cfg["pushoverToken"],
        "user": cfg["pushoverUser"],
        "title": title,
        "message": msg,
        "priority": priority,
    }
    if priority >= 2:
        body.update(retry=300, expire=3600)
    if cfg.get("device"):
        body["device"] = cfg["device"]
    if mono:
        body["monospace"] = 1
    if url:
        body["url"] = url
        if url_title:
            body["url_title"] = url_title
    req = urllib.request.Request(
        PUSHOVER_URL, data=urllib.parse.urlencode(body).encode()
    )
    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()):
        pass
    return True


# ---------------------------------------------------------------- python / processes
def find_python(miner_dir: Path) -> str:
    """Repo venv first (venv/, .venv/, env/), then the Python running this script."""
    for name in ("venv", ".venv", "env"):
        for exe in ("bin/python3", "bin/python", "Scripts/python.exe"):
            p = miner_dir / name / exe
            if p.is_file():
                return str(p)
    return sys.executable


def pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def rss_mb(pid) -> int | None:
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(int(pid))],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        return int(out.strip()) // 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def find_miner_pids(entry: Path) -> list[int]:
    """PIDs of python processes whose command line contains the miner's run.py path."""
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=15
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    me = {os.getpid(), os.getppid()}
    needle = str(entry)
    pids = []
    for line in out.splitlines():
        pid_s, _, cmd = line.strip().partition(" ")
        if (
            needle in cmd
            and "python" in cmd.lower()
            and "miner_supervisor" not in cmd
            and "minerctl" not in cmd
        ):
            try:
                pid = int(pid_s)
            except ValueError:
                continue
            if pid not in me:
                pids.append(pid)
    return pids


def kill_tree(pid: int) -> None:
    """SIGKILL the process group if the pid leads one (supervisor starts the miner in its own session), else the pid."""
    try:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGKILL)
            return
    except (ProcessLookupError, PermissionError):
        pass
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def tail_lines(path: Path, count: int) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, max(count * 400, 65536))
            f.seek(size - block)
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    lines = data.splitlines()
    if block < size and lines:
        lines = lines[1:]  # first line is probably partial
    return lines[-count:]


def newest_log(miner_log_dir: Path) -> Path | None:
    try:
        logs = [p for p in miner_log_dir.glob("*.log") if p.is_file()]
    except OSError:
        return None
    return max(logs, key=lambda p: p.stat().st_mtime, default=None)
