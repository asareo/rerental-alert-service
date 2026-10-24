import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from models import Listing
from database import Database

print("Running component tests...")

# 1. Test Filter Matching
listing = Listing(
    id="test_1",
    title="2BR in Brooklyn · $2,200/mo",
    address="100 Atlantic Ave",
    borough="Brooklyn",
    neighborhood="Cobble Hill",
    rent=2200.0,
    rent_str="$2,200/mo",
    beds="2BR",
    ami="80% AMI",
    household_size="2-4 people",
    apply_url="https://example.com/apply"
)

# Test rent filters
pass_match, _ = listing.matches_filter({"max_rent": 2500})
assert pass_match, "Should pass max_rent 2500"

fail_match, reason = listing.matches_filter({"max_rent": 2000})
assert not fail_match, f"Should fail max_rent 2000: {reason}"

# Test borough filters
pass_b, _ = listing.matches_filter({"allowed_boroughs": ["Brooklyn", "Queens"]})
assert pass_b, "Should pass Brooklyn"

fail_b, reason = listing.matches_filter({"allowed_boroughs": ["Manhattan"]})
assert not fail_b, f"Should fail Manhattan filter: {reason}"

# Test beds filters
pass_beds, _ = listing.matches_filter({"allowed_beds": ["2BR", "3BR"]})
assert pass_beds, "Should pass 2BR"

fail_beds, reason = listing.matches_filter({"allowed_beds": ["Studio", "1BR"]})
assert not fail_beds, f"Should fail Studio/1BR: {reason}"

# 2. Test Telegram and Email HTML generation
tg_html = listing.to_telegram_html()
assert "2BR in Brooklyn" in tg_html
assert "https://example.com/apply" in tg_html
print("Telegram HTML format: OK")

email_html = listing.to_email_html()
assert "$2,200" in email_html
assert "https://example.com/apply" in email_html
print("Email HTML format: OK")

# 3. Test Database
test_db_path = Path(__file__).parent / "test_test.db"
if test_db_path.exists():
    test_db_path.unlink()

db = Database(test_db_path)
assert not db.is_listing_seen("test_1")
db.mark_listing_seen(listing)
assert db.is_listing_seen("test_1")
db.record_notification("test_1", "telegram", "sent")
stats = db.get_stats()
assert stats["total_seen"] == 1
assert stats["telegram_alerts_sent"] == 1
print("Database persistence: OK")

if test_db_path.exists():
    test_db_path.unlink()

print("ALL TESTS PASSED SUCCESSFULLY! ✅")
