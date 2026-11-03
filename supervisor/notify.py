#!/usr/bin/env python3
"""
Sends one alert using miner-alerts.json (Apprise URLs, or Pushover keys). Message body is read from stdin.
Used by the Windows PowerShell scripts so they get Apprise support too.

    echo "message" | python notify.py --title "Miner crashed" --priority 1 [--mono] [--url URL --url-title TEXT]

Exit codes: 0 sent, 3 nothing configured, 1 delivery error.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from miner_common import send_alert  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Twitch miner")
    ap.add_argument("--priority", type=int, default=0)
    ap.add_argument("--mono", action="store_true")
    ap.add_argument("--url")
    ap.add_argument("--url-title")
    a = ap.parse_args()
    msg = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    try:
        sent = send_alert(
            msg,
            priority=a.priority,
            title=a.title,
            mono=a.mono,
            url=a.url,
            url_title=a.url_title,
        )
    except Exception as e:
        print(f"notify.py: {e}", file=sys.stderr)
        return 1
    return 0 if sent else 3


if __name__ == "__main__":
    sys.exit(main())
