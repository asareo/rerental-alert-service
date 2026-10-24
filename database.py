"""
database.py
SQLite persistence layer for tracking seen re-rental listings and alert history.
"""

import sqlite3
import json
import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import contextmanager

DB_FILE = Path(__file__).parent / "rerentals.db"


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_listings (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    address TEXT,
                    rent REAL,
                    beds TEXT,
                    borough TEXT,
                    apply_url TEXT,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications_sent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id TEXT,
                    channel TEXT,
                    status TEXT,
                    error_message TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(listing_id) REFERENCES seen_listings(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_listing_seen(self, listing_id: str) -> bool:
        """Check if a listing ID has already been recorded."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_listings WHERE id = ?", (listing_id,))
            return cursor.fetchone() is not None

    def mark_listing_seen(self, listing, is_baseline: bool = False):
        """Save a new listing to seen_listings."""
        with self._connection() as conn:
            cursor = conn.cursor()
            raw_data = json.dumps(listing.raw_data or {})
            cursor.execute("""
                INSERT OR IGNORE INTO seen_listings 
                (id, source, address, rent, beds, borough, apply_url, first_seen_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (
                listing.id,
                listing.source,
                listing.address,
                listing.rent,
                listing.beds,
                listing.borough,
                listing.apply_url,
                raw_data
            ))
            conn.commit()

    def record_notification(self, listing_id: str, channel: str, status: str, error_message: str = ""):
        """Record a notification dispatch attempt (Telegram or Email)."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notifications_sent (listing_id, channel, status, error_message, sent_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (listing_id, channel, status, error_message))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Return system and alerting statistics."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_listings")
            total_seen = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications_sent WHERE channel = 'telegram' AND status = 'sent'")
            telegram_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications_sent WHERE channel = 'email' AND status = 'sent'")
            email_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT value FROM system_meta WHERE key = 'last_check_time'")
            row = cursor.fetchone()
            last_check = row[0] if row else "Never"

            return {
                "total_seen": total_seen,
                "telegram_alerts_sent": telegram_alerts,
                "email_alerts_sent": email_alerts,
                "last_check_time": last_check
            }

    def set_meta(self, key: str, value: str):
        """Set a metadata value."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_meta (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (key, value))
            conn.commit()

    def get_recent_listings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recently discovered listings."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, source, address, rent, beds, borough, apply_url, first_seen_at
                FROM seen_listings
                ORDER BY first_seen_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_alerts(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return recent notifications history."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT n.id, n.listing_id, n.channel, n.status, n.error_message, n.sent_at,
                       s.address, s.rent, s.beds
                FROM notifications_sent n
                LEFT JOIN seen_listings s ON n.listing_id = s.id
                ORDER BY n.sent_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
