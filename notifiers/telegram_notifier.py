"""
notifiers/telegram_notifier.py
Sends instant Telegram push notifications using Telegram Bot API.
Zero third-party library dependencies (uses Python standard library urllib).
"""

import urllib.request
import urllib.parse
import json
import logging
from typing import Tuple, Dict, Any, Optional, List
from models import Listing

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        self.bot_token = config.get("bot_token", "").strip()
        raw_chat_ids = config.get("chat_ids") or config.get("chat_id") or []
        if isinstance(raw_chat_ids, (str, int)):
            self.chat_ids = [str(raw_chat_ids).strip()] if str(raw_chat_ids).strip() else []
        elif isinstance(raw_chat_ids, list):
            self.chat_ids = [str(cid).strip() for cid in raw_chat_ids if str(cid).strip()]
        else:
            self.chat_ids = []
        self._cached_username: Optional[str] = None

    def is_configured(self) -> bool:
        """Check if Telegram notifier has the required credentials."""
        return bool(self.bot_token and self.chat_ids and self.bot_token != "YOUR_TELEGRAM_BOT_TOKEN")

    def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """Fetch bot info from Telegram API."""
        if not self.bot_token:
            return None
        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    self._cached_username = data["result"].get("username")
                    return data["result"]
        except Exception as e:
            logger.debug(f"[TelegramNotifier] Failed to fetch getMe: {e}")
        return None

    def get_recent_chat_ids(self) -> List[Dict[str, Any]]:
        """Fetch recent chat updates to help user discover their chat ID."""
        if not self.bot_token:
            return []
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = []
                seen_ids = set()
                if data.get("ok"):
                    for u in data.get("result", []):
                        msg = u.get("message") or u.get("channel_post") or {}
                        chat = msg.get("chat")
                        if chat and chat.get("id") not in seen_ids:
                            seen_ids.add(chat.get("id"))
                            results.append(chat)
                return results
        except Exception:
            return []

    def send_alert(self, listing: Listing) -> Tuple[bool, str]:
        """Send an alert message for a re-rental listing."""
        if not self.enabled:
            return False, "Telegram notifier is disabled in configuration."
        if not self.is_configured():
            return False, "Telegram Bot Token or Chat ID is not configured."

        message_html = listing.to_telegram_html()
        return self._post_message(message_html)

    def send_test_message(self) -> Tuple[bool, str]:
        """Send a test message to verify the bot and chat ID configuration."""
        if not self.is_configured():
            return False, "Telegram credentials are incomplete. Please set bot_token and chat_id."

        test_msg = (
            "✅ <b>ReRental Alert Service: Test Successful!</b>\n\n"
            "Your Telegram alerts are properly configured.\n"
            "You will receive immediate notifications here whenever a matching NYC re-rental is posted."
        )
        return self._post_message(test_msg)

    def _post_message(self, text_html: str) -> Tuple[bool, str]:
        if not self.chat_ids:
            return False, "No chat_ids configured"

        success_count = 0
        last_error = ""

        for cid in self.chat_ids:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": cid,
                "text": text_html,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    if resp_data.get("ok"):
                        success_count += 1
                    else:
                        err = resp_data.get("description", "Unknown Telegram API error")
                        logger.error(f"[TelegramNotifier] API error for {cid}: {err}")
                        last_error = err
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                logger.error(f"[TelegramNotifier] HTTP {e.code} for {cid}: {err_body}")

                if "chat not found" in err_body.lower():
                    bot_info = self.get_bot_info()
                    username = bot_info.get("username", "your bot") if bot_info else "rerentalbot_bot"
                    last_error = (
                        f"Chat not found for {cid}. Telegram bots CANNOT start conversations with you.\n"
                        f"👉 Fix: Open Telegram, search for @{username} (or open https://t.me/{username}), "
                        f"and click the 'START' button (or send /start). Then re-run the test."
                    )
                else:
                    last_error = f"HTTP Error {e.code}: {err_body}"
            except Exception as e:
                logger.error(f"[TelegramNotifier] Network error for {cid}: {e}")
                last_error = str(e)

        if success_count > 0:
            logger.info(f"[TelegramNotifier] Alert dispatched to {success_count}/{len(self.chat_ids)} recipients.")
            return True, f"Sent to {success_count}/{len(self.chat_ids)} recipients"
        return False, last_error
