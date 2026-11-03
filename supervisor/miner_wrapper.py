"""
Runs the Twitch miner's run.py and stops it cleanly when a stop-flag file appears.

Used by MinerSupervisor.ps1:
    python miner_wrapper.py <path\\to\\run.py> <path\\to\\stop.flag>

When the flag file shows up, this triggers the same SIGINT handler the miner uses
for Ctrl+C (TwitchChannelPointsMiner.end): it leaves chat, closes the websockets,
waits for pending bets/JSON writes, prints the final report and exits with code 0.
The supervisor force-kills the process if that takes too long.

Needs Python 3.10+ (interrupt_main with a signal number).
"""

import _thread
import os
import runpy
import signal
import sys
import threading
import time


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: miner_wrapper.py <run.py> <stop.flag>")

    entry = os.path.abspath(sys.argv[1])
    flag = os.path.abspath(sys.argv[2])
    miner_dir = os.path.dirname(entry)

    # A leftover flag from an earlier stop must not kill this run straight away.
    try:
        os.remove(flag)
    except FileNotFoundError:
        pass

    def watch_for_stop() -> None:
        while not os.path.exists(flag):
            time.sleep(2)
        try:
            os.remove(flag)
        except OSError:
            pass
        print("miner_wrapper: stop requested - sending Ctrl+C to the miner", flush=True)
        # Runs the miner's installed SIGINT handler in the main thread.
        _thread.interrupt_main(signal.SIGINT)

    threading.Thread(
        target=watch_for_stop, name="stop-flag-watcher", daemon=True
    ).start()

    # Make run.py behave exactly as if it were started directly from its folder.
    os.chdir(miner_dir)
    sys.path[0] = miner_dir
    sys.argv = [entry]
    runpy.run_path(entry, run_name="__main__")


if __name__ == "__main__":
    main()
