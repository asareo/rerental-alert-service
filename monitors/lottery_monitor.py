"""
monitors/lottery_monitor.py
Monitors NYC Housing Connect advertised lotteries via NYC Open Data API (dataset vy5i-a666).
Fetches active housing lotteries directly from NYC Housing Preservation & Development (HPD).
"""

import urllib.request
import json
import ssl
import logging
from typing import List, Optional
from models import LotteryListing

logger = logging.getLogger(__name__)

NYC_OPEN_DATA_LOTTERIES_URL = "https://data.cityofnewyork.us/resource/vy5i-a666.json"
USER_AGENT = "NYC-Housing-Alert-Service/2.0"


class LotteryMonitor:
    def __init__(self, endpoint_url: str = NYC_OPEN_DATA_LOTTERIES_URL):
        self.endpoint_url = endpoint_url
        self.ssl_ctx = ssl._create_unverified_context()

    def fetch_active_lotteries(self) -> List[LotteryListing]:
        """Fetch all currently active NYC Housing Connect lotteries."""
        req = urllib.request.Request(
            self.endpoint_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"[LotteryMonitor] Failed to query NYC Open Data lotteries: {e}")
            return []

        active_lotteries: List[LotteryListing] = []
        for item in data:
            status = (item.get("lottery_status") or "").strip()
            if status != "Active":
                continue

            lottery = self._parse_lottery_item(item)
            if lottery:
                active_lotteries.append(lottery)

        # Sort newest first by start date
        active_lotteries.sort(key=lambda x: x.start_date or "", reverse=True)
        return active_lotteries

    def _parse_lottery_item(self, item: dict) -> Optional[LotteryListing]:
        lottery_id = str(item.get("lottery_id", "")).strip()
        if not lottery_id:
            return None

        status = (item.get("lottery_status") or "").strip()
        name = item.get("lottery_name", "").strip() or f"NYC Housing Lottery #{lottery_id}"
        borough = item.get("borough", "").strip().upper()
        deadline = item.get("lottery_end_date", "")
        start_date = item.get("lottery_start_date", "")

        def parse_int(v):
            try:
                return int(v) if v is not None else 0
            except ValueError:
                return 0

        total_units = parse_int(item.get("unit_count"))
        u_1bed = parse_int(item.get("unit_distribution_1bed"))
        u_2bed = parse_int(item.get("unit_distribution_2bed"))
        u_3bed = parse_int(item.get("unit_distribution_3bed"))

        # Income AMI tiers summary
        ami_parts = []
        if parse_int(item.get("applied_income_ami_extremely_low")) > 0:
            ami_parts.append("Extremely Low")
        if parse_int(item.get("applied_income_ami_very_low")) > 0:
            ami_parts.append("Very Low")
        if parse_int(item.get("applied_income_ami_low")) > 0:
            ami_parts.append("Low")
        if parse_int(item.get("applied_income_ami_moderate")) > 0:
            ami_parts.append("Moderate")
        if parse_int(item.get("applied_income_ami_middle")) > 0:
            ami_parts.append("Middle AMI")

        ami_tiers = ", ".join(ami_parts) if ami_parts else "See Housing Connect"
        postcode = item.get("postcode", "")
        apply_url = f"https://housingconnect.nyc.gov/PublicWeb/details/lottery-details/{lottery_id}"

        return LotteryListing(
            lottery_id=lottery_id,
            name=name,
            borough=borough,
            status=status,
            deadline=deadline,
            start_date=start_date,
            total_units=total_units,
            units_1bed=u_1bed,
            units_2bed=u_2bed,
            units_3bed=u_3bed,
            ami_tiers=ami_tiers,
            postcode=postcode,
            apply_url=apply_url,
            raw_data=item
        )
