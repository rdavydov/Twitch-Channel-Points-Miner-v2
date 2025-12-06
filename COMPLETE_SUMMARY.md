# 📦 Twitch Miner - Telegram Bot Summary

## 🎯 What This Does

Manage your Twitch streamers via Telegram commands without restarting the program.

---

## 🚀 Quick Start

```bash
# Install
pip install python-telegram-bot python-dotenv

# Configure
cp .env.example .env
nano .env  # Add your credentials

# Migrate
python migrate_to_json.py

# Test & Run
python test_setup.py
python main_dynamic.py
```

---

## 📱 Main Commands

```
/add <username>         → Add streamer
/remove <username>      → Remove streamer
/list                   → View all
/status                 → Online status
/stats                  → Statistics
/set_bet <user> <pct>   → Change bet %
```

---

## 📁 Files

**Core:**
- `main_dynamic.py` - Run this
- `TelegramBot.py` - Bot logic
- `config_loader.py` - JSON loader
- `streamers_config.json` - Your streamers

**Setup:**
- `migrate_to_json.py` - Convert from main.py
- `test_setup.py` - Test installation
- `.env` - Your credentials (create from .env.example)

**Optional:**
- `auto_stats_reporter.py` - Automatic reports

---

## ⚙️ JSON Format

```json
{
  "streamers": [
    {
      "username": "streamer_name",
      "settings": {
        "make_predictions": false,
        "bet": {
          "percentage": 5,
          "max_points": 1000
        }
      }
    }
  ]
}
```

---

## 🔧 How It Works

```
Telegram → TelegramBot.py → streamers_config.json → main_dynamic.py → Miner
```

1. Send command on Telegram
2. Bot updates JSON file
3. Changes saved (restart needed to apply)

---

## ⚠️ Current Limitation

Changes are **saved immediately** but require **restart** to take effect. The miner doesn't support hot-reload yet.

---

## 🆘 Troubleshooting

```bash
# Bot not responding
python test_setup.py

# Invalid JSON
python -m json.tool streamers_config.json

# Check logs
tail -f logs/*.log
```

---

## 💡 vs Old System

| Old | New |
|-----|-----|
| Edit code | Telegram command |
| Restart required | Changes saved |
| Local only | Remote control |

---

## ✅ Checklist

- [ ] Dependencies installed
- [ ] `.env` configured
- [ ] `streamers_config.json` created
- [ ] `test_setup.py` passes
- [ ] Bot responds to `/start`

---

**That's it!** Simple, clean, and ready to use. 🎮

For details: check `QUICKSTART.md`