"""
monitors/telegram_monitor.py
Real-time poller for the public NYC Re-Rental Telegram broadcast channel.
Scrapes https://t.me/s/rerentalalert without requiring any Telegram user account.
"""

import urllib.request
import re
import html
import logging
from typing import List, Optional
from models import Listing

logger = logging.getLogger(__name__)

TELEGRAM_CHANNEL_URL = "https://t.me/s/rerentalalert"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class TelegramMonitor:
    def __init__(self, channel_url: str = TELEGRAM_CHANNEL_URL):
        self.channel_url = channel_url

    def fetch_listings(self) -> List[Listing]:
        """Fetch and parse listings from the Telegram public channel web preview."""
        req = urllib.request.Request(
            self.channel_url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                page_html = resp.read().decode("utf-8")
        except Exception as e:
            logger.error(f"[TelegramMonitor] Failed to fetch channel: {e}")
            return []

        posts = re.findall(
            r'data-post="rerentalalert/(\d+)"(.*?)<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            page_html,
            re.DOTALL
        )

        listings: List[Listing] = []
        for post_id, _, raw_html in posts:
            try:
                listing = self._parse_post(post_id, raw_html)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.warning(f"[TelegramMonitor] Failed to parse post {post_id}: {e}")

        # Return listings newest first
        return list(reversed(listings))

    def _parse_post(self, post_id: str, raw_html: str) -> Optional[Listing]:
        text = html.unescape(raw_html)

        # Extract direct application link if present in message
        apply_match = re.search(r'href="([^"]+)"', text)
        apply_url = apply_match.group(1) if apply_match else ""

        # Clean HTML tags to text
        plain_text = re.sub(r'<br\s*/?>', '\n', text)
        plain_text = re.sub(r'<[^>]+>', '', plain_text).strip()

        lines = [line.strip() for line in plain_text.split('\n') if line.strip()]
        if not lines:
            return None

        title_line = lines[0]

        # Extract Beds, Borough, Rent
        beds = ""
        beds_match = re.search(r'(Studio|\d+BR|\d+\s*bedroom|Apartment)', title_line, re.IGNORECASE)
        if beds_match:
            beds = beds_match.group(1).upper()

        borough = ""
        borough_match = re.search(r'\bin\s+(Manhattan|Brooklyn|Queens|Bronx|Staten Island)', title_line, re.IGNORECASE)
        if borough_match:
            borough = borough_match.group(1).title()

        rent_str = ""
        rent = None
        rent_match = re.search(r'(\$[\d,]+(?:\.\d+)?(?:/mo)?)', title_line)
        if rent_match:
            rent_str = rent_match.group(1)
            rent = Listing.parse_rent_number(rent_str)

        # Extract Address and AMI
        address = ""
        ami = ""
        for line in lines:
            if '📍' in line:
                clean_loc = line.replace('📍', '').strip()
                if '·' in clean_loc:
                    parts = clean_loc.split('·')
                    address = parts[0].strip()
                    ami = parts[1].strip()
                else:
                    address = clean_loc
                break

        # If borough wasn't in title, check address line or whole text
        if not borough:
            for b in ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]:
                if b.lower() in plain_text.lower():
                    borough = b
                    break

        # Extract Income limits
        income_limits = ""
        if "Income limits:" in plain_text:
            idx = plain_text.find("Income limits:")
            sub = plain_text[idx + len("Income limits:"):].strip()
            end_idx = sub.find("Apply here:") if "Apply here:" in sub else len(sub)
            income_limits = sub[:end_idx].strip()

        clean_title = title_line.replace('🏠', '').strip()

        return Listing(
            id=f"tg_{post_id}",
            title=clean_title,
            address=address,
            borough=borough,
            rent=rent,
            rent_str=rent_str,
            beds=beds,
            ami=ami,
            income_limits=income_limits,
            source="NYC Re-Rental Broadcast",
            apply_url=apply_url,
            detail_url=f"https://t.me/rerentalalert/{post_id}",
            raw_data={"post_id": post_id, "raw_text": plain_text}
        )
