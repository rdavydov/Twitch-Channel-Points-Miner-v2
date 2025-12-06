# -*- coding: utf-8 -*-

import logging
import threading
import os
from colorama import Fore
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Telegram import Telegram
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder

from TelegramBot import TwitchMinerTelegramBot
from config_loader import load_streamers_from_config

try:
    from dotenv import load_dotenv

    load_dotenv()
    print("Environment variables loaded from .env")
except ImportError:
    print("python-dotenv not installed, using default values")

TWITCH_USERNAME = os.getenv("TWITCH_USERNAME")
TWITCH_PASSWORD = os.getenv("TWITCH_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
ANALYTICS_HOST = os.getenv("ANALYTICS_HOST", "127.0.0.1")
ANALYTICS_PORT = int(os.getenv("ANALYTICS_PORT", "5000"))


twitch_miner = TwitchChannelPointsMiner(
    username=TWITCH_USERNAME,
    password=TWITCH_PASSWORD,
    claim_drops_startup=False,
    priority=[
        Priority.STREAK,
        Priority.DROPS,
        Priority.ORDER
    ],
    enable_analytics=True,
    disable_ssl_cert_verification=False,
    disable_at_in_nickname=False,
    logger_settings=LoggerSettings(
        save=True,
        console_level=logging.INFO,
        console_username=False,
        auto_clear=True,
        time_zone="",
        file_level=logging.DEBUG,
        emoji=True,
        less=False,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="GREEN",
            streamer_offline="red",
            BET_wiN=Fore.MAGENTA
        ),
        telegram=Telegram(
            chat_id=TELEGRAM_CHAT_ID,
            token=TELEGRAM_TOKEN,
            events=[
                Events.STREAMER_ONLINE,
                Events.STREAMER_OFFLINE,
                Events.BET_LOSE,
                Events.BET_WIN,
                Events.CHAT_MENTION
            ],
            disable_notification=True,
        ),
    ),
)

twitch_miner.analytics(host=ANALYTICS_HOST, port=ANALYTICS_PORT, refresh=5, days_ago=7)


def start_telegram_bot(miner_instance):
    """Start Telegram bot in a separate thread"""
    bot = TwitchMinerTelegramBot(
        token=TELEGRAM_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        miner_instance=miner_instance
    )

    bot_thread = threading.Thread(target=bot.start, daemon=True)
    bot_thread.name = "Telegram Bot Thread"
    bot_thread.start()

    logging.info("Telegram management bot started!")
    return bot


def main():
    """Main function"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   \U0001F3AE Twitch Channel Points Miner - Dynamic Edition \U0001F916        ║
║                                                               ║
║   \u2728 Features:                                                ║
║   • Dynamic streamer management via Telegram                 ║
║   • Modify settings without restart                          ║
║   • Configuration stored in JSON                             ║
║                                                               ║
║   \U0001F4CB Available Telegram commands:                            ║
║   • /start - Show help                                       ║
║   • /add <username> - Add a streamer                         ║
║   • /remove <username> - Remove a streamer                   ║
║   • /list - View all streamers                               ║
║   • /status - Real-time status                               ║
║   • /stats - Global statistics                               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print("Loading configuration from streamers_config.json...")
    streamers = load_streamers_from_config()

    if not streamers:
        print("No streamers loaded! Check your configuration file.")
        print("A default file has been created. Edit it and restart the script.")
        return

    print(f"{len(streamers)} streamers loaded successfully!\n")

    telegram_bot = start_telegram_bot(twitch_miner)

    print("Starting mining...\n")
    print("=" * 60)

    twitch_miner.mine(
        streamers=streamers,
        followers=False,
        followers_order=FollowersOrder.ASC
    )


if __name__ == "__main__":
    main()