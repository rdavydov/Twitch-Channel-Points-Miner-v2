import json
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from threading import Thread

import pandas as pd
from flask import Flask, Response, cli, render_template, request

from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.utils import download_file

cli.show_server_banner = lambda *_: None
logger = logging.getLogger(__name__)


def streamers_available():
    path = getattr(Settings, "analytics_path", None)
    if not path or not os.path.isdir(path):
        return []
    return [
        f
        for f in os.listdir(path)
        if os.path.isfile(os.path.join(path, f)) and f.endswith(".json") and f != "config.json"
    ]


def aggregate(df, freq="30Min"):
    df_base_events = df[(df.z == "Watch") | (df.z == "Claim")]
    df_other_events = df[(df.z != "Watch") & (df.z != "Claim")]

    be = df_base_events.groupby(
        [pd.Grouper(freq=freq, key="datetime"), "z"]).max()
    be = be.reset_index()

    oe = df_other_events.groupby(
        [pd.Grouper(freq=freq, key="datetime"), "z"]).max()
    oe = oe.reset_index()

    result = pd.concat([be, oe])
    return result


def filter_datas(start_date, end_date, datas):
    start_date = (
        datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000
        if start_date is not None
        else 0
    )
    end_date = (
        datetime.strptime(end_date, "%Y-%m-%d")
        if end_date is not None
        else datetime.now()
    ).replace(hour=23, minute=59, second=59).timestamp() * 1000

    original_series = datas.get("series", [])

    if "series" in datas and datas["series"]:
        df = pd.DataFrame(datas["series"])
        df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")
        df = df[(df.x >= start_date) & (df.x <= end_date)]
        datas["series"] = (
            df.drop(columns="datetime")
            .sort_values(by=["x", "y"], ascending=True)
            .to_dict("records")
        )
    else:
        datas["series"] = []

    if len(datas["series"]) == 0 and original_series:
        try:
            new_end_date = start_date
            new_start_date = 0
            df = pd.DataFrame(original_series)
            df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")
            df = df[(df.x >= new_start_date) & (df.x <= new_end_date)]
            if not df.empty:
                last_balance = df.drop(columns="datetime").sort_values(
                    by=["x", "y"], ascending=True).to_dict("records")[-1]['y']
                datas["series"] = [{'x': start_date, 'y': last_balance, 'z': 'No Stream'}, {
                    'x': end_date, 'y': last_balance, 'z': 'No Stream'}]
        except Exception:
            pass

    if "annotations" in datas and datas["annotations"]:
        df = pd.DataFrame(datas["annotations"])
        df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")
        df = df[(df.x >= start_date) & (df.x <= end_date)]
        datas["annotations"] = (
            df.drop(columns="datetime")
            .sort_values(by="x", ascending=True)
            .to_dict("records")
        )
    else:
        datas["annotations"] = datas.get("annotations", [])

    return datas


def read_json(streamer, return_response=True):
    start_date = request.args.get("startDate", type=str)
    end_date = request.args.get("endDate", type=str)

    path = getattr(Settings, "analytics_path", None)
    if not path:
        msg = "Analytics not enabled"
        return Response(json.dumps({"error": msg}), status=500, mimetype="application/json") if return_response else {"error": msg}

    streamer = streamer if streamer.endswith(".json") else f"{streamer}.json"

    if not os.path.exists(os.path.join(path, streamer)):
        error_message = f"File '{streamer}' not found."
        logger.error(error_message)
        if return_response:
            return Response(json.dumps({"error": error_message}), status=404, mimetype="application/json")
        else:
            return {"error": error_message}

    try:
        with open(os.path.join(path, streamer), 'r') as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        error_message = f"Error decoding JSON in file '{streamer}': {str(e)}"
        logger.error(error_message)
        if return_response:
            return Response(json.dumps({"error": error_message}), status=500, mimetype="application/json")
        else:
            return {"error": error_message}

    filtered_data = filter_datas(start_date, end_date, data)
    if return_response:
        return Response(json.dumps(filtered_data), status=200, mimetype="application/json")
    else:
        return filtered_data


def get_challenge_points(streamer):
    datas = read_json(streamer, return_response=False)
    if "series" in datas and datas["series"]:
        return datas["series"][-1]["y"]
    return 0


def get_last_activity(streamer):
    datas = read_json(streamer, return_response=False)
    if "series" in datas and datas["series"]:
        return datas["series"][-1]["x"]
    return 0


def json_all():
    return Response(
        json.dumps(
            [
                {
                    "name": streamer.strip(".json"),
                    "data": read_json(streamer, return_response=False),
                }
                for streamer in streamers_available()
            ]
        ),
        status=200,
        mimetype="application/json",
    )


def index(refresh=5, days_ago=7):
    return render_template(
        "charts.html",
        refresh=(refresh * 60 * 1000),
        daysAgo=days_ago,
    )


def streamers():
    return Response(
        json.dumps(
            [
                {"name": s, "points": get_challenge_points(
                    s), "last_activity": get_last_activity(s)}
                for s in sorted(streamers_available())
            ]
        ),
        status=200,
        mimetype="application/json",
    )


# === New helpers ===

def get_config_path(username):
    base = getattr(Settings, "analytics_path", None)
    if base:
        return os.path.join(base, "config.json")
    # fallback to analytics/<username>/config.json
    if username:
        return os.path.join(Path().absolute(), "analytics", username, "config.json")
    return os.path.join(Path().absolute(), "analytics", "config.json")


def serialize_bet(bet):
    if bet is None:
        return None
    fc = None
    if getattr(bet, "filter_condition", None) is not None:
        fc = bet.filter_condition
        fc_dict = {
            "by": str(fc.by) if fc.by else None,
            "where": str(fc.where) if fc.where else None,
            "value": fc.value,
        }
    else:
        fc_dict = None
    return {
        "strategy": str(bet.strategy) if bet.strategy else None,
        "percentage": bet.percentage,
        "percentage_gap": bet.percentage_gap,
        "max_points": bet.max_points,
        "minimum_points": bet.minimum_points,
        "stealth_mode": bet.stealth_mode,
        "delay": bet.delay,
        "delay_mode": str(bet.delay_mode) if bet.delay_mode else None,
        "filter_condition": fc_dict,
    }


def serialize_streamer_settings(s):
    if s is None:
        return None
    return {
        "make_predictions": s.make_predictions,
        "follow_raid": s.follow_raid,
        "claim_drops": s.claim_drops,
        "claim_moments": s.claim_moments,
        "watch_streak": s.watch_streak,
        "community_goals": s.community_goals,
        "chat": str(s.chat) if s.chat else None,
        "bet": serialize_bet(getattr(s, "bet", None)),
    }


def load_config_file(username):
    path = get_config_path(username)
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config {path}: {e}")
    return None


def save_config_file(username, data):
    path = get_config_path(username)
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)
    return path


def default_global_config():
    # Settings uses __slots__ - getattr returns member_descriptor when not set, so check for real instance
    try:
        gs = getattr(Settings, "streamer_settings", None)
        # member_descriptor has no make_predictions attr, real settings does
        if gs is not None and hasattr(gs, "make_predictions"):
            return serialize_streamer_settings(gs)
    except Exception:
        pass
    # fallback defaults
    return {
        "make_predictions": True,
        "follow_raid": True,
        "claim_drops": True,
        "claim_moments": True,
        "watch_streak": True,
        "community_goals": False,
        "chat": "ONLINE",
        "bet": {
            "strategy": "SMART",
            "percentage": 5,
            "percentage_gap": 20,
            "max_points": 50000,
            "minimum_points": 0,
            "stealth_mode": False,
            "delay": 6,
            "delay_mode": "FROM_END",
            "filter_condition": None,
        },
    }


def compute_streamer_stats(streamer_file, username=None):
    # streamer_file is like "feinberg.json"
    path = getattr(Settings, "analytics_path", None)
    if not path:
        if username:
            path = os.path.join(Path().absolute(), "analytics", username)
        else:
            return {}
    full = os.path.join(path, streamer_file)
    if not os.path.isfile(full):
        return {}
    try:
        with open(full, "r") as f:
            data = json.load(f)
    except Exception:
        return {}

    series = data.get("series", [])
    annotations = data.get("annotations", [])

    if not series:
        return {"points": 0, "last_activity": 0, "total_gained": 0, "series_count": 0, "bets": {"placed": 0, "wins": 0, "losses": 0, "win_rate": 0}}

    points = series[-1].get("y", 0)
    last_activity = series[-1].get("x", 0)
    first_y = series[0].get("y", points)
    total_gained = points - first_y

    # Gains by reason
    z_counter = Counter([s.get("z", "Unknown") for s in series])
    # gains per reason approximated by diffs? Use count and sum of deltas per reason
    gains_by_reason = defaultdict(int)
    # compute delta between consecutive points and attribute to current reason
    for i in range(1, len(series)):
        delta = series[i]["y"] - series[i-1]["y"]
        if delta > 0:
            reason = series[i].get("z", "Unknown")
            gains_by_reason[reason] += delta

    # Bet stats from annotations: colors
    # #45c1ff streak, #ffe045 prediction_made, #36b535 win, #ff4545 lose
    color_map = {"#45c1ff": 0, "#ffe045": 0, "#36b535": 0, "#ff4545": 0}
    for a in annotations:
        c = a.get("borderColor")
        if c in color_map:
            color_map[c] += 1

    placed = color_map["#ffe045"]
    wins = color_map["#36b535"]
    losses = color_map["#ff4545"]
    streaks = color_map["#45c1ff"]
    win_rate = round((wins / (wins + losses) * 100) if (wins + losses) > 0 else 0, 1)

    # history table similar to Streamer.history: aggregate gains_by_reason
    history = {k: {"counter": z_counter.get(k, 0), "amount": gains_by_reason.get(k, 0)} for k in set(list(z_counter.keys()) + list(gains_by_reason.keys()))}

    return {
        "name": streamer_file.replace(".json", ""),
        "file": streamer_file,
        "points": points,
        "last_activity": last_activity,
        "first_y": first_y,
        "total_gained": total_gained,
        "series_count": len(series),
        "annotations_count": len(annotations),
        "z_counter": dict(z_counter),
        "gains_by_reason": dict(gains_by_reason),
        "history": history,
        "bets": {
            "placed": placed,
            "wins": wins,
            "losses": losses,
            "streaks": streaks,
            "win_rate": win_rate,
        },
    }


def api_overview(username):
    files = streamers_available()
    stats_list = [compute_streamer_stats(f, username) for f in files]
    total_points = sum(s.get("points", 0) for s in stats_list)
    total_gained = sum(s.get("total_gained", 0) for s in stats_list)
    total_bets = sum(s.get("bets", {}).get("placed", 0) for s in stats_list)
    total_wins = sum(s.get("bets", {}).get("wins", 0) for s in stats_list)
    total_losses = sum(s.get("bets", {}).get("losses", 0) for s in stats_list)
    # top streamer by points
    top = max(stats_list, key=lambda x: x.get("points", 0)) if stats_list else None
    return {
        "total_streamers": len(files),
        "total_points": total_points,
        "total_gained": total_gained,
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "win_rate": round((total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0, 1),
        "top_streamer": top.get("name") if top else None,
        "streamers": stats_list,
    }


def api_bet_history(username, streamer=None):
    path = getattr(Settings, "analytics_path", None)
    if not path and username:
        path = os.path.join(Path().absolute(), "analytics", username)
    files = [streamer + ".json"] if streamer else streamers_available()
    rows = []
    for fname in files:
        full = os.path.join(path, fname) if path else fname
        if not os.path.isfile(full):
            continue
        try:
            with open(full, "r") as f:
                data = json.load(f)
        except Exception:
            continue
        name = fname.replace(".json", "")
        annotations = data.get("annotations", [])
        series = data.get("series", [])
        # series dict for quick lookup of balance at time
        for ann in annotations:
            color = ann.get("borderColor")
            text = ann.get("label", {}).get("text", "")
            x = ann.get("x", 0)
            # map color to type
            if color == "#ffe045":
                typ = "BET_PLACED"
            elif color == "#36b535":
                typ = "WIN"
            elif color == "#ff4545":
                typ = "LOSE"
            elif color == "#45c1ff":
                typ = "WATCH_STREAK"
            else:
                typ = "OTHER"
            # find balance at x (nearest series before)
            balance = None
            for s in reversed(series):
                if s["x"] <= x:
                    balance = s["y"]
                    break
            rows.append({
                "streamer": name,
                "type": typ,
                "color": color,
                "text": text,
                "x": x,
                "datetime": datetime.fromtimestamp(x/1000).isoformat() if x else None,
                "balance": balance,
            })
    # sort by time desc
    rows.sort(key=lambda r: r["x"], reverse=True)
    return rows


def api_enums():
    # expose allowed enum values for frontend
    return {
        "strategies": ["MOST_VOTED", "HIGH_ODDS", "PERCENTAGE", "SMART_MONEY", "SMART", "NUMBER_1", "NUMBER_2", "NUMBER_3", "NUMBER_4", "NUMBER_5", "NUMBER_6", "NUMBER_7", "NUMBER_8"],
        "delay_modes": ["FROM_START", "FROM_END", "PERCENTAGE"],
        "chat_presences": ["ALWAYS", "NEVER", "ONLINE", "OFFLINE"],
        "outcome_keys": ["PERCENTAGE_USERS", "ODDS_PERCENTAGE", "ODDS", "TOP_POINTS", "TOTAL_USERS", "TOTAL_POINTS", "DECISION_USERS", "DECISION_POINTS"],
        "conditions": ["GT", "LT", "GTE", "LTE"],
        "priorities": ["STREAK", "DROPS", "ORDER", "SUBSCRIBED", "POINTS_ASCENDING", "POINTS_DESCENDING"],
    }


def download_assets(assets_folder, required_files):
    Path(assets_folder).mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading assets to {assets_folder}")

    for f in required_files:
        if os.path.isfile(os.path.join(assets_folder, f)) is False:
            if (
                download_file(os.path.join("assets", f),
                              os.path.join(assets_folder, f))
                is True
            ):
                logger.info(f"Downloaded {f}")


def check_assets():
    required_files = [
        "banner.png",
        "charts.html",
        "script.js",
        "style.css",
        "dark-theme.css",
    ]
    assets_folder = os.path.join(Path().absolute(), "assets")
    if os.path.isdir(assets_folder) is False:
        logger.info(f"Assets folder not found at {assets_folder}")
        download_assets(assets_folder, required_files)
    else:
        for f in required_files:
            if os.path.isfile(os.path.join(assets_folder, f)) is False:
                logger.info(f"Missing file {f} in {assets_folder}")
                download_assets(assets_folder, required_files)
                break

last_sent_log_index = 0

class AnalyticsServer(Thread):
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        refresh: int = 5,
        days_ago: int = 7,
        username: str = None,
        miner=None,
    ):
        super(AnalyticsServer, self).__init__()

        check_assets()

        self.host = host
        self.port = port
        self.refresh = refresh
        self.days_ago = days_ago
        self.username = username
        self.miner = miner

        def generate_log():
            global last_sent_log_index
            last_received_index = int(request.args.get("lastIndex", last_sent_log_index))
            logs_path = os.path.join(Path().absolute(), "logs")
            log_file_path = os.path.join(logs_path, f"{username}.log")
            try:
                with open(log_file_path, "r", encoding="utf-8") as log_file:
                    log_content = log_file.read()
                new_log_entries = log_content[last_received_index:]
                last_sent_log_index = len(log_content)
                return Response(new_log_entries, status=200, mimetype="text/plain")
            except FileNotFoundError:
                return Response("Log file not found.", status=404, mimetype="text/plain")

        # === API handlers (closures capturing username/miner) ===
        def api_config_get():
            saved = load_config_file(username)
            if saved:
                return Response(json.dumps(saved), status=200, mimetype="application/json")
            live_global = default_global_config()
            streamers_cfg = {}
            if self.miner and hasattr(self.miner, "streamers"):
                for s in self.miner.streamers:
                    if hasattr(s, "settings") and s.settings:
                        streamers_cfg[s.username] = serialize_streamer_settings(s.settings)
            out = {"global": live_global, "streamers": streamers_cfg, "priority": [str(p) for p in getattr(self.miner, "priority", [])] if self.miner and hasattr(self.miner, "priority") else []}
            return Response(json.dumps(out), status=200, mimetype="application/json")

        def api_config_put():
            try:
                data = request.get_json(force=True)
            except Exception as e:
                return Response(json.dumps({"error": str(e)}), status=400, mimetype="application/json")
            # merge with existing or create new
            existing = load_config_file(username) or {"global": default_global_config(), "streamers": {}, "priority": []}
            if "global" in data:
                existing["global"] = data["global"]
                # also try to apply to live Settings if miner running
                try:
                    from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, DelayMode, FilterCondition, BetSettings, Condition, OutcomeKeys
                    from TwitchChannelPointsMiner.classes.Chat import ChatPresence
                    from TwitchChannelPointsMiner.classes.entities.Streamer import StreamerSettings
                    gs = existing["global"]
                    # update Settings.streamer_settings live (best effort) - guard for __slots__ descriptor
                    try:
                        _live_tmp = getattr(Settings, "streamer_settings", None)
                        live = _live_tmp if _live_tmp is not None and hasattr(_live_tmp, "make_predictions") else None
                    except Exception:
                        live = None
                    if live:
                        for k in ["make_predictions","follow_raid","claim_drops","claim_moments","watch_streak","community_goals"]:
                            if k in gs:
                                setattr(live, k, gs[k])
                        if "chat" in gs and gs["chat"]:
                            try:
                                setattr(live, "chat", ChatPresence[gs["chat"]])
                            except: pass
                        if "bet" in gs and gs["bet"]:
                            b = gs["bet"]
                            blive = live.bet
                            for kb in ["percentage","percentage_gap","max_points","minimum_points","stealth_mode","delay"]:
                                if kb in b:
                                    setattr(blive, kb, b[kb])
                            if "strategy" in b and b["strategy"]:
                                try: blive.strategy = Strategy[b["strategy"]]
                                except: pass
                            if "delay_mode" in b and b["delay_mode"]:
                                try: blive.delay_mode = DelayMode[b["delay_mode"]]
                                except: pass
                            if "filter_condition" in b:
                                fc = b["filter_condition"]
                                if fc is None:
                                    blive.filter_condition = None
                                else:
                                    try:
                                        blive.filter_condition = FilterCondition(by=OutcomeKeys[fc["by"]] if fc.get("by") else None, where=Condition[fc["where"]] if fc.get("where") else None, value=fc.get("value"))
                                        # Normalize by to string value for storage
                                        blive.filter_condition.by = fc.get("by")
                                        blive.filter_condition.where = fc.get("where")
                                        blive.filter_condition.value = fc.get("value")
                                    except: pass
                except Exception as e:
                    logger.error(f"Failed to apply live config: {e}")
            if "streamers" in data:
                existing["streamers"] = data["streamers"]
            if "priority" in data:
                existing["priority"] = data["priority"]
            save_config_file(username, existing)
            return Response(json.dumps({"status": "ok", "config": existing}), status=200, mimetype="application/json")

        def api_streamer_put(name):
            try:
                data = request.get_json(force=True)
            except Exception as e:
                return Response(json.dumps({"error": str(e)}), status=400, mimetype="application/json")
            cfg = load_config_file(username) or {"global": default_global_config(), "streamers": {}, "priority": []}
            if "streamers" not in cfg:
                cfg["streamers"] = {}
            cfg["streamers"][name] = data
            # attempt live update if miner has this streamer
            if self.miner and hasattr(self.miner, "streamers"):
                for s in self.miner.streamers:
                    if s.username == name.lower():
                        try:
                            from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, DelayMode, FilterCondition, BetSettings, Condition, OutcomeKeys
                            from TwitchChannelPointsMiner.classes.Chat import ChatPresence
                            from TwitchChannelPointsMiner.classes.entities.Streamer import StreamerSettings
                            # shallow apply
                            for k in ["make_predictions","follow_raid","claim_drops","claim_moments","watch_streak","community_goals"]:
                                if k in data:
                                    setattr(s.settings, k, data[k])
                            if "chat" in data and data["chat"]:
                                try: s.settings.chat = ChatPresence[data["chat"]]
                                except: pass
                            if "bet" in data and data["bet"]:
                                b=data["bet"]
                                blive=s.settings.bet
                                if blive is None:
                                    blive=BetSettings()
                                    s.settings.bet=blive
                                for kb in ["percentage","percentage_gap","max_points","minimum_points","stealth_mode","delay"]:
                                    if kb in b:
                                        setattr(blive, kb, b[kb])
                                if "strategy" in b and b["strategy"]:
                                    try: blive.strategy = Strategy[b["strategy"]]
                                    except: pass
                                if "delay_mode" in b and b["delay_mode"]:
                                    try: blive.delay_mode = DelayMode[b["delay_mode"]]
                                    except: pass
                                if "filter_condition" in b:
                                    fc=b["filter_condition"]
                                    if fc is None:
                                        blive.filter_condition=None
                                    else:
                                        try:
                                            # store as object but keep raw strings
                                            cond = FilterCondition(by=fc.get("by"), where=fc.get("where"), value=fc.get("value"))
                                            # fix by/where to enum for runtime if possible
                                            try:
                                                cond.by = OutcomeKeys[fc["by"]] if fc.get("by") and hasattr(OutcomeKeys, fc["by"]) else fc.get("by")
                                            except: pass
                                            try:
                                                cond.where = Condition[fc["where"]] if fc.get("where") and hasattr(Condition, fc["where"]) else fc.get("where")
                                            except: pass
                                            blive.filter_condition=cond
                                        except: pass
                        except Exception as e:
                            logger.error(f"live update failed for {name}: {e}")
            save_config_file(username, cfg)
            return Response(json.dumps({"status": "ok", "streamer": name, "settings": data}), status=200, mimetype="application/json")

        def api_streamer_delete(name):
            cfg = load_config_file(username) or {"global": default_global_config(), "streamers": {}, "priority": []}
            if name in cfg.get("streamers", {}):
                del cfg["streamers"][name]
                save_config_file(username, cfg)
                return Response(json.dumps({"status": "deleted", "streamer": name}), status=200, mimetype="application/json")
            return Response(json.dumps({"error": "not found"}), status=404, mimetype="application/json")

        def api_streamer_add():
            try:
                data = request.get_json(force=True)
            except Exception as e:
                return Response(json.dumps({"error": str(e)}), status=400, mimetype="application/json")
            name = data.get("username") or data.get("name")
            if not name:
                return Response(json.dumps({"error": "username required"}), status=400, mimetype="application/json")
            name = name.lower().strip()
            settings = data.get("settings")
            cfg = load_config_file(username) or {"global": default_global_config(), "streamers": {}, "priority": []}
            if cfg["streamers"].get(name):
                return Response(json.dumps({"error": "already exists"}), status=409, mimetype="application/json")
            cfg["streamers"][name] = settings if settings else None
            save_config_file(username, cfg)
            return Response(json.dumps({"status": "created", "streamer": name}), status=201, mimetype="application/json")

        def api_overview_handler():
            data = api_overview(username)
            return Response(json.dumps(data), status=200, mimetype="application/json")

        def api_bets_handler():
            streamer = request.args.get("streamer", type=str)
            limit = request.args.get("limit", type=int) or 100
            type_filter = request.args.get("type", type=str)
            rows = api_bet_history(username, streamer)
            if type_filter:
                rows = [r for r in rows if r["type"] == type_filter.upper()]
            rows = rows[:limit]
            return Response(json.dumps(rows), status=200, mimetype="application/json")

        def api_streamers_details():
            files = streamers_available()
            out = []
            for f in files:
                stats = compute_streamer_stats(f, username)
                # merge with config if exists
                cfg = load_config_file(username)
                per_stream_cfg = None
                if cfg and "streamers" in cfg:
                    per_stream_cfg = cfg["streamers"].get(stats["name"]) or cfg["streamers"].get(stats["name"].lower())
                stats["config"] = per_stream_cfg
                # live online status if miner available
                if self.miner and hasattr(self.miner, "streamers"):
                    for s in self.miner.streamers:
                        if s.username == stats["name"].lower():
                            stats["is_online"] = s.is_online
                            stats["channel_points_live"] = s.channel_points
                            break
                out.append(stats)
            # sort by points desc by default
            out.sort(key=lambda x: x.get("points", 0), reverse=True)
            return Response(json.dumps(out), status=200, mimetype="application/json")

        def api_enums_handler():
            return Response(json.dumps(api_enums()), status=200, mimetype="application/json")

        def api_series_aggregate(streamer):
            freq = request.args.get("freq", type=str) or "30Min"
            data = read_json(streamer, return_response=False)
            if "error" in data:
                return Response(json.dumps(data), status=404, mimetype="application/json")
            if freq != "raw" and "series" in data and data["series"]:
                try:
                    df = pd.DataFrame(data["series"])
                    df["datetime"] = pd.to_datetime(df.x // 1000, unit="s")
                    agg = aggregate(df, freq=freq)
                    # agg is DataFrame with datetime and z groups
                    # Convert back to series format: need x,y,z
                    # agg has columns datetime,z,y,x maybe max aggregation - use max y per group
                    # Simplify: group by z and datetime
                    # agg already contains x,y?
                    # For simplicity, return filtered data without aggregation if aggregation fails
                    data["series"] = agg.drop(columns="datetime").sort_values(by=["x","y"]).to_dict("records") if "x" in agg else data["series"]
                except Exception as e:
                    logger.error(f"aggregate failed: {e}")
            return Response(json.dumps(data), status=200, mimetype="application/json")

        self.app = Flask(
            __name__,
            template_folder=os.path.join(Path().absolute(), "assets"),
            static_folder=os.path.join(Path().absolute(), "assets"),
        )
        self.app.add_url_rule(
            "/",
            "index",
            index,
            defaults={"refresh": refresh, "days_ago": days_ago},
            methods=["GET"],
        )
        self.app.add_url_rule("/streamers", "streamers",
                              streamers, methods=["GET"])
        self.app.add_url_rule(
            "/json/<string:streamer>", "json", read_json, methods=["GET"]
        )
        self.app.add_url_rule("/json_all", "json_all",
                              json_all, methods=["GET"])
        self.app.add_url_rule(
            "/log", "log", generate_log, methods=["GET"])
        # New APIs
        self.app.add_url_rule("/api/config", "api_config_get", api_config_get, methods=["GET"])
        self.app.add_url_rule("/api/config", "api_config_put", api_config_put, methods=["PUT"])
        self.app.add_url_rule("/api/config/streamer/<string:name>", "api_streamer_put", api_streamer_put, methods=["PUT"])
        self.app.add_url_rule("/api/config/streamer/<string:name>", "api_streamer_delete", api_streamer_delete, methods=["DELETE"])
        self.app.add_url_rule("/api/config/streamer", "api_streamer_add", api_streamer_add, methods=["POST"])
        self.app.add_url_rule("/api/overview", "api_overview", api_overview_handler, methods=["GET"])
        self.app.add_url_rule("/api/bets", "api_bets", api_bets_handler, methods=["GET"])
        self.app.add_url_rule("/api/streamers/details", "api_streamers_details", api_streamers_details, methods=["GET"])
        self.app.add_url_rule("/api/enums", "api_enums", api_enums_handler, methods=["GET"])
        self.app.add_url_rule("/api/series/<string:streamer>", "api_series_agg", api_series_aggregate, methods=["GET"])

    def run(self):
        logger.info(
            f"Analytics running on http://{self.host}:{self.port}/",
            extra={"emoji": ":globe_with_meridians:"},
        )
        self.app.run(host=self.host, port=self.port,
                     threaded=True, debug=False)
