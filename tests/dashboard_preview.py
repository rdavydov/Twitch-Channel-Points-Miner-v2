"""Isolated dashboard fixture server. Never logs in to Twitch or runs a miner."""

import argparse
import copy
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import request
from waitress import serve
from test_dashboard import fixture_service, response_for
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
from TwitchChannelPointsMiner.dashboard.reader import operation
from TwitchChannelPointsMiner.dashboard.server import create_app


def preview_app(folder):
    service, _ = fixture_service(Path(folder) / "preview.sqlite3")
    service.account = "dashboard-preview"
    now = time.time()
    service.clock.value = now
    for i, name in enumerate(
        [
            "2okos",
            "glorious_e",
            "lvndmark",
            "sheefgg",
            "ppanka",
            "warthunder_esports",
            "coolestjonas",
            "theeuropeancanadian",
            "wearethevr",
            "formal",
            "jaguara333",
            "henkovic",
        ]
    ):
        if i == 0:
            streamer = service.miner.streamers[0]
        else:
            streamer = Streamer(
                name, copy.deepcopy(service.miner.streamers[0].settings)
            )
            streamer.settings.favorite = False
            streamer.channel_id = str(i)
            service.miner.streamers.append(streamer)
        streamer.is_online = i in (0, 1, 3, 4)
        streamer.channel_points = (i + 1) * 5897
        streamer.channel_points_context_at = now
        for op, variables in (
            ("ChannelPointsContext", {"channelLogin": name}),
            ("VideoPlayerStreamInfoOverlayChannel", {"channel": name}),
            ("RewardList", {"channelID": streamer.channel_id}),
        ):
            value = response_for(operation(op, variables))
            if op == "ChannelPointsContext":
                value["data"]["community"]["channel"]["self"]["communityPoints"][
                    "balance"
                ] = streamer.channel_points
            if op == "VideoPlayerStreamInfoOverlayChannel" and not streamer.is_online:
                value["data"]["user"]["stream"] = None
            if op == "RewardList":
                milestone = value["data"]["channel"]["self"]["watchStreakMilestone"]
                milestone["watchStreakMilestone"]["value"] = str(3 + i)
                milestone["missedStreams"] = (
                    [] if i != 2 else [{"broadcastIdentifiers": [{"id": "missed"}]}]
                )
                milestone["expiresAt"] = now + 7200 if i == 2 else None
                if i == 2:
                    from datetime import datetime, timezone

                    milestone["expiresAt"] = datetime.fromtimestamp(
                        now + 7200, timezone.utc
                    ).isoformat()
            service.observe_response(operation(op, variables), value, now - 1, now)
        for n in range(30):
            service.store.sample(
                name, streamer.channel_points - 300 + n * 10, now - (30 - n) * 3600
            )
    service.selection = [
        {"channel": "2okos", "reason": "Priority rules: Favorite > Subscribed > Drops"},
        {"channel": "glorious_e", "reason": "Streak slot"},
    ]
    service.last_selection_at = now
    service.miner.streamers[0].stream.watch_streak_missing = False
    service.remote["_account"] = {
        "inventory": {
            "drops": [
                {
                    "id": "drop-1",
                    "campaign": "Autumn campaign",
                    "campaign_id": "campaign",
                    "name": "Forest camouflage",
                    "reward": "Vehicle camouflage",
                    "minutes": 75,
                    "required_minutes": 120,
                    "claimed": False,
                    "ends_at": now + 86400,
                }
            ],
            "fetched_at": now,
            "source": "Twitch",
            "error": None,
        }
    }
    tracker = service.miner.prediction_tracker
    for i, result in enumerate(("WIN", "LOSE", "REFUND")):
        key = str(i)
        tracker.state["events"][key] = {
            "channel": "2okos",
            "title": "Will the squad survive?",
            "outcomes": [{"id": "yes", "title": "Yes"}],
        }
        tracker.state["predictions"][key] = {
            "event_id": key,
            "channel_id": "872174898",
            "outcome_id": "yes",
            "points": 5000,
            "source": "Miner" if i != 1 else "Manual / external",
            "result": {
                "type": result,
                "points_won": 8750
                if result == "WIN"
                else 5000
                if result == "REFUND"
                else 0,
            },
            "predicted_at": "2026-11-01T10:00:00Z",
            "resolved_at": "2026-11-01T11:00:00Z",
        }
    service.store.event(
        "recovery_confirmed",
        "Watch streak recovery confirmed by Twitch",
        channel="lvndmark",
    )
    service.store.flush()
    app = create_app(service)

    @app.before_request
    def fixture_snapshot():
        service.clock.value = time.time()
        service.last_selection_at = service.clock()
        if request.path == "/api/v1/bootstrap":
            service.refresh.update(
                state="complete",
                next_manual_at=0,
                next_auto_at=time.time() + 300,
                completed_at=time.time() - 120,
                completed=62,
                total=62,
            )
        service.cached = service.build_snapshot()

    return app, service


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        app, service = preview_app(folder)
        try:
            serve(app, host="127.0.0.1", port=args.port)
        finally:
            service.stop()
