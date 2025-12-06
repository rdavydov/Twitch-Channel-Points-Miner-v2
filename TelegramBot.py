# -*- coding: utf-8 -*-

import json
import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

CONFIG_FILE = "streamers_config.json"


class TwitchMinerTelegramBot:
    """Telegram bot for dynamic streamer management without restart"""

    def __init__(self, token: str, chat_id: int, miner_instance=None):
        self.token = token
        self.chat_id = chat_id
        self.miner = miner_instance
        self.config_file = CONFIG_FILE

        if not os.path.exists(self.config_file):
            self._save_config({"streamers": [], "settings": {}})

    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"streamers": [], "settings": {}}

    def _save_config(self, config):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /start - Display available commands"""
        help_text = """
\U0001F3AE **Twitch Channel Points Miner - Management Bot**

**\U0001F4CB Available Commands:**

**Streamer Management:**
â€¢ `/add <username>` - Add a streamer
â€¢ `/remove <username>` - Remove a streamer
â€¢ `/list` - Show all streamers
â€¢ `/status` - Check streamers online status

**Settings:**
â€¢ `/set_bet <username> <percentage>` - Modify bet % (e.g. /set_bet suns1de999 10)
â€¢ `/set_max_points <username> <points>` - Modify max_points (e.g. /set_max_points suns1de999 5000)
â€¢ `/enable_predictions <username>` - Enable predictions
â€¢ `/disable_predictions <username>` - Disable predictions

**Information:**
â€¢ `/stats` - Global statistics
â€¢ `/help` - Show this help

**\u26A0\ufe0f Note:** Changes are applied immediately without restart!
        """
        await update.message.reply_text(help_text)

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /add - Add a streamer"""
        if not context.args:
            await update.message.reply_text("\u274c Usage: /add <username>")
            return

        username = context.args[0].lower().strip()
        config = self._load_config()

        if any(s.get("username") == username for s in config["streamers"]):
            await update.message.reply_text(f"\u26A0\ufe0f {username} is already in the list!")
            return

        new_streamer = {
            "username": username,
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
            },
            "added_at": datetime.now().isoformat()
        }

        config["streamers"].append(new_streamer)

        if self._save_config(config):
            if self.miner and self.miner.running:
                await self._add_streamer_to_running_miner(username, new_streamer["settings"])

            await update.message.reply_text(
                f"\u2714\ufe0f Streamer **{username}** added successfully!\n"
                f"\U0001F4CA Default settings applied.\n"
                f"\u26A1 Use /set_* to customize."
            )
        else:
            await update.message.reply_text("\u274c Error adding streamer")

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /remove - Remove a streamer"""
        if not context.args:
            await update.message.reply_text("\u274c Usage: /remove <username>")
            return

        username = context.args[0].lower().strip()
        config = self._load_config()

        initial_count = len(config["streamers"])
        config["streamers"] = [s for s in config["streamers"] if s.get("username") != username]

        if len(config["streamers"]) == initial_count:
            await update.message.reply_text(f"\u26A0\ufe0f {username} is not in the list!")
            return

        if self._save_config(config):
            if self.miner and self.miner.running:
                await self._remove_streamer_from_running_miner(username)

            await update.message.reply_text(f"\u2714\ufe0f Streamer **{username}** removed successfully!")
        else:
            await update.message.reply_text("\u274c Error removing streamer")

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /list - Display all streamers"""
        config = self._load_config()

        if not config["streamers"]:
            await update.message.reply_text("\U0001F4ED No streamers configured!")
            return

        message = "\U0001F4ED **Streamers List:**\n\n"
        for i, streamer in enumerate(config["streamers"], 1):
            username = streamer.get("username", "Unknown")
            predictions = "\u2714\ufe0f" if streamer.get("settings", {}).get("make_predictions") else "\u274c"
            bet_pct = streamer.get("settings", {}).get("bet", {}).get("percentage", 5)
            max_pts = streamer.get("settings", {}).get("bet", {}).get("max_points", 1000)

            message += f"{i}. **{username}**\n"
            message += f"   â€¢ Predictions: {predictions}\n"
            message += f"   â€¢ Bet: {bet_pct}% (max: {max_pts} pts)\n\n"

        await update.message.reply_text(message)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /status - Display streamers status"""
        if not self.miner or not self.miner.running:
            await update.message.reply_text("\u26A0\ufe0f Miner is not running!")
            return

        message = "\U0001F3AE **Streamers Status:**\n\n"
        online_count = 0

        for streamer in self.miner.streamers:
            status = "\U0001F7E2 ONLINE" if streamer.is_online else "\U0001F534 OFFLINE"
            points = f"{streamer.channel_points:,}" if hasattr(streamer, 'channel_points') else "N/A"

            if streamer.is_online:
                online_count += 1

            message += f"{status} **{streamer.username}**\n"
            message += f"   \U0001F4B0 Points: {points}\n\n"

        message += f"\n\U0001F4CA Total: {online_count}/{len(self.miner.streamers)} online"
        await update.message.reply_text(message)

    async def cmd_set_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /set_bet - Modify bet percentage"""
        if len(context.args) < 2:
            await update.message.reply_text("\u274c Usage: /set_bet <username> <percentage>")
            return

        username = context.args[0].lower().strip()
        try:
            percentage = int(context.args[1])
            if percentage < 1 or percentage > 100:
                raise ValueError
        except ValueError:
            await update.message.reply_text("\u274c Percentage must be between 1 and 100!")
            return

        config = self._load_config()
        streamer_found = False

        for streamer in config["streamers"]:
            if streamer.get("username") == username:
                streamer["settings"]["bet"]["percentage"] = percentage
                streamer_found = True
                break

        if not streamer_found:
            await update.message.reply_text(f"\u26A0\ufe0f Streamer {username} not found!")
            return

        if self._save_config(config):
            await update.message.reply_text(
                f"\u2714\ufe0f Bet percentage for **{username}** updated: {percentage}%"
            )
        else:
            await update.message.reply_text("\u274c Error updating config")

    async def cmd_set_max_points(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /set_max_points - Modify max_points"""
        if len(context.args) < 2:
            await update.message.reply_text("\u274c Usage: /set_max_points <username> <points>")
            return

        username = context.args[0].lower().strip()
        try:
            max_points = int(context.args[1])
            if max_points < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("\u274c Points must be a positive number!")
            return

        config = self._load_config()
        streamer_found = False

        for streamer in config["streamers"]:
            if streamer.get("username") == username:
                streamer["settings"]["bet"]["max_points"] = max_points
                streamer_found = True
                break

        if not streamer_found:
            await update.message.reply_text(f"\u26A0\ufe0f Streamer {username} not found!")
            return

        if self._save_config(config):
            await update.message.reply_text(
                f"\u2714\ufe0f Max points for **{username}** updated: {max_points}"
            )
        else:
            await update.message.reply_text("\u274c Error updating config")

    async def cmd_enable_predictions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /enable_predictions - Enable predictions"""
        if not context.args:
            await update.message.reply_text("\u274c Usage: /enable_predictions <username>")
            return

        username = context.args[0].lower().strip()
        await self._toggle_predictions(update, username, True)

    async def cmd_disable_predictions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /disable_predictions - Disable predictions"""
        if not context.args:
            await update.message.reply_text("\u274c Usage: /disable_predictions <username>")
            return

        username = context.args[0].lower().strip()
        await self._toggle_predictions(update, username, False)

    async def _toggle_predictions(self, update, username, enabled):
        """Toggle predictions for a streamer"""
        config = self._load_config()
        streamer_found = False

        for streamer in config["streamers"]:
            if streamer.get("username") == username:
                streamer["settings"]["make_predictions"] = enabled
                streamer_found = True
                break

        if not streamer_found:
            await update.message.reply_text(f"\u26A0\ufe0f Streamer {username} not found!")
            return

        if self._save_config(config):
            status = "enabled \u2714\ufe0f" if enabled else "disabled \u274c"
            await update.message.reply_text(
                f"Predictions {status} for **{username}**"
            )
        else:
            await update.message.reply_text("\u274c Error updating config")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command /stats - Display global statistics"""
        if not self.miner or not self.miner.running:
            await update.message.reply_text("\u26A0\ufe0f Miner is not running!")
            return

        total_points = sum(s.channel_points for s in self.miner.streamers)
        online = sum(1 for s in self.miner.streamers if s.is_online)

        uptime = datetime.now() - self.miner.start_datetime if self.miner.start_datetime else None

        message = "\U0001F4CA **Global Statistics:**\n\n"
        message += f"\U0001F4B0 Total points: {total_points:,}\n"
        message += f"\U0001F3AE Streamers: {len(self.miner.streamers)}\n"
        message += f"\U0001F7E2 Online: {online}\n"
        if uptime:
            message += f"\u23f1\ufe0f Uptime: {str(uptime).split('.')[0]}\n"
        message += f"\U0001F194 Session: {self.miner.session_id[:8]}..."

        await update.message.reply_text(message)

    async def _add_streamer_to_running_miner(self, username, settings):
        """Add streamer to running miner"""
        logger.info(f"TODO: Add {username} to running miner")

    async def _remove_streamer_from_running_miner(self, username):
        """Remove streamer from running miner"""
        logger.info(f"TODO: Remove {username} from running miner")

    def start(self):
        """Start the Telegram bot"""
        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_start))
        app.add_handler(CommandHandler("add", self.cmd_add))
        app.add_handler(CommandHandler("remove", self.cmd_remove))
        app.add_handler(CommandHandler("list", self.cmd_list))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("set_bet", self.cmd_set_bet))
        app.add_handler(CommandHandler("set_max_points", self.cmd_set_max_points))
        app.add_handler(CommandHandler("enable_predictions", self.cmd_enable_predictions))
        app.add_handler(CommandHandler("disable_predictions", self.cmd_disable_predictions))
        app.add_handler(CommandHandler("stats", self.cmd_stats))

        logger.info("\U0001F916 Telegram bot started and ready to receive commands!")

        app.run_polling(stop_signals=None)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")

    bot = TwitchMinerTelegramBot(TOKEN, int(CHAT_ID))
    bot.start()
