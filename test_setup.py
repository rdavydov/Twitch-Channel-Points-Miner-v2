# -*- coding: utf-8 -*-

import sys
import os
import json


def check_file(filename, required=True):
    """Check if a file exists"""
    exists = os.path.exists(filename)
    status = "✅" if exists else ("❌" if required else "⚠️")
    print(f"{status} {filename}")
    return exists


def check_module(module_name):
    """Check if a Python module is installed"""
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
        return True
    except ImportError:
        print(f"❌ {module_name} (pip install {module_name})")
        return False


def check_json_validity(filename):
    """Check if JSON is valid"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if "streamers" not in data:
            print(f"  ⚠️ Missing 'streamers' key")
            return False

        streamers_count = len(data["streamers"])
        print(f"  ✅ Valid JSON ({streamers_count} streamers)")

        for i, streamer in enumerate(data["streamers"]):
            if "username" not in streamer:
                print(f"  ⚠️ Streamer #{i + 1}: missing 'username'")
                return False
            if "settings" not in streamer:
                print(f"  ⚠️ Streamer #{i + 1}: missing 'settings'")
                return False

        print(f"  ✅ All streamers are properly formatted")
        return True

    except json.JSONDecodeError as e:
        print(f"  ❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🔍 Installation Test - Telegram Bot Miner              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    all_good = True

    print("\n📂 Checking Python files:")
    print("-" * 60)
    required_files = [
        "TelegramBot.py",
        "config_loader.py",
        "main_dynamic.py"
    ]

    for file in required_files:
        if not check_file(file, required=True):
            all_good = False

    check_file("main.py", required=False)

    print("\n📋 Checking configuration file:")
    print("-" * 60)
    if check_file("streamers_config.json"):
        check_json_validity("streamers_config.json")
    else:
        print("  ⚠️ File will be created on first launch")

    print("\n📦 Checking Python dependencies:")
    print("-" * 60)
    modules = [
        "telegram",
        "colorama",
        "requests",
    ]

    for module in modules:
        if not check_module(module):
            all_good = False

    print("\n🎮 Checking Twitch module:")
    print("-" * 60)
    if not check_file("TwitchChannelPointsMiner/__init__.py"):
        print("❌ TwitchChannelPointsMiner module not found!")
        all_good = False
    else:
        print("✅ TwitchChannelPointsMiner module present")

    print("\n📱 Checking Telegram configuration:")
    print("-" * 60)

    try:
        with open("main_dynamic.py", 'r', encoding='utf-8') as f:
            content = f.read()

        if "write-your-secure-psw" in content:
            print("⚠️ Twitch password not configured")
            print("   → Edit main_dynamic.py and replace 'write-your-secure-psw'")
            all_good = False
        else:
            print("✅ Twitch password configured")

        if "8180467830:AAHKkivatT_oWSElQW0ofSjfVkhSxhRbhAg" in content:
            print("⚠️ Default Telegram token detected")
            print("   → Make sure this is the correct token")
        else:
            print("✅ Custom Telegram token")

        if "1294936940" in content:
            print("✅ Telegram chat ID configured")

    except Exception as e:
        print(f"❌ Error reading main_dynamic.py: {e}")
        all_good = False

    print("\n" + "=" * 60)
    if all_good:
        print("✅ All tests passed!")
        print("=" * 60)
        print("\n🚀 You can start the miner with:")
        print("   python main_dynamic.py")
        print("\n💡 Available Telegram commands:")
        print("   /start - Show help")
        print("   /list - View your streamers")
        print("   /add <username> - Add a streamer")
    else:
        print("❌ Some issues were detected!")
        print("=" * 60)
        print("\n🔧 Please fix the errors above before starting")
        print("\n📚 Check README_TELEGRAM_BOT.md for more info")

    print("\n")


if __name__ == "__main__":
    main()