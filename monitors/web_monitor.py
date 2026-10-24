"""
monitors/web_monitor.py
Monitors rerentalalert.com/browse catalog for new affordable housing re-rentals.
Fetches detailed application links, income limits, and transit info.
"""

import urllib.request
import re
import json
import logging
from typing import List, Dict, Any, Optional
from models import Listing

logger = logging.getLogger(__name__)

BROWSE_URL = "https://rerentalalert.com/browse"
BASE_URL = "https://rerentalalert.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

BOROUGH_MAP = {
    "manhattan": "Manhattan",
    "brooklyn": "Brooklyn",
    "queens": "Queens",
    "bronx": "Bronx",
    "staten island": "Staten Island",
    # Common neighborhoods
    "harlem": "Manhattan",
    "washington heights": "Manhattan",
    "inwood": "Manhattan",
    "chelsea": "Manhattan",
    "east village": "Manhattan",
    "lower east side": "Manhattan",
    "midtown": "Manhattan",
    "upper east side": "Manhattan",
    "upper west side": "Manhattan",
    "bedford-stuyvesant": "Brooklyn",
    "bed-stuy": "Brooklyn",
    "williamsburg": "Brooklyn",
    "bushwick": "Brooklyn",
    "crown heights": "Brooklyn",
    "flatbush": "Brooklyn",
    "greenpoint": "Brooklyn",
    "sunset park": "Brooklyn",
    "astoria": "Queens",
    "long island city": "Queens",
    "sunnyside": "Queens",
    "woodside": "Queens",
    "jackson heights": "Queens",
    "flushing": "Queens",
    "jamaica": "Queens",
    "mott haven": "Bronx",
    "concourse": "Bronx",
    "bedford park": "Bronx",
    "highbridge": "Bronx",
    "fordham": "Bronx",
    "soundview": "Bronx"
}


class WebCatalogMonitor:
    def __init__(self, browse_url: str = BROWSE_URL):
        self.browse_url = browse_url

    def fetch_listings(self, fetch_details: bool = True, max_details: int = 15) -> List[Listing]:
        """Fetch active listings from the browse catalog."""
        req = urllib.request.Request(
            self.browse_url,
            headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                page_html = resp.read().decode("utf-8")
        except Exception as e:
            logger.error(f"[WebMonitor] Failed to fetch browse page: {e}")
            return []

        match = re.search(r'(\[{"addr":.*?}\])', page_html)
        if not match:
            logger.warning("[WebMonitor] Could not find listing catalog JSON on browse page.")
            return []

        try:
            items: List[Dict[str, Any]] = json.loads(match.group(1))
        except Exception as e:
            logger.error(f"[WebMonitor] Failed to parse catalog JSON: {e}")
            return []

        listings: List[Listing] = []
        details_fetched = 0

        # Prioritize items marked 'new' first, then normal order
        sorted_items = sorted(items, key=lambda x: 0 if x.get("new") else 1)

        for item in sorted_items:
            try:
                listing = self._convert_item(item)
                if not listing:
                    continue

                # If requested and within budget, fetch detail page for apply link and income limits
                if fetch_details and details_fetched < max_details and listing.detail_url:
                    # Enrich newly marked items or items without an apply_url
                    if item.get("new") or not listing.apply_url:
                        self._enrich_listing(listing)
                        details_fetched += 1

                listings.append(listing)
            except Exception as e:
                logger.warning(f"[WebMonitor] Error processing listing {item.get('addr')}: {e}")

        return listings

    def _convert_item(self, item: Dict[str, Any]) -> Optional[Listing]:
        addr = (item.get("addr") or "").strip()
        if not addr:
            return None

        hood = (item.get("hood") or "").strip()
        rent_val = item.get("rent")
        rent_str = str(rent_val).strip() if rent_val is not None else ""
        rent = Listing.parse_rent_number(rent_str)
        
        beds_val = item.get("beds")
        beds = str(beds_val).strip().upper() if beds_val is not None else ""
        if not beds or beds == "NOT PUBLISHED":
            beds = "Apartment"

        rel_url = str(item.get("url") or "")
        detail_url = f"{BASE_URL}{rel_url}" if rel_url.startswith("/") else rel_url

        # Generate a stable unique ID
        listing_id = rel_url.replace("/listing/", "web_").replace("%7C", "_").replace("|", "_")
        if not listing_id or listing_id == "web_":
            listing_id = f"web_{re.sub(r'[^a-zA-Z0-9]', '', addr.lower())}_{rent or '0'}"

        borough = self._infer_borough(addr, hood)

        title = f"{beds} in {borough} · {rent_str}" if borough else f"{beds} · {rent_str}"

        return Listing(
            id=listing_id,
            title=title,
            address=addr,
            neighborhood=hood,
            borough=borough,
            rent=rent,
            rent_str=rent_str,
            beds=beds,
            source="NYC Affordable Housing Catalog",
            detail_url=detail_url,
            raw_data=item
        )

    def _infer_borough(self, address: str, hood: str) -> str:
        text = f"{hood} {address}".lower()
        for key, b_name in BOROUGH_MAP.items():
            if key in text:
                return b_name
        return ""

    def _enrich_listing(self, listing: Listing):
        """Fetch individual listing detail page to populate apply link, agency source, and income limits."""
        if not listing.detail_url:
            return

        req = urllib.request.Request(
            listing.detail_url,
            headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                d_html = resp.read().decode("utf-8")
        except Exception:
            return

        # 1. Apply link: check .apply-actions or class="btn"
        apply_m = re.search(r'<div class="apply-actions">\s*<a[^>]*href="([^"]+)"', d_html)
        if not apply_m:
            apply_m = re.search(r'href="([^"]+)"[^>]*>Apply on ', d_html)
        if not apply_m:
            apply_m = re.search(r'href="(https?://[^"]+)"[^>]*class="[^"]*btn[^"]*"[^>]*>(?:Apply|Get the application)', d_html)
        if apply_m:
            listing.apply_url = apply_m.group(1).strip()

        # 2. Source / Listed By
        source_m = re.search(r'Listed by\s+([^<\n]+)', d_html)
        if source_m:
            listing.source = source_m.group(1).strip()

        # 3. Household size
        hh_m = re.search(r'Household size\s*</p>\s*<p[^>]*>([^<]+)', d_html)
        if not hh_m:
            hh_m = re.search(r'Household size.*?(\d+[–\-]\d+\s*people)', d_html, re.DOTALL)
        if hh_m:
            listing.household_size = hh_m.group(1).strip()

        # 4. Subway lines
        subways = re.findall(r'<span class="subway-bullet[^"]*">([^<]+)</span>', d_html)
        if subways:
            listing.subway_lines = [s.strip() for s in subways]
