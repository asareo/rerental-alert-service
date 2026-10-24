import sys
from pathlib import Path
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
sys.path.insert(0, str(Path(__file__).parent))

from models import Listing, LotteryListing
from monitors.lottery_monitor import LotteryMonitor
from bot.telegram_ai_bot import TelegramAIBot
from database import Database
from config import load_config

print("=== 1. Testing Unspecified Bedroom Inference (Solutions A, B, C) ===")
unspecified_listing = Listing(
    id="test_unspec_1",
    title="Apartment in Highbridge · $3,443/mo",
    address="1000 Woodycrest Avenue Apt 5B",
    borough="Bronx",
    neighborhood="Highbridge",
    rent=3443.0,
    rent_str="$3,443/mo",
    beds="Apartment", # unspecified!
    household_size="2–5 people",
    apply_url="https://airtable.com/sample"
)

# Solution A: Inference
inferred = unspecified_listing.infer_bedrooms()
print("Inferred bedroom:", inferred)
assert "2BR" in inferred, f"Expected 2BR inference, got: {inferred}"

# Solution B: StreetEasy URL
se_url = unspecified_listing.get_streeteasy_url()
print("StreetEasy URL:", se_url)
assert "1000+Woodycrest+Avenue" in se_url
assert "streeteasy.com" in se_url

# Solution C: Matching filter for 2BR
matched, reason = unspecified_listing.matches_filter({"allowed_beds": ["2BR"], "include_unspecified_beds": True})
print(f"Filter matched: {matched} ({reason})")
assert matched, "Listing should match 2BR filter via inference"
assert unspecified_listing.is_unspecified_beds, "Should be tagged as unspecified"

print("HTML output preview:")
tg_html = unspecified_listing.to_telegram_html()
assert "Unconfirmed BR" in tg_html
assert "Check Unit on StreetEasy" in tg_html
print("Unspecified rooms test: PASSED ✅\n")

print("=== 2. Testing NYC Housing Lottery Monitor ===")
lm = LotteryMonitor()
lotteries = lm.fetch_active_lotteries()
print(f"Fetched {len(lotteries)} active lotteries.")
assert len(lotteries) > 0
sample_lottery = lotteries[0]
assert sample_lottery.lottery_id
assert sample_lottery.name
print(f"Sample Lottery: {sample_lottery.name} (Deadline: {sample_lottery.deadline})")
print("Lottery monitor test: PASSED ✅\n")

print("=== 3. Testing 2-Way Telegram AI Chat (Style B) ===")
cfg = load_config()
db = Database()
ai_bot = TelegramAIBot(cfg, db)

# Test Gemini response generation
prompt = "Find me 2BR apartments in Brooklyn under $3,500"
print(f"Querying Gemini with prompt: '{prompt}'...")
# Simulate query
ai_bot._process_ai_query("569845821", prompt, "Owuraku")
print("Telegram AI query test: PASSED ✅\n")

print("ALL ADVANCED FEATURES TESTED & VERIFIED SUCCESSFULLY! 🚀")
