"""
app.py
Command-Line Interface and entry point for the NYC Re-Rental Alert Service.

Usage:
  python app.py               Start background monitoring service
  python app.py --check-once  Run a single check cycle and exit
  python app.py --dashboard   Start local web dashboard (http://localhost:5050)
  python app.py --test        Send test alerts to verify Telegram and Email
  python app.py --setup       Interactive configuration wizard
  python app.py --stats       Show service statistics and recent listings
"""

import sys
import argparse
import logging

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from config import load_config, save_config, create_example_config
from database import Database
from service import ReRentalService
from notifiers.telegram_notifier import TelegramNotifier
from notifiers.email_notifier import EmailNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("rerental")


def setup_wizard():
    """Interactive command-line setup wizard."""
    print("\n" + "=" * 60)
    print("  🏢 NYC Re-Rental Alert Service Setup Wizard")
    print("=" * 60)
    print("Configure your instant Telegram and Email alerts without paying any fees.\n")

    cfg = load_config()

    # 1. Telegram
    print("--- ✈️  Telegram Notifications ---")
    enable_tg = input("Enable Telegram alerts? (y/n) [default: y]: ").strip().lower() != 'n'
    cfg["telegram"]["enabled"] = enable_tg
    if enable_tg:
        curr_token = cfg["telegram"].get("bot_token", "")
        print("\nTo get a Telegram Bot Token:")
        print(" 1. In Telegram, message @BotFather and send /newbot")
        print(" 2. Follow prompts and copy the HTTP API token")
        token = input(f"Enter Telegram Bot Token [{curr_token[:10]}...]: ").strip()
        if token:
            cfg["telegram"]["bot_token"] = token

        curr_chat = cfg["telegram"].get("chat_id", "")
        print("\nTo find your Telegram Chat ID:")
        print(" 1. In Telegram, message @userinfobot or @raw_data_bot")
        print(" 2. It will reply with your numeric ID (e.g. 123456789)")
        chat = input(f"Enter Telegram Chat ID [{curr_chat}]: ").strip()
        if chat:
            cfg["telegram"]["chat_id"] = chat

    # 2. Email
    print("\n--- 📧 Email Notifications ---")
    enable_em = input("Enable Email alerts? (y/n) [default: y]: ").strip().lower() != 'n'
    cfg["email"]["enabled"] = enable_em
    if enable_em:
        sender = input(f"Sender Email address [{cfg['email'].get('sender_email')}]: ").strip()
        if sender:
            cfg["email"]["sender_email"] = sender
            cfg["email"]["recipient_email"] = sender

        print("\nNote for Gmail users: Use an App Password (not your main password).")
        print("Generate one at: https://myaccount.google.com/apppasswords")
        pwd = input("Enter App Password / SMTP Password: ").strip()
        if pwd:
            cfg["email"]["sender_password"] = pwd

        recip = input(f"Recipient Email (where to receive alerts) [{cfg['email'].get('recipient_email')}]: ").strip()
        if recip:
            cfg["email"]["recipient_email"] = recip

    # 3. Filters
    print("\n--- 🎯 Search Filters (Free & Customizable) ---")
    max_rent_input = input("Maximum rent ($/mo) [press Enter for no limit]: ").strip()
    if max_rent_input:
        try:
            cfg["filters"]["max_rent"] = float(max_rent_input.replace("$", "").replace(",", ""))
        except ValueError:
            print("Invalid rent number, leaving no limit.")

    beds_input = input("Bedrooms to alert on (comma-separated, e.g. Studio, 1BR, 2BR) [Enter for all]: ").strip()
    if beds_input:
        cfg["filters"]["allowed_beds"] = [b.strip() for b in beds_input.split(",") if b.strip()]

    boroughs_input = input("Boroughs to alert on (e.g. Manhattan, Brooklyn, Queens) [Enter for all]: ").strip()
    if boroughs_input:
        cfg["filters"]["allowed_boroughs"] = [b.strip() for b in boroughs_input.split(",") if b.strip()]

    save_config(cfg)
    print("\n" + "=" * 60)
    print("✅ Configuration successfully saved to config.json!")
    print("=" * 60)

    test_now = input("\nWould you like to send a test alert now? (y/n) [y]: ").strip().lower() != 'n'
    if test_now:
        test_alerts()


def test_alerts():
    """Test notification channels."""
    cfg = load_config()
    print("\n[Testing Notification Channels]")

    # Test Telegram
    if cfg["telegram"].get("enabled"):
        print("Testing Telegram...")
        tg = TelegramNotifier(cfg["telegram"])
        success, msg = tg.send_test_message()
        if success:
            print("  ✅ Telegram test message sent successfully!")
        else:
            print(f"  ❌ Telegram test failed: {msg}")
    else:
        print("  ℹ️ Telegram alerts are disabled in config.json")

    # Test Email
    if cfg["email"].get("enabled"):
        print("Testing Email...")
        em = EmailNotifier(cfg["email"])
        success, msg = em.send_test_email()
        if success:
            print("  ✅ Email test message sent successfully!")
        else:
            print(f"  ❌ Email test failed: {msg}")
    else:
        print("  ℹ️ Email alerts are disabled in config.json")
    print()


def find_chat_id():
    """Helper to discover chat ID from messages sent to the bot."""
    cfg = load_config()
    token = cfg.get("telegram", {}).get("bot_token", "")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ Please configure your telegram.bot_token first.")
        return

    tg = TelegramNotifier(cfg["telegram"])
    bot_info = tg.get_bot_info()
    username = bot_info.get("username", "your bot") if bot_info else "your bot"

    print(f"\nChecking messages sent to @{username} (https://t.me/{username})...")
    chats = tg.get_recent_chat_ids()

    if not chats:
        print("\n⚠️ No messages found yet!")
        print(f"👉 Please open Telegram, visit https://t.me/{username} and click 'START' (or send any message).")
        print("Then run this command again:\n  python app.py --find-chat-id\n")
        return

    print(f"\n✅ Found {len(chats)} chat(s):")
    for c in chats:
        c_id = str(c.get("id"))
        c_name = c.get("first_name", "") or c.get("username", "") or c.get("title", "")
        print(f"  • Name: {c_name} | Chat ID: {c_id}")

    # If exactly one or user wants to update
    latest_id = str(chats[-1].get("id"))
    cfg["telegram"]["chat_id"] = latest_id
    cfg["telegram"]["enabled"] = True
    save_config(cfg)
    print(f"\n💾 Updated config.json with chat_id: {latest_id}")
    print("Testing connection now...")
    test_alerts()


def show_stats():
    """Display service statistics."""
    """Display service statistics."""
    db = Database()
    stats = db.get_stats()
    print("\n" + "=" * 50)
    print("  📊 ReRental Alert Service Statistics")
    print("=" * 50)
    print(f"  Total listings tracked:      {stats['total_seen']}")
    print(f"  Telegram alerts sent:        {stats['telegram_alerts_sent']}")
    print(f"  Email alerts sent:           {stats['email_alerts_sent']}")
    print(f"  Last checked timestamp:      {stats['last_check_time']}")
    print("=" * 50)

    recent = db.get_recent_listings(limit=8)
    if recent:
        print("\nLatest tracked listings:")
        for r in recent:
            rent_str = f"${r['rent']:,.0f}/mo" if r['rent'] else "N/A"
            print(f"  • {rent_str:12} | {r['beds']:8} | {r['address'][:30]:30} | {r['borough']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="NYC Affordable Housing Re-Rental Alert Service")
    parser.add_argument("--find-chat-id", action="store_true", help="Auto-detect your Chat ID from messages sent to your bot")
    parser.add_argument("--check-once", action="store_true", help="Execute one check cycle and exit")
    parser.add_argument("--dashboard", action="store_true", help="Launch local web dashboard UI (http://localhost:5050)")
    parser.add_argument("--test", action="store_true", help="Send test Telegram and Email notifications")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup wizard")
    parser.add_argument("--stats", action="store_true", help="View statistics and recent tracked listings")
    parser.add_argument("--port", type=int, default=5050, help="Port for web dashboard (default: 5050)")

    args = parser.parse_args()

    # Ensure example config exists
    create_example_config()

    if args.setup:
        setup_wizard()
    elif args.find_chat_id:
        find_chat_id()
    elif args.test:
        test_alerts()
    elif args.stats:
        show_stats()
    elif args.dashboard:
        from dashboard import run_dashboard
        run_dashboard(port=args.port)
    elif args.check_once:
        service = ReRentalService()
        service.initialize_if_needed()
        service.run_check_cycle()
    else:
        # Default: Run continuous service
        service = ReRentalService()
        service.start_loop()


if __name__ == "__main__":
    main()
