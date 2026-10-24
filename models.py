"""
models.py
Data models and formatting for ReRental listings and alerts.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Tuple
import datetime
import html
import re


@dataclass
class Listing:
    id: str
    title: str = ""
    address: str = ""
    neighborhood: str = ""
    borough: str = ""
    rent: Optional[float] = None
    rent_str: str = ""
    beds: str = ""
    ami: str = ""
    income_limits: str = ""
    household_size: str = ""
    source: str = ""
    apply_url: str = ""
    detail_url: str = ""
    subway_lines: List[str] = field(default_factory=list)
    amenities: List[str] = field(default_factory=list)
    posted_at: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_rent_number(cls, rent_str: str) -> Optional[float]:
        """Extract numeric rent from string like '$3,492/mo' or '$3,492' or '3492'."""
        if not rent_str:
            return None
        cleaned = re.sub(r"[^\d.]", "", rent_str)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def matches_filter(self, filters: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluate listing against user filter criteria.
        Returns (is_match, reason).
        """
        if not filters:
            return True, "No filters configured (all listings pass)"

        # 1. Max Rent filter
        max_rent = filters.get("max_rent")
        if max_rent is not None and max_rent > 0:
            if self.rent is not None:
                if self.rent > float(max_rent):
                    return False, f"Rent ${self.rent:,.0f} exceeds max rent of ${max_rent:,.0f}"

        # 2. Min Rent filter
        min_rent = filters.get("min_rent")
        if min_rent is not None and min_rent > 0:
            if self.rent is not None:
                if self.rent < float(min_rent):
                    return False, f"Rent ${self.rent:,.0f} is below min rent of ${min_rent:,.0f}"

        # 3. Bedroom filter
        allowed_beds = filters.get("allowed_beds")
        if allowed_beds and isinstance(allowed_beds, list) and len(allowed_beds) > 0:
            allowed_beds_normalized = [b.lower().strip() for b in allowed_beds if b.strip()]
            if allowed_beds_normalized:
                beds_norm = self.beds.lower().strip()
                # Check for match (e.g. '1br', 'studio', '2 bedroom')
                matched = any(
                    target in beds_norm or beds_norm in target
                    for target in allowed_beds_normalized
                )
                if not matched:
                    return False, f"Bedrooms '{self.beds}' does not match allowed: {', '.join(allowed_beds)}"

        # 4. Borough filter
        allowed_boroughs = filters.get("allowed_boroughs")
        if allowed_boroughs and isinstance(allowed_boroughs, list) and len(allowed_boroughs) > 0:
            allowed_boroughs_norm = [b.lower().strip() for b in allowed_boroughs if b.strip()]
            if allowed_boroughs_norm:
                listing_borough = (self.borough or "").lower().strip()
                listing_text = f"{self.borough} {self.neighborhood} {self.address}".lower()
                matched = any(
                    b in listing_borough or b in listing_text
                    for b in allowed_boroughs_norm
                )
                if not matched:
                    return False, f"Borough/Area '{self.borough or self.neighborhood}' does not match allowed: {', '.join(allowed_boroughs)}"

        # 5. Search keywords (optional include filter)
        keywords = filters.get("keywords")
        if keywords and isinstance(keywords, list) and len(keywords) > 0:
            text_to_search = f"{self.title} {self.address} {self.neighborhood} {self.borough}".lower()
            matched = any(kw.lower() in text_to_search for kw in keywords if kw.strip())
            if not matched:
                return False, f"Listing does not contain any of required keywords: {', '.join(keywords)}"

        return True, "Listing matches all filter criteria"

    def to_telegram_html(self) -> str:
        """Format listing for Telegram HTML mode."""
        lines = []
        lines.append("🚨 <b>NEW NYC RE-RENTAL ALERT</b>\n")

        # Title & Price
        rent_display = f"${self.rent:,.0f}/mo" if self.rent else (self.rent_str or "Rent not listed")
        unit_display = self.beds if self.beds else "Apartment"
        borough_display = f" in {self.borough}" if self.borough else ""
        lines.append(f"🏠 <b>{html.escape(unit_display)}{html.escape(borough_display)} · {html.escape(rent_display)}</b>")

        # Address & Area
        addr_line = self.address or "Address not specified"
        if self.neighborhood and self.neighborhood.lower() not in addr_line.lower():
            addr_line += f", {self.neighborhood}"
        lines.append(f"📍 <b>{html.escape(addr_line)}</b>\n")

        # Details
        if self.household_size:
            lines.append(f"👥 <b>Household:</b> {html.escape(self.household_size)}")
        if self.income_limits:
            lines.append(f"💰 <b>Income Limits:</b> {html.escape(self.income_limits)}")
        if self.ami:
            lines.append(f"🏷️ <b>AMI Level:</b> {html.escape(self.ami)}")
        if self.source:
            lines.append(f"🏢 <b>Source:</b> {html.escape(self.source)}")
        if self.subway_lines:
            lines.append(f"🚇 <b>Subways:</b> {html.escape(', '.join(self.subway_lines))}")

        lines.append("")

        # Application / Action Link
        if self.apply_url:
            lines.append(f'👉 <a href="{html.escape(self.apply_url)}"><b>Apply Directly Here</b></a>')
        if self.detail_url and self.detail_url != self.apply_url:
            lines.append(f'ℹ️ <a href="{html.escape(self.detail_url)}">View Full Listing Details</a>')

        # Maps link
        if self.address:
            clean_addr = re.sub(r'#\w+', '', self.address).strip()
            maps_url = f"https://www.google.com/maps/search/?api=1&query={clean_addr.replace(' ', '+')}+NYC"
            lines.append(f'🗺️ <a href="{html.escape(maps_url)}">Google Maps Location</a>')

        return "\n".join(lines)

    def to_email_html(self) -> str:
        """Format responsive HTML email template for notifications."""
        rent_display = f"${self.rent:,.0f}" if self.rent else (self.rent_str or "Not Listed")
        unit_display = self.beds if self.beds else "Apartment"
        borough_display = f"in {self.borough}" if self.borough else "in NYC"
        addr_line = self.address or "Address Pending"
        if self.neighborhood and self.neighborhood.lower() not in addr_line.lower():
            addr_line += f", {self.neighborhood}"

        apply_btn = ""
        if self.apply_url:
            apply_btn = f'''
            <div style="margin: 24px 0 16px 0; text-align: center;">
                <a href="{html.escape(self.apply_url)}" target="_blank"
                   style="background: #2563eb; color: #ffffff; text-decoration: none; padding: 14px 28px;
                          border-radius: 8px; font-weight: bold; font-size: 16px; display: inline-block;
                          box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);">
                    🚀 Apply Directly to This Unit
                </a>
            </div>
            '''

        details_rows = []
        if self.beds:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>Bedrooms</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(self.beds)}</td></tr>")
        if self.borough or self.neighborhood:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>Location</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(self.neighborhood or self.borough)} ({html.escape(self.borough)})</td></tr>")
        if self.household_size:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>Household Size</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(self.household_size)}</td></tr>")
        if self.income_limits:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>Income Limits</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(self.income_limits)}</td></tr>")
        if self.ami:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>AMI Band</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(self.ami)}</td></tr>")
        if self.source:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>Source</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(self.source)}</td></tr>")
        if self.subway_lines:
            details_rows.append(f"<tr><td style='padding: 8px 12px; color: #64748b;'>Subways</td><td style='padding: 8px 12px; font-weight: 600; color: #1e293b;'>{html.escape(', '.join(self.subway_lines))}</td></tr>")

        details_table = "\n".join(details_rows)

        clean_addr = re.sub(r'#\w+', '', self.address).strip()
        maps_url = f"https://www.google.com/maps/search/?api=1&query={clean_addr.replace(' ', '+')}+NYC"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>New Re-Rental Alert</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f1f5f9; padding: 24px 0;">
  <tr>
    <td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); max-width: 600px; width: 100%;">
        
        <!-- Header banner -->
        <tr>
          <td style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 24px; text-align: center;">
            <span style="background: #dc2626; color: #ffffff; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; padding: 4px 10px; border-radius: 20px; display: inline-block; margin-bottom: 8px;">
              Immediate Alert
            </span>
            <h1 style="color: #ffffff; margin: 4px 0 0 0; font-size: 22px; font-weight: 700;">
              New NYC Affordable Re-Rental
            </h1>
          </td>
        </tr>

        <!-- Rent Highlight Card -->
        <tr>
          <td style="padding: 24px 28px 12px 28px; text-align: center; border-bottom: 1px solid #f1f5f9;">
            <p style="margin: 0; color: #64748b; font-size: 13px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">Monthly Rent</p>
            <div style="font-size: 38px; font-weight: 800; color: #0f172a; margin: 4px 0;">
              {html.escape(rent_display)} <span style="font-size: 18px; font-weight: 400; color: #64748b;">/ month</span>
            </div>
            <p style="margin: 4px 0 0 0; font-size: 18px; font-weight: 600; color: #334155;">
              {html.escape(unit_display)} {html.escape(borough_display)}
            </p>
            <p style="margin: 6px 0 0 0; font-size: 15px; color: #64748b;">
              📍 <a href="{html.escape(maps_url)}" style="color: #2563eb; text-decoration: underline;" target="_blank">{html.escape(addr_line)}</a>
            </p>
          </td>
        </tr>

        <!-- Action Button -->
        <tr>
          <td style="padding: 12px 28px;">
            {apply_btn}
          </td>
        </tr>

        <!-- Table of Details -->
        <tr>
          <td style="padding: 12px 28px 24px 28px;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 14px;">
              {details_table}
            </table>
          </td>
        </tr>

        <!-- Links and footer -->
        <tr>
          <td style="padding: 16px 28px 24px 28px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #94a3b8;">
            <p style="margin: 0 0 8px 0;">
              Applying to NYC affordable housing is always <b>free</b>. Never pay any broker fee or application charge.
            </p>
            <p style="margin: 0;">
              Automated Re-Rental Alert Service &bull; Detected at {html.escape(self.posted_at)}
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

    def to_plain_text(self) -> str:
        """Format plain text for notifications."""
        rent_display = f"${self.rent:,.0f}/mo" if self.rent else (self.rent_str or "Rent not listed")
        unit_display = self.beds if self.beds else "Apartment"
        borough_display = f" in {self.borough}" if self.borough else ""

        lines = [
            "========================================",
            "🚨 NEW NYC RE-RENTAL ALERT",
            "========================================",
            f"Unit: {unit_display}{borough_display} - {rent_display}",
            f"Address: {self.address}" + (f", {self.neighborhood}" if self.neighborhood else ""),
        ]
        if self.household_size:
            lines.append(f"Household Size: {self.household_size}")
        if self.income_limits:
            lines.append(f"Income Limits: {self.income_limits}")
        if self.ami:
            lines.append(f"AMI Level: {self.ami}")
        if self.source:
            lines.append(f"Source: {self.source}")
        if self.subway_lines:
            lines.append(f"Subways: {', '.join(self.subway_lines)}")
        if self.apply_url:
            lines.append(f"\n👉 Apply Directly: {self.apply_url}")
        if self.detail_url:
            lines.append(f"ℹ️ Full Details: {self.detail_url}")

        lines.append(f"\nDetected at: {self.posted_at}")
        return "\n".join(lines)
