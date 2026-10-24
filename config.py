"""
config.py
Configuration loader and validator for the ReRental Alert Service.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).parent / "config.json"
EXAMPLE_CONFIG_FILE = Path(__file__).parent / "config.example.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "poll_interval_seconds": 60,
    "baseline_on_first_run": True,
    "gemini_api_key": "",
    "housing_lotteries": {
        "enabled": True,
        "poll_interval_hours": 3
    },
    "telegram": {
        "enabled": False,
        "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
        "chat_id": "YOUR_TELEGRAM_CHAT_ID"
    },
    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls": True,
        "use_ssl": False,
        "sender_email": "YOUR_EMAIL@gmail.com",
        "sender_password": "YOUR_APP_PASSWORD",
        "recipient_email": "YOUR_EMAIL@gmail.com",
        "resend_api_key": ""
    },
    "filters": {
        "max_rent": None,
        "min_rent": None,
        "allowed_beds": [],
        "allowed_boroughs": [],
        "include_unspecified_beds": True,
        "keywords": []
    }
}


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json, with environment variable overrides."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        config = DEFAULT_CONFIG.copy()
    else:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config = DEFAULT_CONFIG.copy()
                for k, v in user_config.items():
                    if isinstance(v, dict) and k in config and isinstance(config[k], dict):
                        config[k].update(v)
                    else:
                        config[k] = v
        except Exception as e:
            print(f"[Config] Error loading config.json: {e}. Using defaults.")
            config = DEFAULT_CONFIG.copy()

    # Environment variable overrides (useful for Render/Cloud deployment)
    if os.environ.get("GEMINI_API_KEY"):
        config["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    if os.environ.get("INCLUDE_UNSPECIFIED_BEDS"):
        config["filters"]["include_unspecified_beds"] = os.environ["INCLUDE_UNSPECIFIED_BEDS"].lower() in ("true", "1", "yes")

    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram"]["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
        config["telegram"]["enabled"] = True
    if os.environ.get("TELEGRAM_CHAT_ID"):
        raw_chats = os.environ["TELEGRAM_CHAT_ID"]
        config["telegram"]["chat_ids"] = [c.strip() for c in raw_chats.split(",") if c.strip()]
        config["telegram"]["enabled"] = True

    if os.environ.get("RESEND_API_KEY"):
        config["email"]["resend_api_key"] = os.environ["RESEND_API_KEY"]
        config["email"]["enabled"] = True
    if os.environ.get("EMAIL_RECIPIENT"):
        config["email"]["recipient_email"] = os.environ["EMAIL_RECIPIENT"]
        config["email"]["enabled"] = True
    if os.environ.get("EMAIL_SENDER"):
        config["email"]["sender_email"] = os.environ["EMAIL_SENDER"]
    if os.environ.get("EMAIL_PASSWORD"):
        config["email"]["sender_password"] = os.environ["EMAIL_PASSWORD"]
    if os.environ.get("EMAIL_ENABLED"):
        config["email"]["enabled"] = os.environ["EMAIL_ENABLED"].lower() in ("true", "1", "yes")

    if os.environ.get("MAX_RENT"):
        try:
            config["filters"]["max_rent"] = float(os.environ["MAX_RENT"])
        except ValueError:
            pass
    if os.environ.get("ALLOWED_BEDS"):
        config["filters"]["allowed_beds"] = [b.strip() for b in os.environ["ALLOWED_BEDS"].split(",") if b.strip()]
    if os.environ.get("ALLOWED_BOROUGHS"):
        config["filters"]["allowed_boroughs"] = [b.strip() for b in os.environ["ALLOWED_BOROUGHS"].split(",") if b.strip()]

    return config


def save_config(config: Dict[str, Any]):
    """Save configuration to config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def create_example_config():
    """Create a documented config.example.json."""
    with open(EXAMPLE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4)
