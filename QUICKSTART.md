# 🚀 Quick Start Guide

## Installation in 5 minutes

### 1️⃣ Install dependencies

```bash
pip install python-telegram-bot python-dotenv
```

### 2️⃣ Configure your credentials

**Option A: .env file (recommended)**
```bash
cp .env.example .env
nano .env  # Edit with your real values
```

**Option B: Edit main_dynamic.py directly**
```python
TWITCH_USERNAME = "your_username"
TWITCH_PASSWORD = "your_password"
TELEGRAM_TOKEN = "your_token"
TELEGRAM_CHAT_ID = your_chat_id
```

### 3️⃣ Create streamers configuration

**Option A: Automatic migration from main.py**
```bash
python migrate_to_json.py
```

**Option B: Manual creation**
Copy the provided `streamers_config.json` file and modify it.

### 4️⃣ Test the installation

```bash
python test_setup.py
```

If all tests pass (✅), you're ready!

### 5️⃣ Start the miner

```bash
python main_dynamic.py
```

---

## 🎮 Using the Telegram Bot

### Open Telegram and test

1. Open your conversation with the bot
2. Send `/start`
3. You should see the commands list

### Essential commands

```
/list          → View your streamers
/status        → Who is online?
/add ninja     → Add a streamer
/remove ninja  → Remove a streamer
/stats         → Statistics
```

---

## ⚙️ Quick streamer configuration

### Add a streamer with default settings

```
/add <username>
```

### Customize settings

```
/set_bet <username> 10              → 10% bet
/set_max_points <username> 5000     → Maximum 5000 points
/enable_predictions <username>      → Enable predictions
```

---

## 🔧 Quick troubleshooting

### Bot not responding
```bash
python test_setup.py
```

### Twitch connection error
- Check username/password in .env
- Wait 5 minutes (rate limiting)

### Streamers not loading
```bash
python -m json.tool streamers_config.json
```

---

## 📊 File structure

```
your-project/
├── .env                          ← Your credentials (DON'T COMMIT!)
├── .env.example                  ← Template
├── main_dynamic.py               ← RUN THIS FILE
├── TelegramBot.py                ← Management bot
├── config_loader.py              ← Config loader
├── streamers_config.json         ← Your streamers
├── migrate_to_json.py            ← Migration script
├── test_setup.py                 ← Test script
├── requirements_telegram.txt     ← Dependencies
└── TwitchChannelPointsMiner/     ← Miner module
```

---

## 🎯 Typical workflow

1. **Morning**: Run `python main_dynamic.py`
2. **During the day**: Manage via Telegram
   - `/status` to see who's online
   - `/add` to add new streamers
   - `/remove` to remove inactive ones
3. **Evening**: `/stats` to see your gains
4. Miner runs 24/7, you manage everything from Telegram!

---

## 💡 Tips

- **Backup**: Make a copy of `streamers_config.json` regularly
- **Logs**: Check log files if there are issues
- **Analytics**: Open http://127.0.0.1:5000 for visual stats
- **Security**: Never share your `.env` file!

---

## 📚 Go further

Check `README_TELEGRAM_BOT.md` for:
- All available commands
- Advanced customization
- Detailed JSON format
- Creating custom commands

---

## ✅ Startup checklist

- [ ] `pip install python-telegram-bot python-dotenv` executed
- [ ] `.env` file created and filled
- [ ] `streamers_config.json` created (via migration or manually)
- [ ] `python test_setup.py` → all tests pass ✅
- [ ] `python main_dynamic.py` launched
- [ ] Bot responds to `/start` on Telegram
- [ ] `/list` shows your streamers
- [ ] http://127.0.0.1:5000 opens for analytics

🎉 **Let's go!** You can now farm comfortably while managing from your phone!