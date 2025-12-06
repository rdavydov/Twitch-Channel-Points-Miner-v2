# 🤖 Twitch Channel Points Miner - Telegram Bot for Dynamic Management

## 📋 Overview

This system allows you to **manage your streamers and settings via Telegram WITHOUT restarting the program**. No more manual code modifications!

---

## 🚀 Installation

### 1️⃣ Install Python Dependencies

```bash
pip install python-telegram-bot python-dotenv
```

### 2️⃣ File Structure

Place these new files in the same folder as your `main.py`:

```
your-project/
├── main.py (your old file)
├── main_dynamic.py (new - use this)
├── TelegramBot.py (new)
├── config_loader.py (new)
├── streamers_config.json (new - auto-created)
└── TwitchChannelPointsMiner/ (existing folder)
```

### 3️⃣ Initial Configuration

1. **Edit `main_dynamic.py`**:
   - Replace `"write-your-secure-psw"` with your real Twitch password
   - Verify your Telegram token and chat_id are correct

2. **Create your configuration file**:
   - Copy the provided `streamers_config.json` content
   - Modify the streamer list according to your needs
   - Save the file in the project folder

---

## 🎮 Usage

### Start the Miner

```bash
python main_dynamic.py
```

The program will:
1. ✅ Load streamers from `streamers_config.json`
2. ✅ Start the Telegram bot
3. ✅ Launch mining normally

### Available Telegram Commands

#### 📋 Streamer Management

| Command | Description | Example |
|---------|-------------|---------|
| `/start` or `/help` | Show complete help | `/start` |
| `/add <username>` | Add a new streamer | `/add ninja` |
| `/remove <username>` | Remove a streamer | `/remove ninja` |
| `/list` | View all configured streamers | `/list` |
| `/status` | Real-time status (online/offline) | `/status` |

#### ⚙️ Settings Modification

| Command | Description | Example |
|---------|-------------|---------|
| `/set_bet <username> <percentage>` | Modify bet % | `/set_bet suns1de999 10` |
| `/set_max_points <username> <points>` | Modify max points to bet | `/set_max_points ohnepixel 5000` |
| `/enable_predictions <username>` | Enable predictions | `/enable_predictions dorozea` |
| `/disable_predictions <username>` | Disable predictions | `/disable_predictions dorozea` |

#### 📊 Information

| Command | Description |
|---------|-------------|
| `/stats` | Global statistics (total points, uptime, etc.) |

---

## 🔄 How It Works

### Architecture

```
┌─────────────────────┐
│  Telegram App       │
│  (You)              │
└──────────┬──────────┘
           │ Commands
           ▼
┌─────────────────────┐
│  TelegramBot.py     │
│  (Management Bot)   │
└──────────┬──────────┘
           │ Modifies
           ▼
┌─────────────────────┐
│ streamers_config.json│
│ (Configuration)     │
└──────────┬──────────┘
           │ Read by
           ▼
┌─────────────────────┐
│  main_dynamic.py    │
│  (Mining)           │
└─────────────────────┘
```

### Workflow

1. **You send a command** on Telegram (e.g. `/add ninja`)
2. **The bot modifies** `streamers_config.json`
3. **Configuration is saved** immediately
4. ⚠️ **Current note**: Miner must be restarted to apply changes (for now)

---

## 📝 Configuration File Format

### JSON Structure

```json
{
  "streamers": [
    {
      "username": "streamer_name",
      "settings": {
        "make_predictions": false,
        "follow_raid": true,
        "claim_drops": true,
        "watch_streak": true,
        "community_goals": true,
        "bet": {
          "strategy": "SMART",
          "percentage": 5,
          "stealth_mode": true,
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
    "default_make_predictions": false
  }
}
```

### Possible Values

#### Bet Strategies
- `"SMART"` - Smart strategy (recommended)
- `"PERCENTAGE"` - Fixed percentage
- `"SMART_MONEY"` - Follow big bettors
- `"HIGH_ODDS"` - Bet on high odds
- `"MOST_VOTED"` - Follow majority

#### Delay Modes
- `"FROM_START"` - Delay from start
- `"FROM_END"` - Delay before end (recommended)
- `"PERCENTAGE"` - Percentage of time

#### Filter Conditions
- `by`: `"TOTAL_USERS"`, `"TOTAL_POINTS"`, `"ODDS"`, etc.
- `where`: `"LTE"` (≤), `"GTE"` (≥), `"LT"` (<), `"GT"` (>)

---

## 🔧 Advanced Customization

### Add Your Own Commands

Edit `TelegramBot.py` and add your function:

```python
async def cmd_my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """My custom command"""
    await update.message.reply_text("Hello!")

# In start(), add:
app.add_handler(CommandHandler("my_command", self.cmd_my_command))
```

### Modify Default Settings

Edit the `global_settings` section in `streamers_config.json`.

---

## ⚠️ Current Limitations

### 🔴 Hot-reload Not Implemented

For now, Telegram modifications are **saved in JSON** but require **miner restart** to be applied.

### 🟢 What Works
- ✅ Add/remove streamers in config
- ✅ Modify settings in config
- ✅ Real-time status display
- ✅ Statistics

### 🟡 Future Improvements
- 🔄 Hot-reload without restart
- 📊 Statistics graphs
- 🔔 Custom alerts
- 💾 Automatic config backup

---

## 🆘 Troubleshooting

### Bot Not Responding
- Check Telegram token is correct
- Check bot is running (see logs)
- Try `/start` to verify connection

### Streamers Not Loading
- Check JSON file format
- Look at logs for errors
- Verify usernames (no unnecessary capitals)

### Twitch Connection Error
- Check your username and password
- Check your internet connection
- Wait a few minutes (rate limiting)

---

## 📚 Resources

- [Twitch API Documentation](https://dev.twitch.tv/)
- [python-telegram-bot Docs](https://docs.python-telegram-bot.org/)
- [Original Miner Repo](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2)

---

## 🎯 Migration from Old main.py

If you already have a streamer list in your `main.py`, you can:

1. Use the `config_loader.py` script to export:
   ```python
   from config_loader import export_current_config_to_json
   export_current_config_to_json(your_streamers)
   ```

2. Or create the JSON manually by copying your streamers

---

## 💡 Tips

1. **Backup** your original `main.py`
2. **Test first** with 2-3 streamers
3. **Watch the logs** the first time
4. **Use `/status`** regularly to check
5. **Keep `streamers_config.json`** under version control (git)

---

## 🤝 Support

If you encounter problems:
1. Check program logs
2. Verify JSON format
3. Test Telegram commands one by one

Happy farming! 🎮💰