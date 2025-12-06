# -*- coding: utf-8 -*-

import json
import re


def extract_streamers_from_main():
    """Extract streamers from main.py file"""

    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Error: main.py file not found!")
        return None

    pattern = r'Streamer\("([^"]+)"'
    matches = re.findall(pattern, content)

    if not matches:
        print("⚠️ No streamers found in main.py")
        return None

    print(f"✅ {len(matches)} streamers found!")

    streamers = []
    for username in matches:
        streamer_data = {
            "username": username.lower().strip(),
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
        streamers.append(streamer_data)
        print(f"  ✓ {username}")

    return streamers


def create_config_file(streamers):
    """Create streamers_config.json file"""

    config = {
        "streamers": streamers,
        "global_settings": {
            "default_bet_percentage": 5,
            "default_max_points": 1000,
            "default_make_predictions": False,
            "default_strategy": "SMART"
        },
        "metadata": {
            "created_by": "migrate_to_json.py",
            "total_streamers": len(streamers)
        }
    }

    output_file = "streamers_config.json"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"\n✅ File created: {output_file}")
        print(f"📊 {len(streamers)} streamers exported")
        return True

    except Exception as e:
        print(f"❌ Error creating file: {e}")
        return False


def main():
    """Main function"""

    print("""
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   🔄 Migration to streamers_config.json              ║
║                                                       ║
║   This script will extract your streamers from       ║
║   main.py and create the JSON configuration file     ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
    """)

    print("📂 Searching for streamers in main.py...\n")

    streamers = extract_streamers_from_main()

    if not streamers:
        print("\n❌ Migration cancelled: no streamers found")
        return

    print("\n" + "=" * 60)
    print("📋 Preview of streamers to export:")
    print("=" * 60)

    for i, s in enumerate(streamers, 1):
        print(f"{i:2d}. {s['username']}")

    print("=" * 60)

    response = input("\n⚠️ Create streamers_config.json? (y/n): ").lower()

    if response == 'y':
        if create_config_file(streamers):
            print("\n" + "=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print("\n📝 Next steps:")
            print("  1. Check streamers_config.json")
            print("  2. Customize settings if needed")
            print("  3. Run: python main_dynamic.py")
            print("\n💡 Tip: Keep a backup of your original main.py!")
        else:
            print("\n❌ Migration failed")
    else:
        print("\n❌ Migration cancelled by user")


if __name__ == "__main__":
    main()