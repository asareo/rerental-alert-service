"""
bot/telegram_ai_bot.py
Interactive 2-way AI Telegram Chatbot powered by Google Gemini.
Allows users to chat with their bot in natural English to search re-rentals,
query NYC housing lotteries, and update their alert filters directly from phone.
"""

import urllib.request
import urllib.parse
import json
import threading
import time
import logging
import re
from typing import Dict, Any, List, Optional
from database import Database
from config import load_config, save_config

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"


class TelegramAIBot:
    def __init__(self, config: Dict[str, Any], db: Database):
        self.config = config
        self.db = db
        self.bot_token = config.get("telegram", {}).get("bot_token", "").strip()
        raw_chats = config.get("telegram", {}).get("chat_ids") or config.get("telegram", {}).get("chat_id") or []
        if isinstance(raw_chats, (str, int)):
            self.chat_ids = [str(raw_chats).strip()]
        elif isinstance(raw_chats, list):
            self.chat_ids = [str(c).strip() for c in raw_chats if str(c).strip()]
        else:
            self.chat_ids = []
            
        self.gemini_key = config.get("gemini_api_key", "").strip()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_update_id = 0

    def start(self):
        """Start the Telegram polling listener in a daemon thread."""
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            logger.warning("[TelegramAIBot] Bot token not configured. AI listener disabled.")
            return

        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True, name="TelegramAIBotWorker")
        self.thread.start()
        logger.info("[TelegramAIBot] Interactive AI chat listener started.")

    def stop(self):
        self.running = False

    def _polling_loop(self):
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=20"
                req = urllib.request.Request(url, headers={"User-Agent": "TelegramAIBot/2.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if data.get("ok"):
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        msg = update.get("message")
                        if msg and msg.get("text"):
                            self._handle_incoming_message(msg)
            except Exception as e:
                time.sleep(2)

    def _handle_incoming_message(self, msg: Dict[str, Any]):
        chat_id = str(msg["chat"]["id"])
        user_name = msg["from"].get("first_name", "User")
        text = msg.get("text", "").strip()

        # If user isn't in chat_ids, auto-register them
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)
            cfg = load_config()
            cfg["telegram"]["chat_ids"] = self.chat_ids
            save_config(cfg)
            logger.info(f"[TelegramAIBot] Registered new chat_id: {chat_id} ({user_name})")

        logger.info(f"[TelegramAIBot] Received message from {user_name} ({chat_id}): '{text}'")

        # 1. Quick commands
        if text.startswith("/start") or text.startswith("/help"):
            reply = (
                f"👋 <b>Hey {user_name}! I'm your NYC Housing Assistant.</b>\n\n"
                "You can chat with me naturally or give me commands:\n\n"
                "• <i>\"Find me 2BR apartments in Brooklyn under $3,500\"</i>\n"
                "• <i>\"Show me active housing lotteries in Queens\"</i>\n"
                "• <i>\"What's the newest re-rental posted today?\"</i>\n"
                "• <i>\"Change my max rent to $4,000\"</i>\n"
                "• <i>\"Show me recent listings with unconfirmed 2BRs\"</i>\n\n"
                "Ask me anything and I'll find the best matching units with direct application links!"
            )
            self._send_telegram_reply(chat_id, reply)
            return

        if text.startswith("/stats"):
            stats = self.db.get_stats()
            reply = (
                f"📊 <b>ReRental & Lottery Stats</b>\n\n"
                f"• Tracked re-rentals: <b>{stats['total_seen']}</b>\n"
                f"• Alerts sent: <b>{stats['telegram_alerts_sent']}</b>\n"
                f"• Last checked: <code>{stats['last_check_time']}</code>"
            )
            self._send_telegram_reply(chat_id, reply)
            return

        # 2. Process query with Gemini AI and local database search
        self._process_ai_query(chat_id, text, user_name)

    def _process_ai_query(self, chat_id: str, user_text: str, user_name: str):
        # Check if user wants to update filters (e.g. "change max rent to 3500", "set borough to Queens")
        filter_updated = self._check_and_update_filter(user_text)
        if filter_updated:
            self._send_telegram_reply(chat_id, filter_updated)
            return

        # Extract search keywords and query the database
        borough = None
        for b in ["manhattan", "brooklyn", "queens", "bronx", "staten island"]:
            if b in user_text.lower():
                borough = b.title()
                break

        beds = None
        if "studio" in user_text.lower():
            beds = "Studio"
        elif "1br" in user_text.lower() or "1 bed" in user_text.lower() or "one bed" in user_text.lower():
            beds = "1BR"
        elif "2br" in user_text.lower() or "2 bed" in user_text.lower() or "two bed" in user_text.lower():
            beds = "2BR"
        elif "3br" in user_text.lower() or "3 bed" in user_text.lower() or "three bed" in user_text.lower():
            beds = "3BR"

        max_rent = None
        m_rent = re.search(r'\$?(\d{1,2}(?:,\d{3})|\d{4})\b', user_text)
        if m_rent:
            try:
                max_rent = float(m_rent.group(1).replace(",", ""))
            except ValueError:
                pass

        # Check if user asked about lotteries
        wants_lottery = any(w in user_text.lower() for w in ["lottery", "lotteries", "housing connect"])

        listings_context = []
        if wants_lottery:
            lotteries = self.db.get_active_lotteries(limit=8)
            for l in lotteries:
                listings_context.append(
                    f"LOTTERY: {l['name']} | Borough: {l['borough']} | Units: {l['total_units']} | Deadline: {l['deadline']} | Apply: {l['apply_url']}"
                )
        else:
            db_results = self.db.search_listings(borough=borough, max_rent=max_rent, beds=beds, limit=8)
            for r in db_results:
                rent_s = f"${r['rent']:,.0f}/mo" if r['rent'] else "Rent unlisted"
                clean_addr = re.sub(r'#\w+|apt\.?\s*\w+', '', r['address'], flags=re.IGNORECASE).strip()
                se_url = f"https://streeteasy.com/search?q={urllib.parse.quote_plus(clean_addr + ' NYC')}"
                listings_context.append(
                    f"RE-RENTAL: {r['address']} ({r['borough']}) - {r['beds'] or 'Apartment'} - {rent_s} - Source: {r['source']} - Apply: {r['apply_url']} - StreetEasy: {se_url}"
                )

        # Formulate prompt for Gemini
        system_instruction = (
            f"You are a friendly, expert NYC Housing & Re-Rental Assistant chatting with {user_name} on Telegram. "
            "Respond in clear, formatted HTML (use <b>bold</b>, bullet points, emoji). "
            "Always include direct application links (<a href='...'>Apply</a>) and StreetEasy links. "
            "Keep the response concise, punchy, and helpful."
        )

        db_text = "\n".join(listings_context) if listings_context else "No direct matches found in current catalog."

        gemini_prompt = (
            f"{system_instruction}\n\n"
            f"User asked: \"{user_text}\"\n\n"
            f"Current listings matching database query:\n{db_text}\n\n"
            "Formulate the best Telegram response for the user:"
        )

        reply_text = self._call_gemini(gemini_prompt)
        if not reply_text:
            # Fallback if Gemini is unreachable
            if listings_context:
                reply_text = f"Found {len(listings_context)} matching units for you:\n\n" + "\n\n".join(listings_context[:4])
            else:
                reply_text = "I checked our live database but didn't find units matching those exact criteria. Try broadening your rent or borough search!"

        self._send_telegram_reply(chat_id, reply_text)

    def _check_and_update_filter(self, text: str) -> Optional[str]:
        """Detect if user is asking to update their search preferences."""
        text_lower = text.lower()
        if not any(k in text_lower for k in ["change my", "set my", "update my", "filter to", "max rent to"]):
            return None

        cfg = load_config()
        updated = []

        # Rent update
        m_rent = re.search(r'(?:max\s*rent|rent)\s*(?:to|is|=)\s*\$?(\d{1,2}(?:,\d{3})|\d{4})', text_lower)
        if m_rent:
            new_rent = float(m_rent.group(1).replace(",", ""))
            cfg["filters"]["max_rent"] = new_rent
            updated.append(f"Max Rent: <b>${new_rent:,.0f}/mo</b>")

        # Bedrooms update
        if "2br" in text_lower or "2 bed" in text_lower:
            cfg["filters"]["allowed_beds"] = ["2BR"]
            updated.append("Bedrooms: <b>2BR</b>")
        elif "1br" in text_lower or "1 bed" in text_lower:
            cfg["filters"]["allowed_beds"] = ["1BR"]
            updated.append("Bedrooms: <b>1BR</b>")
        elif "studio" in text_lower:
            cfg["filters"]["allowed_beds"] = ["Studio"]
            updated.append("Bedrooms: <b>Studio</b>")

        # Borough update
        for b in ["manhattan", "brooklyn", "queens", "bronx", "staten island"]:
            if b in text_lower:
                cfg["filters"]["allowed_boroughs"] = [b.title()]
                updated.append(f"Borough: <b>{b.title()}</b>")
                break

        if updated:
            save_config(cfg)
            return "✅ <b>Updated your alert filters!</b>\n\n" + "\n".join(f"• {u}" for u in updated)
        return None

    def _call_gemini(self, prompt: str) -> Optional[str]:
        if not self.gemini_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 900}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw_text = parts[0].get("text", "")
                        # Convert markdown bold to Telegram HTML bold
                        formatted = raw_text.replace("**", "<b>").replace("</b>", "</b>")
                        return raw_text
        except Exception as e:
            logger.error(f"[TelegramAIBot] Gemini API error: {e}")
        return None

    def _send_telegram_reply(self, chat_id: str, text: str):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        # Try sending with HTML, fallback to plain text if HTML tags are malformed
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return
        except urllib.error.HTTPError as e:
            # Fallback to plain text
            payload.pop("parse_mode", None)
            clean_text = re.sub(r'<[^>]+>', '', text)
            payload["text"] = clean_text
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[TelegramAIBot] Failed to reply: {e}")
