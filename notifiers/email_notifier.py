"""
notifiers/email_notifier.py
Sends instant HTML & plain-text email alerts via:
1. Resend API (Zero-password cloud delivery - Recommended)
2. Standard SMTP (Gmail, Outlook, iCloud, etc.)
Zero third-party library dependencies (uses Python standard library urllib & smtplib).
"""

import smtplib
import urllib.request
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import Tuple, Dict, Any, List
from models import Listing

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        # Resend Cloud API settings
        self.resend_api_key = config.get("resend_api_key", "").strip()
        self.resend_from = config.get("resend_from", "NYC Re-Rentals <onboarding@resend.dev>").strip()

        # SMTP settings (fallback)
        self.smtp_host = config.get("smtp_host", "smtp.gmail.com").strip()
        self.smtp_port = int(config.get("smtp_port", 587))
        self.use_tls = config.get("use_tls", True)
        self.use_ssl = config.get("use_ssl", False)
        self.sender_email = config.get("sender_email", "").strip()
        self.sender_password = config.get("sender_password", "").strip()

        # Recipients (supports single string or list of emails)
        raw_recipients = config.get("recipient_emails") or config.get("recipient_email") or []
        if isinstance(raw_recipients, str):
            self.recipients = [e.strip() for e in raw_recipients.split(",") if e.strip()]
        elif isinstance(raw_recipients, list):
            self.recipients = [str(e).strip() for e in raw_recipients if str(e).strip()]
        else:
            self.recipients = []

    def is_configured(self) -> bool:
        """Check if either Resend API or SMTP is configured."""
        if not self.recipients:
            return False
        # Resend API check
        if self.resend_api_key and self.resend_api_key != "YOUR_RESEND_API_KEY":
            return True
        # SMTP check
        return bool(
            self.sender_email
            and self.sender_password
            and self.sender_email != "YOUR_EMAIL@gmail.com"
            and self.sender_password != "YOUR_APP_PASSWORD"
        )

    def send_alert(self, listing: Listing) -> Tuple[bool, str]:
        """Send an HTML/text email alert for a re-rental listing."""
        if not self.enabled:
            return False, "Email notifier is disabled in configuration."
        if not self.is_configured():
            return False, "Email settings are not configured. Set resend_api_key or SMTP settings."

        # Format Subject Line
        rent_display = f"${listing.rent:,.0f}/mo" if listing.rent else (listing.rent_str or "")
        beds_display = listing.beds or "Apartment"
        borough_display = f" in {listing.borough}" if listing.borough else ""
        subject = f"🚨 [NYC Re-Rental] {beds_display}{borough_display} · {rent_display}"

        html_body = listing.to_email_html()
        text_body = listing.to_plain_text()

        # If Resend API key is present, use Resend API directly (zero password!)
        if self.resend_api_key and self.resend_api_key != "YOUR_RESEND_API_KEY":
            return self._send_via_resend(subject, html_body, text_body)

        # Fallback to SMTP
        return self._send_email_smtp(subject, html_body, text_body)

    def send_test_email(self) -> Tuple[bool, str]:
        """Send a test email to verify configuration."""
        if not self.is_configured():
            return False, "Email configuration is incomplete. Check resend_api_key or SMTP settings."

        subject = "✅ [ReRental Alert Service] Test Alert Successful!"
        text_body = (
            "Congratulations!\n\n"
            "Your email alert configuration is working properly.\n"
            "You will receive immediate notifications whenever a matching NYC affordable re-rental drops."
        )
        html_body = """
        <div style="font-family: sans-serif; max-width: 500px; margin: 20px auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #16a34a; margin-top: 0;">✅ Test Notification Successful!</h2>
            <p style="color: #334155; line-height: 1.5;">
                Your email notification system for <b>NYC Re-Rentals</b> is fully connected and ready.
            </p>
            <p style="color: #64748b; font-size: 13px;">
                You will receive instant alerts the moment new re-rental units matching your filters are posted.
            </p>
        </div>
        """
        if self.resend_api_key and self.resend_api_key != "YOUR_RESEND_API_KEY":
            return self._send_via_resend(subject, html_body, text_body)
        return self._send_email_smtp(subject, html_body, text_body)

    def _send_via_resend(self, subject: str, html_content: str, text_content: str) -> Tuple[bool, str]:
        """Send email using Resend REST API (no passwords, works out of the box)."""
        url = "https://api.resend.com/emails"
        payload = {
            "from": self.resend_from,
            "to": self.recipients,
            "subject": subject,
            "html": html_content,
            "text": text_content
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ReRentalAlertService/1.0"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                logger.info(f"[EmailNotifier/Resend] Sent successfully to {self.recipients}. ID: {resp_data.get('id')}")
                return True, f"Email sent via Resend to {', '.join(self.recipients)}"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"[EmailNotifier/Resend] HTTP {e.code}: {err_body}")
            return False, f"Resend API Error {e.code}: {err_body}"
        except Exception as e:
            logger.error(f"[EmailNotifier/Resend] Network error: {e}")
            return False, str(e)

    def _send_email_smtp(self, subject: str, html_content: str, text_content: str) -> Tuple[bool, str]:
        """Fallback send using standard SMTP."""
        recip_str = ", ".join(self.recipients)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"NYC Re-Rental Alert <{self.sender_email}>"
        msg["To"] = recip_str

        part1 = MIMEText(text_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        err1 = None
        try:
            return self._attempt_smtp_send(
                self.smtp_host, self.smtp_port, self.use_ssl, self.use_tls, msg
            )
        except Exception as e:
            err1 = e
            logger.debug(f"[EmailNotifier] Initial SMTP attempt failed: {e}")

        if "gmail" in self.smtp_host.lower():
            try:
                alt_port = 465 if self.smtp_port == 587 else 587
                alt_ssl = (alt_port == 465)
                alt_tls = not alt_ssl
                return self._attempt_smtp_send(
                    self.smtp_host, alt_port, alt_ssl, alt_tls, msg
                )
            except Exception as e:
                logger.debug(f"[EmailNotifier] Alternate Gmail attempt failed: {e}")

        err_str = str(err1)
        logger.error(f"[EmailNotifier] Failed to send email: {err_str}")
        return False, err_str

    def _attempt_smtp_send(self, host: str, port: int, use_ssl: bool, use_tls: bool, msg: MIMEMultipart) -> Tuple[bool, str]:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=12)
        else:
            server = smtplib.SMTP(host, port, timeout=12)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        if self.sender_password:
            server.login(self.sender_email, self.sender_password)

        server.sendmail(self.sender_email, self.recipients, msg.as_string())
        server.quit()
        logger.info(f"[EmailNotifier] Email successfully sent to {self.recipients}")
        return True, f"Email sent successfully to {', '.join(self.recipients)}"
