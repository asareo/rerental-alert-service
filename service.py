"""
service.py
Core daemon engine that orchestrates polling, deduplication, filtering,
and dispatching instant alerts via Telegram and Email.
"""

import time
import datetime
import logging
from typing import Dict, Any, Optional
from database import Database
from monitors.aggregator import ListingAggregator
from notifiers.telegram_notifier import TelegramNotifier
from notifiers.email_notifier import EmailNotifier
from config import load_config

logger = logging.getLogger("rerental_service")


class ReRentalService:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_config()
        self.db = Database()
        self.telegram = TelegramNotifier(self.config.get("telegram", {}))
        self.email = EmailNotifier(self.config.get("email", {}))
        self.aggregator = ListingAggregator(self.db, self.config.get("filters", {}))
        self.poll_interval = max(15, int(self.config.get("poll_interval_seconds", 60)))
        self.running = False

    def initialize_if_needed(self):
        """Establish baseline on initial run if not already done."""
        stats = self.db.get_stats()
        is_first_run = stats["total_seen"] == 0

        if is_first_run and self.config.get("baseline_on_first_run", True):
            logger.info("=" * 60)
            logger.info("First run detected: Establishing baseline of active listings...")
            logger.info("This avoids spamming your inbox/Telegram with hundreds of old listings.")
            logger.info("=" * 60)
            self.aggregator.check_for_new_listings(is_initial_run=True)
            new_stats = self.db.get_stats()
            logger.info(f"Baseline established! {new_stats['total_seen']} active listings cataloged.")
            logger.info("From now on, ANY newly posted re-rental will trigger an instant alert.")
            logger.info("=" * 60)

    def run_check_cycle(self) -> int:
        """
        Execute one check cycle across all monitored feeds.
        Returns number of new matching alerts dispatched.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.set_meta("last_check_time", now_str)
        logger.info(f"[{now_str}] Polling monitored sources for new re-rentals...")

        matches = self.aggregator.check_for_new_listings(is_initial_run=False)
        dispatched_count = 0

        for listing, reason in matches:
            logger.info(f"🚨 DISPATCHING ALERT for: {listing.title} ({listing.address})")

            # 1. Dispatch Telegram notification
            if self.telegram.enabled:
                success, msg = self.telegram.send_alert(listing)
                status = "sent" if success else "failed"
                self.db.record_notification(listing.id, "telegram", status, msg)
                if not success:
                    logger.warning(f"[Service] Telegram alert failed: {msg}")

            # 2. Dispatch Email notification
            if self.email.enabled:
                success, msg = self.email.send_alert(listing)
                status = "sent" if success else "failed"
                self.db.record_notification(listing.id, "email", status, msg)
                if not success:
                    logger.warning(f"[Service] Email alert failed: {msg}")

            dispatched_count += 1

        if dispatched_count == 0:
            logger.info("No new matching re-rentals found in this cycle.")
        else:
            logger.info(f"✅ Successfully processed {dispatched_count} new alerts.")

        return dispatched_count

    def start_loop(self):
        """Start continuous background monitoring loop."""
        self.running = True
        self.initialize_if_needed()

        logger.info(f"Monitoring service active. Polling every {self.poll_interval} seconds.")
        logger.info("Press Ctrl+C to stop.")

        try:
            while self.running:
                try:
                    self.run_check_cycle()
                except Exception as e:
                    logger.error(f"[Service] Error during check cycle: {e}", exc_info=True)

                # Sleep interval
                for _ in range(self.poll_interval):
                    if not self.running:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Monitoring service stopped by user.")
        finally:
            self.running = False
