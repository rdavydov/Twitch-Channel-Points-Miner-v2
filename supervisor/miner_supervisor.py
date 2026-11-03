#!/usr/bin/env python3
"""
Supervisor for Twitch-Channel-Points-Miner-v2 on Linux and macOS
(the Python counterpart of MinerSupervisor.ps1). Started by systemd or launchd via minerctl.py.

Runs forever and:
  - Checks the git remote for updates every --update-hours (default 24), fast-forwards the checkout,
    and reinstalls requirements.txt only when it changed.
  - Rolls back a bad update: if a commit that has never run 30 min cleanly crashes 3 times within
    30 min, it resets to the last good commit (keeping your local edits) and skips the bad one.
  - Starts run.py through miner_wrapper.py, output captured to supervisor-logs/.
  - Restarts every --restart-hours (default 24) gracefully (the miner's own Ctrl+C shutdown),
    force-killing only if it takes longer than --graceful-seconds.
  - Restarts on crash with backoff (30 s doubling up to 15 min).
  - Restarts a frozen miner: if its log (DEBUG file level) stops growing for --stall-minutes.
  - Twitch login: when the saved login is rejected (ERR_BADAUTH) it moves the cookie aside and
    restarts; when the miner asks for a twitch.tv/activate code it pushes the code to your phone,
    and gets a fresh code when it expires (3 tries, then every 6 h).
  - Writes supervisor-logs/status.json every minute for `minerctl.py health`.
  - Sends alerts (Apprise, or Pushover directly) if miner-alerts.json exists next to this script.
  - Refuses to run twice (lock file). Stops the miner cleanly on SIGTERM/SIGINT.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from miner_common import (  # noqa: E402
    WRAPPER,
    Paths,
    default_miner_dir,
    find_miner_pids,
    find_python,
    iso,
    kill_tree,
    now,
    parse_time,
    read_json,
    send_alert,
    tail_lines,
    newest_log,
    write_json,
)

CODE_RE = re.compile(r"enter this code:\s*([A-Za-z0-9-]+)")
EXPIRE_RE = re.compile(r"expire in (\d+) minutes")


class Supervisor:
    def __init__(self, args):
        self.args = args
        self.p = Paths(args.miner_dir, args.entry)
        self.p.log_dir.mkdir(parents=True, exist_ok=True)
        self.python = args.python or find_python(self.p.miner_dir)
        self.git = shutil.which("git")
        self.use_wrapper = WRAPPER.is_file()
        self.shutdown = False
        self.state = {
            "supervisorPid": os.getpid(),
            "supervisorStarted": iso(),
            "heartbeat": None,
            "pythonExe": self.python,
            "minerDir": str(self.p.miner_dir),
            "gracefulStop": self.use_wrapper,
            "minerPid": None,
            "minerStarted": None,
            "minerState": "starting",  # running | restarting | crashed-waiting | stopped
            "lastLogActivity": None,
            "logIsDebug": None,
            "loginNeeded": None,
            "version": None,
            "goodCommit": None,
            "lastUpdateCheck": None,
            "lastUpdateResult": None,
            "lastRollback": None,
            "scheduledRestarts": 0,
            "stallRestarts": 0,
            "lastExitCode": None,
            "lastExitTime": None,
            "crashes": [],
        }
        u = read_json(self.p.update_state) or {}
        self.good_commit = u.get("goodCommit")
        self.bad_commits = [c for c in (u.get("badCommits") or []) if c]
        self.codes_sent = 0
        self.login_paused_until = None
        self.reset_run_trackers()

    # ------------------------------------------------------------ logging / status / alerts
    def log(self, msg: str, level: str = "INFO") -> None:
        line = f"{now():%Y-%m-%d %H:%M:%S} [{level}] {msg}\n"
        try:
            with open(self.p.supervisor_log, "a", encoding="utf-8") as f:
                f.write(line)
            if self.p.supervisor_log.stat().st_size > 5 * 1024 * 1024:
                os.replace(self.p.supervisor_log, str(self.p.supervisor_log) + ".1")
        except OSError:
            pass
        if sys.stdout.isatty():
            print(line, end="")

    def save_status(self) -> None:
        self.state["heartbeat"] = iso()
        try:
            write_json(self.p.status, self.state)
        except OSError:
            pass

    def alert(
        self, msg: str, priority: int = 0, title: str = "Twitch miner", **kw
    ) -> None:
        try:
            send_alert(msg, priority=priority, title=title, **kw)
        except Exception as e:  # never let an alert take the supervisor down
            self.log(f"Alert send failed: {e}", "WARN")

    # ------------------------------------------------------------ git
    def run(self, *cmd: str, timeout: int = 300) -> tuple[int, str]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, (r.stdout + r.stderr).strip()
        except (OSError, subprocess.SubprocessError) as e:
            return 1, str(e)

    def git_cmd(self, *a: str) -> tuple[int, str]:
        return self.run(self.git, "-C", str(self.p.miner_dir), *a)

    def commit(self, rev: str = "HEAD", short: bool = False) -> str | None:
        if not self.git:
            return None
        code, out = self.git_cmd("rev-parse", *(["--short"] if short else []), rev)
        return out if code == 0 else None

    def save_update_state(self) -> None:
        try:
            write_json(
                self.p.update_state,
                {"goodCommit": self.good_commit, "badCommits": self.bad_commits},
            )
        except OSError:
            pass
        self.state["goodCommit"] = self.good_commit[:7] if self.good_commit else None

    def set_update_result(self, result: str, level: str = "INFO") -> None:
        self.log(result, level)
        self.state["lastUpdateCheck"] = iso()
        self.state["lastUpdateResult"] = result

    def install_requirements(self, why: str) -> bool:
        self.log(f"Running pip install -r requirements.txt ({why}).")
        code, out = self.run(
            self.python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-r",
            str(self.p.requirements),
            timeout=900,
        )
        if code != 0:
            self.log(f"pip install failed: {out}", "ERROR")
            return False
        self.log("pip install OK.")
        return True

    def req_hash(self) -> str:
        try:
            return hashlib.sha256(self.p.requirements.read_bytes()).hexdigest()
        except OSError:
            return ""

    def update_miner(self) -> None:
        if not self.git:
            self.set_update_result(
                "Update checks disabled (no git / not a git checkout).", "WARN"
            )
            return
        branch = self.args.branch
        code, out = self.git_cmd("fetch", "--quiet", "origin", branch)
        if code != 0:
            self.set_update_result(f"git fetch failed (offline?): {out}", "WARN")
            return
        old_head = self.commit() or "?"
        self.state["version"] = self.commit(short=True)
        _, behind = self.git_cmd("rev-list", "--count", f"HEAD..origin/{branch}")
        if behind == "0":
            self.set_update_result(
                f"Update check: up to date ({self.state['version']})."
            )
            return
        remote = self.commit(f"origin/{branch}")
        if remote and remote in self.bad_commits:
            self.set_update_result(
                f"Update check: skipping {remote[:7]} - it was rolled back after crashing. "
                "Waiting for a newer upstream commit.",
                "WARN",
            )
            return
        req_before = self.req_hash()
        code, out = self.git_cmd("merge", "--ff-only", f"origin/{branch}")
        if code != 0:
            msg = (
                f"Update available ({behind} commits) but fast-forward failed - local edits to tracked files? "
                f"Staying on {self.state['version']}. git: {out}"
            )
            self.set_update_result(msg, "WARN")
            self.alert(msg, title="Miner update failed")
            return
        new_short = self.commit(short=True)
        self.state["version"] = new_short
        self.set_update_result(
            f"Updated {old_head[:7]} -> {new_short} ({behind} commits)."
        )
        pip_note = ""
        req_after = self.req_hash()
        if (
            req_after
            and req_after != req_before
            and not self.install_requirements("requirements.txt changed")
        ):
            self.set_update_result(
                f"Updated to {new_short} but pip install failed - check supervisor.log.",
                "ERROR",
            )
            pip_note = " WARNING: pip install failed - check supervisor.log."
        self.alert(
            f"Updated {old_head[:7]} -> {new_short} ({behind} commits). Starting the miner on the new version. "
            f"It will roll back automatically if it keeps crashing.{pip_note}",
            title="Miner updated",
        )

    def check_rollback(self) -> None:
        """Called after each crash. Rolls back if the current commit has never proven itself and keeps crashing."""
        if not self.git or not self.good_commit:
            return
        head = self.commit()
        if not head or head == self.good_commit:
            return
        bad = self.commit(short=True)
        cutoff = now() - timedelta(minutes=30)
        fast = [
            c
            for c in self.state["crashes"]
            if c["commit"] == bad
            and (parse_time(c["time"]) or cutoff) > cutoff
            and c["ranMinutes"] < 15
        ]
        if len(fast) < 3:
            return
        good = self.commit(self.good_commit, short=True) or self.good_commit[:7]
        self.log(
            f"Commit {bad} crashed {len(fast)} times in 30 min - rolling back to last good commit {good}.",
            "WARN",
        )
        # --keep (not --hard): leaves your edits to run.py etc. in place; refuses if they would be overwritten.
        code, out = self.git_cmd("reset", "--keep", "--quiet", self.good_commit)
        if code != 0:
            self.log(f"Rollback failed: {out}", "ERROR")
            self.alert(
                f"Commit {bad} keeps crashing and the rollback to {good} failed: {out}",
                title="Miner rollback failed",
                priority=1,
            )
            return
        self.bad_commits = (self.bad_commits + [head])[-20:]
        self.save_update_state()
        self.install_requirements("rollback")
        self.state["version"] = good
        self.state["lastRollback"] = f"{iso()}|{bad} -> {good}"
        self.set_update_result(
            f"Rolled back {bad} -> {good} after {len(fast)} crashes. "
            f"{bad} will be skipped until upstream has a newer commit.",
            "WARN",
        )
        self.alert(
            f"Update {bad} crashed {len(fast)} times within 30 min. Rolled back to {good}, which last ran "
            f"cleanly. {bad} will be skipped until a newer commit appears upstream.",
            title="Miner update rolled back",
            priority=1,
        )

    # ------------------------------------------------------------ miner process
    def stop_miner(self, reason: str) -> None:
        for pid in find_miner_pids(self.p.entry):
            self.log(f"Force-stopping miner PID {pid} ({reason}).")
            kill_tree(pid)

    def stop_miner_gracefully(self, proc: subprocess.Popen, reason: str) -> None:
        self.state["minerState"] = "restarting"
        self.save_status()
        if proc.poll() is None:
            self.log(f"Stopping miner gracefully ({reason}).")
            if self.use_wrapper:
                self.p.stop_flag.write_text("stop")
            else:
                try:
                    os.killpg(proc.pid, signal.SIGINT)
                except (ProcessLookupError, PermissionError):
                    pass
            try:
                proc.wait(timeout=self.args.graceful_seconds)
                self.log(f"Miner shut down cleanly (exit {proc.returncode}).")
            except subprocess.TimeoutExpired:
                self.log(
                    f"Miner didn't shut down within {self.args.graceful_seconds} s - forcing.",
                    "WARN",
                )
                kill_tree(proc.pid)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
        self.stop_miner(reason)
        self.p.stop_flag.unlink(missing_ok=True)

    @staticmethod
    def rotate(path: Path) -> None:
        if path.exists():
            os.replace(path, str(path) + ".prev")

    def reset_run_trackers(self) -> None:
        self.out_pos = 0
        self.out_rest = ""
        self.bad_auth = 0
        self.login = None
        self.log_path = None
        self.log_len = -1
        self.log_grew_at = now()
        self.log_is_debug = None

    def read_new_output(self) -> list[str]:
        """Lines appended to miner-stdout.log since the last call."""
        try:
            with open(self.p.out_log, "rb") as f:
                size = f.seek(0, os.SEEK_END)
                if size < self.out_pos:
                    self.out_pos, self.out_rest = 0, ""
                length = size - self.out_pos
                if length <= 0:
                    return []
                if length > 4 * 1024 * 1024:
                    self.out_pos, self.out_rest = size - 4 * 1024 * 1024, ""
                f.seek(self.out_pos)
                data = f.read()
                self.out_pos += len(data)
        except OSError:
            return []
        lines = (self.out_rest + data.decode("utf-8", errors="replace")).split("\n")
        self.out_rest = lines[-1]
        return [ln.rstrip("\r") for ln in lines[:-1]]

    def check_stalled(self, started) -> str | None:
        """Returns a reason if the miner looks frozen. Only active with DEBUG file logging."""
        log = newest_log(self.p.miner_log_dir)
        if not log:
            return None
        try:
            size = log.stat().st_size
        except OSError:
            return None
        if log != self.log_path or size != self.log_len:
            self.log_path, self.log_len, self.log_grew_at = log, size, now()
            self.state["lastLogActivity"] = iso(self.log_grew_at)
        if now() - started < timedelta(minutes=15):  # startup grace
            return None
        if self.log_is_debug is None:
            self.log_is_debug = any(" - DEBUG - " in ln for ln in tail_lines(log, 400))
            self.state["logIsDebug"] = self.log_is_debug
            if not self.log_is_debug:
                self.log(
                    "Miner file log is not at DEBUG level - freeze detection is off (health check still warns)."
                )
        if not self.log_is_debug:
            return None
        quiet = (now() - self.log_grew_at).total_seconds() / 60
        if quiet >= self.args.stall_minutes:
            return f"its log hasn't grown for {int(quiet)} min"
        return None

    def cookie_files(self) -> list[Path]:
        try:
            return [p for p in self.p.cookie_dir.glob("*.pkl") if p.is_file()]
        except OSError:
            return []

    # ------------------------------------------------------------ login handling
    def watch_output(self) -> None:
        for line in self.read_new_output():
            m = CODE_RE.search(line)
            if m:
                issued = now()
                self.login = {
                    "code": m.group(1),
                    "issued": issued,
                    "expires": issued + timedelta(minutes=30),
                    "pushed": False,
                }
                continue
            m = EXPIRE_RE.search(line)
            if m and self.login:
                self.login["expires"] = self.login["issued"] + timedelta(
                    minutes=int(m.group(1))
                )
            elif "ERR_BADAUTH" in line:
                self.bad_auth += 1
        if self.login and not self.login["pushed"]:
            self.login["pushed"] = True
            self.codes_sent += 1
            until = f"{self.login['expires']:%H:%M}"
            code = self.login["code"]
            self.state["loginNeeded"] = (
                f"Waiting for twitch.tv/activate code {code} (valid until {until})"
            )
            self.save_status()
            self.log(
                f"Twitch login needed - activation code {code}, valid until {until}."
            )
            self.alert(
                f"Twitch needs you to log in again. Open twitch.tv/activate and enter:\n\n{code}\n\n"
                f"Valid until {until}. The miner continues on its own once you've entered it.",
                title="Twitch login needed",
                priority=1,
                url="https://www.twitch.tv/activate",
                url_title="Open twitch.tv/activate",
            )

    def check_login(self) -> str | None:
        """Returns a restart reason when the login situation needs a restart."""
        if not self.login and self.bad_auth >= 3:
            cookies = self.cookie_files()
            if cookies:
                stamp = f"{now():%Y%m%d-%H%M%S}"
                for c in cookies:
                    c.rename(c.with_name(f"{c.name}.expired-{stamp}"))
                self.log(
                    f"Twitch rejected the saved login (ERR_BADAUTH x{self.bad_auth}). "
                    f"Moved {len(cookies)} cookie file(s) aside.",
                    "WARN",
                )
                self.alert(
                    "Twitch rejected the saved login (the cookie expired). Restarting the miner - "
                    "you will get a login code next.",
                    title="Twitch login expired",
                )
                return "saved Twitch login expired"
            self.bad_auth = 0
        if not self.login:
            return None

        issued_ts = self.login["issued"].timestamp()
        if any(c.stat().st_mtime > issued_ts for c in self.cookie_files()):
            self.log("Twitch login completed - new cookie saved.")
            self.alert(
                "Logged in to Twitch again - the miner is back to work.",
                title="Twitch login OK",
                priority=-1,
            )
            self.login = None
            self.codes_sent = 0
            self.login_paused_until = None
            self.state["loginNeeded"] = None
            return None

        if now() > self.login["expires"] + timedelta(minutes=1):
            if self.codes_sent < 3:
                return "login code expired - getting a new one"
            if not self.login_paused_until:
                self.login_paused_until = now() + timedelta(hours=6)
                when = f"{self.login_paused_until:%a %H:%M}"
                self.state["loginNeeded"] = (
                    f"Not logged in after 3 codes - next try {when}, or run run.py by hand"
                )
                self.save_status()
                self.alert(
                    f"Still not logged in to Twitch after 3 codes. Next code at {when}, or run run.py by hand.",
                    title="Twitch login needed",
                    priority=1,
                )
            elif now() > self.login_paused_until:
                self.codes_sent = 0
                self.login_paused_until = None
                return "retrying Twitch login"
        return None

    # ------------------------------------------------------------ main loop
    def on_signal(self, signum, _frame) -> None:
        self.log(f"Received signal {signum} - stopping.")
        self.shutdown = True

    def sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while not self.shutdown and time.time() < end:
            time.sleep(min(2, end - time.time()))

    def start_miner(self) -> subprocess.Popen:
        env = dict(
            os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1"
        )
        cmd = (
            [self.python, str(WRAPPER), str(self.p.entry), str(self.p.stop_flag)]
            if self.use_wrapper
            else [self.python, str(self.p.entry)]
        )
        with open(self.p.out_log, "ab") as out, open(self.p.err_log, "ab") as err:
            return subprocess.Popen(
                cmd,
                cwd=self.p.miner_dir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )

    def loop(self) -> int:
        a = self.args
        if self.git and not (self.p.miner_dir / ".git").exists():
            self.log(
                "Folder is not a git checkout (ZIP download?) - update checks disabled. "
                "Clone it with git to enable updates.",
                "WARN",
            )
            self.git = None
        elif not self.git:
            self.log("git not found - update checks disabled.", "WARN")
        if not Path(self.python).exists():
            self.log(f"Python not found: {self.python}. Pass --python.", "ERROR")
            return 1
        self.log(f"Using Python: {self.python}")
        if not self.p.entry.is_file():
            self.log(f"Entry script not found: {self.p.entry}", "ERROR")
            return 1
        if not self.use_wrapper:
            self.log(
                "miner_wrapper.py not found next to the supervisor - stopping with SIGINT instead.",
                "WARN",
            )

        if self.git and not self.good_commit:
            self.good_commit = (
                self.commit()
            )  # the version running today is the baseline
        self.save_update_state()
        self.log(
            f"Supervisor started (PID {os.getpid()}). Restart every {a.restart_hours} h, "
            f"update check every {a.update_hours} h, graceful stop: {self.use_wrapper}."
        )
        self.save_status()
        self.alert(
            "Supervisor started (boot, service restart or reinstall). Starting miner.",
            title="Miner supervisor started",
            priority=-1,
        )

        last_update = 0.0
        last_crash_alert = 0.0
        crashes_since_alert = 0
        crashed = False
        backoff = 30
        restart_after = timedelta(hours=a.restart_hours)

        while not self.shutdown:
            since_update = time.time() - last_update
            # Daily check, plus an extra check if the miner keeps crashing (an update may fix it).
            if since_update >= a.update_hours * 3600 or (
                crashed and since_update >= 3600
            ):
                try:
                    self.update_miner()
                except Exception as e:
                    self.set_update_result(f"Update check error: {e}", "ERROR")
                last_update = time.time()

            # Fresh run: clean up leftovers and reset per-run trackers.
            self.stop_miner("leftover before start")
            self.p.stop_flag.unlink(missing_ok=True)
            self.rotate(self.p.out_log)
            self.rotate(self.p.err_log)
            self.reset_run_trackers()
            if not self.login_paused_until:
                self.state["loginNeeded"] = None

            proc = self.start_miner()
            started = now()
            commit = self.commit(short=True)
            self.log(f"Miner started (PID {proc.pid}, commit {commit}).")
            self.state.update(
                minerPid=proc.pid, minerStarted=iso(started), minerState="running"
            )
            self.save_status()

            # Check once a minute against the wall clock (survives sleep/suspend).
            exited = False
            restart_reason = None
            stalled = False
            while not self.shutdown:
                deadline = time.time() + 60
                while (
                    not self.shutdown and time.time() < deadline and proc.poll() is None
                ):
                    time.sleep(2)
                if proc.poll() is not None:
                    exited = True
                    break
                if self.shutdown:
                    break
                self.watch_output()
                restart_reason = self.check_login()
                if not restart_reason and not self.login:
                    stall = self.check_stalled(started)
                    if stall:
                        restart_reason, stalled = f"frozen - {stall}", True
                # A commit that has run 30 min without crashing becomes the rollback target.
                if self.git and now() - started >= timedelta(minutes=30):
                    head = self.commit()
                    if head and head != self.good_commit:
                        self.good_commit = head
                        self.save_update_state()
                        self.log(f"Commit {commit} marked as good.")
                if not restart_reason and now() - started >= restart_after:
                    restart_reason = f"scheduled {a.restart_hours} h restart"
                self.save_status()
                if restart_reason:
                    break

            if self.shutdown:
                if proc.poll() is None:
                    self.stop_miner_gracefully(proc, "supervisor stopping")
                break

            if not exited:
                if stalled:
                    self.state["stallRestarts"] += 1
                    self.alert(
                        f"The miner looked frozen ({restart_reason.removeprefix('frozen - ')}). Restarting it.",
                        title="Miner frozen - restarted",
                    )
                elif restart_reason.startswith("scheduled"):
                    self.state["scheduledRestarts"] += 1
                self.stop_miner_gracefully(proc, restart_reason)
                crashed = False
                backoff = 30
                self.sleep(5)
                continue

            ran = now() - started
            code = proc.returncode
            ran_min = int(ran.total_seconds() // 60)
            self.log(
                f"Miner exited with code {code} after {str(ran).split('.')[0]}. See miner-stderr.log. "
                f"Restarting in {backoff}s.",
                "WARN",
            )
            self.stop_miner("cleanup after exit")
            self.state.update(
                minerPid=None,
                minerState="crashed-waiting",
                lastExitCode=code,
                lastExitTime=iso(),
            )
            self.state["crashes"] = (
                self.state["crashes"]
                + [
                    {
                        "time": iso(),
                        "exitCode": code,
                        "ranMinutes": ran_min,
                        "commit": commit,
                    }
                ]
            )[-20:]
            self.save_status()

            # Alert on the first crash, then at most once an hour while it keeps crashing.
            crashes_since_alert += 1
            if time.time() - last_crash_alert >= 3600:
                tail = "\n".join(tail_lines(self.p.err_log, 6)).strip()
                extra = (
                    f" ({crashes_since_alert} crashes since last alert)"
                    if crashes_since_alert > 1
                    else ""
                )
                self.alert(
                    f"Exit {code} after {ran_min} min on {commit}{extra}. Restarting in {backoff}s.\n\n{tail}",
                    title="Miner crashed",
                    priority=1,
                    mono=True,
                )
                last_crash_alert = time.time()
                crashes_since_alert = 0
            try:
                self.check_rollback()
            except Exception as e:
                self.log(f"Rollback check error: {e}", "ERROR")
            if ran >= timedelta(hours=1):
                backoff = 30
            crashed = True
            self.sleep(backoff)
            backoff = min(backoff * 2, 900)

        self.state.update(minerPid=None, minerState="stopped")
        self.save_status()
        self.log("Supervisor stopped.")
        return 0


def acquire_lock(path: Path):
    """Single instance. Returns an open file holding the lock, or None if another supervisor runs."""
    f = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--miner-dir", type=Path, default=default_miner_dir())
    ap.add_argument(
        "--python",
        default="",
        help="python for the miner (default: repo venv, else this python)",
    )
    ap.add_argument("--entry", default="run.py")
    ap.add_argument("--restart-hours", type=int, default=24)
    ap.add_argument("--update-hours", type=int, default=24)
    ap.add_argument("--stall-minutes", type=int, default=20)
    ap.add_argument("--graceful-seconds", type=int, default=120)
    ap.add_argument("--branch", default="master")
    args = ap.parse_args()

    if sys.version_info < (3, 10):
        sys.exit("Python 3.10+ is required.")
    sup = Supervisor(args)
    lock = acquire_lock(sup.p.lock)
    if not lock:
        return 0  # another supervisor is already running
    signal.signal(signal.SIGTERM, sup.on_signal)
    signal.signal(signal.SIGINT, sup.on_signal)
    try:
        return sup.loop()
    except Exception as e:
        sup.log(f"Supervisor crashed: {e!r}", "ERROR")
        sup.state["minerState"] = "stopped"
        sup.save_status()
        sup.alert(
            f"Supervisor crashed: {e!r} - the service manager will restart it.",
            title="Miner supervisor crashed",
            priority=1,
        )
        sup.stop_miner("supervisor crash")
        return 1
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
