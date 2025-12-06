# -*- coding: utf-8 -*-

import json
import logging
import os
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import BetSettings, Strategy, FilterCondition, Condition, \
    OutcomeKeys, DelayMode

logger = logging.getLogger(__name__)

CONFIG_FILE = "streamers_config.json"


def create_default_config():
    """Create a default configuration file"""
    default_config = {
        "streamers": [
            {
                "username": "suns1de999",
                "settings": {
                    "make_predictions": False,
                    "follow_raid": True,
                    "claim_drops": True,
                    "watch_streak": True,
                    "community_goals": True,
                    "bet": {
                        "strategy": "SMART",
                        "percentage": 5,
                        "stealth_mode": True,
                        "percentage_gap": 20,
                        "max_points": 1000,
                        "delay_mode": "FROM_END",
                        "delay": 6,
                        "minimum_points": 20000,
                        "filter_condition": {
                            "by": "TOTAL_USERS",
                            "where": "LTE",
                            "value": 800
                        }
                    }
                }
            }
        ],
        "global_settings": {
            "default_bet_percentage": 5,
            "default_max_points": 1000,
            "default_make_predictions": False
        }
    }

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Configuration file created: {CONFIG_FILE}")
    return default_config


def load_streamers_from_config():
    """Load streamers from JSON configuration file"""

    if not os.path.exists(CONFIG_FILE):
        logger.warning(f"⚠️ File {CONFIG_FILE} not found. Creating default config...")
        config = create_default_config()
    else:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"✅ Configuration loaded from {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            config = create_default_config()

    streamers_list = []

    for streamer_data in config.get("streamers", []):
        try:
            username = streamer_data.get("username")
            settings_data = streamer_data.get("settings", {})

            bet_data = settings_data.get("bet", {})
            filter_data = bet_data.get("filter_condition", {})

            strategy_map = {
                "SMART": Strategy.SMART,
                "PERCENTAGE": Strategy.PERCENTAGE,
                "SMART_MONEY": Strategy.SMART_MONEY,
                "HIGH_ODDS": Strategy.HIGH_ODDS,
                "MOST_VOTED": Strategy.MOST_VOTED
            }

            outcome_keys_map = {
                "TOTAL_USERS": OutcomeKeys.TOTAL_USERS,
                "TOTAL_POINTS": OutcomeKeys.TOTAL_POINTS,
                "PERCENTAGE_USERS": OutcomeKeys.PERCENTAGE_USERS,
                "ODDS_PERCENTAGE": OutcomeKeys.ODDS_PERCENTAGE,
                "ODDS": OutcomeKeys.ODDS,
                "TOP_POINTS": OutcomeKeys.TOP_POINTS
            }

            condition_map = {
                "LTE": Condition.LTE,
                "GTE": Condition.GTE,
                "LT": Condition.LT,
                "GT": Condition.GT
            }

            delay_mode_map = {
                "FROM_START": DelayMode.FROM_START,
                "FROM_END": DelayMode.FROM_END,
                "PERCENTAGE": DelayMode.PERCENTAGE
            }

            filter_condition = FilterCondition(
                by=outcome_keys_map.get(filter_data.get("by", "TOTAL_USERS"), OutcomeKeys.TOTAL_USERS),
                where=condition_map.get(filter_data.get("where", "LTE"), Condition.LTE),
                value=filter_data.get("value", 800)
            )

            bet_settings = BetSettings(
                strategy=strategy_map.get(bet_data.get("strategy", "SMART"), Strategy.SMART),
                percentage=bet_data.get("percentage", 5),
                percentage_gap=bet_data.get("percentage_gap", 20),
                max_points=bet_data.get("max_points", 1000),
                stealth_mode=bet_data.get("stealth_mode", True),
                delay_mode=delay_mode_map.get(bet_data.get("delay_mode", "FROM_END"), DelayMode.FROM_END),
                delay=bet_data.get("delay", 6),
                minimum_points=bet_data.get("minimum_points", 20000),
                filter_condition=filter_condition
            )

            streamer_settings = StreamerSettings(
                make_predictions=settings_data.get("make_predictions", False),
                follow_raid=settings_data.get("follow_raid", True),
                claim_drops=settings_data.get("claim_drops", True),
                claim_moments=settings_data.get("claim_moments", True),
                watch_streak=settings_data.get("watch_streak", True),
                community_goals=settings_data.get("community_goals", True),
                bet=bet_settings
            )

            streamer = Streamer(username, settings=streamer_settings)
            streamers_list.append(streamer)

            logger.info(f"✅ Streamer loaded: {username}")

        except Exception as e:
            logger.error(f"❌ Error loading streamer {streamer_data.get('username', 'Unknown')}: {e}")
            continue

    logger.info(f"📊 Total of {len(streamers_list)} streamers loaded from configuration")
    return streamers_list


def export_current_config_to_json(streamers_list):
    """Export current streamers configuration to JSON"""
    config = {"streamers": []}

    for streamer in streamers_list:
        streamer_data = {
            "username": streamer.username if hasattr(streamer, 'username') else str(streamer),
            "settings": {
                "make_predictions": False,
                "follow_raid": True,
                "claim_drops": True,
                "watch_streak": True,
                "community_goals": True,
                "bet": {
                    "strategy": "SMART",
                    "percentage": 5,
                    "stealth_mode": True,
                    "percentage_gap": 20,
                    "max_points": 1000,
                    "filter_condition": {
                        "by": "TOTAL_USERS",
                        "where": "LTE",
                        "value": 800
                    }
                }
            }
        }
        config["streamers"].append(streamer_data)

    output_file = "streamers_config_export.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Configuration exported to {output_file}")
    return output_file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    streamers = load_streamers_from_config()
    print(f"\n✅ {len(streamers)} streamers loaded successfully!")
    for s in streamers:
        print(f"  - {s.username}")