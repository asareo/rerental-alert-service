"""
monitors/aggregator.py
Aggregates listings from Telegram and Web catalog monitors, deduplicates,
and filters candidates against user preferences.
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from models import Listing
from database import Database
from monitors.telegram_monitor import TelegramMonitor
from monitors.web_monitor import WebCatalogMonitor

logger = logging.getLogger(__name__)


def normalize_address_key(addr: str) -> str:
    """Normalize street address for cross-source deduplication."""
    if not addr:
        return ""
    text = addr.lower().strip()
    # Strip unit/apt info
    text = re.sub(r"(?:apt|unit|suite|#|fl|floor)\s*[a-z0-9\-]+", "", text)
    # Standardize street suffixes
    replacements = {
        r"\bavenue\b": "ave",
        r"\bstreet\b": "st",
        r"\bboulevard\b": "blvd",
        r"\broad\b": "rd",
        r"\bplace\b": "pl",
        r"\bdrive\b": "dr",
        r"\blane\b": "ln",
        r"\bcourt\b": "ct",
        r"\bterrace\b": "ter"
    }
    for pat, rep in replacements.items():
        text = re.sub(pat, rep, text)
    # Strip non-alphanumeric
    cleaned = re.sub(r"[^a-z0-9]", "", text)
    return cleaned


class ListingAggregator:
    def __init__(self, db: Database, filters: Dict[str, Any]):
        self.db = db
        self.filters = filters or {}
        self.tg_monitor = TelegramMonitor()
        self.web_monitor = WebCatalogMonitor()

    def check_for_new_listings(self, is_initial_run: bool = False) -> List[Tuple[Listing, str]]:
        """
        Poll sources, deduplicate, filter against user preferences.
        Returns list of tuples: (Listing, match_reason).
        
        If is_initial_run=True, mark active listings as baseline without triggering
        a flood of historic notifications, unless user explicitly opted to alert on initial.
        """
        logger.info("[Aggregator] Fetching from Telegram feed...")
        tg_listings = self.tg_monitor.fetch_listings()
        logger.info(f"[Aggregator] Telegram returned {len(tg_listings)} listings.")

        logger.info("[Aggregator] Fetching from Web catalog...")
        web_listings = self.web_monitor.fetch_listings(fetch_details=True, max_details=10)
        logger.info(f"[Aggregator] Web catalog returned {len(web_listings)} listings.")

        # Combine, processing Telegram first (since Telegram usually has the latest real-time drop)
        all_candidates = tg_listings + web_listings

        new_matches: List[Tuple[Listing, str]] = []
        seen_in_this_cycle = set()

        for listing in all_candidates:
            # 1. Primary check: Has this exact ID already been recorded?
            if self.db.is_listing_seen(listing.id):
                continue

            # 2. Cross-source check: Match normalized address key + rent
            norm_key = (normalize_address_key(listing.address), round(listing.rent or 0, -1))
            if norm_key in seen_in_this_cycle and norm_key[0]:
                # Already processed from another feed in this cycle
                self.db.mark_listing_seen(listing)
                continue

            seen_in_this_cycle.add(norm_key)

            # Record in DB so it won't be considered again
            self.db.mark_listing_seen(listing)

            # 3. If baseline initialization, do not alert
            if is_initial_run:
                continue

            # 4. Check if listing matches user filter settings
            matched, reason = listing.matches_filter(self.filters)
            if matched:
                logger.info(f"[Aggregator] MATCH FOUND: {listing.title} ({listing.address}) - {reason}")
                new_matches.append((listing, reason))
            else:
                logger.debug(f"[Aggregator] Listing filtered out: {listing.title} - {reason}")

        return new_matches
