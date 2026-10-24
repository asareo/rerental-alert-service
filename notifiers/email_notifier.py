"""
notifiers/email_notifier.py
Sends instant HTML & plain-text email alerts via standard SMTP (Gmail, Outlook, iCloud, etc.).
Zero third-party library dependencies (uses Python standard library smtplib).
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import Tuple, Dict, Any
from models import Listing

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        self.smtp_host = config.get("smtp_host", "smtp.gmail.com").strip()
        self.smtp_port = int(config.get("smtp_port", 587))
        self.use_tls = config.get("use_tls", True)
        self.use_ssl = config.get("use_ssl", False)
        self.sender_email = config.get("sender_email", "").strip()
        self.sender_password = config.get("sender_password", "").strip()
        self.recipient_email = config.get("recipient_email", "").strip()

    def is_configured(self) -> bool:
        """Check if email settings are populated."""
        return bool(
            self.sender_email
            and self.sender_password
            and self.recipient_email
            and self.sender_email != "YOUR_EMAIL@gmail.com"
            and self.sender_password != "YOUR_APP_PASSWORD"
        )

    def send_alert(self, listing: Listing) -> Tuple[bool, str]:
        """Send an HTML/text email alert for a re-rental listing."""
        if not self.enabled:
            return False, "Email notifier is disabled in configuration."
        if not self.is_configured():
            return False, "Email SMTP settings are not fully configured."

        # Format Subject Line
        rent_display = f"${listing.rent:,.0f}/mo" if listing.rent else (listing.rent_str or "")
        beds_display = listing.beds or "Apartment"
        borough_display = f" in {listing.borough}" if listing.borough else ""
        subject = f"🚨 [NYC Re-Rental] {beds_display}{borough_display} · {rent_display}"

        html_body = listing.to_email_html()
        text_body = listing.to_plain_text()

        return self._send_email(subject, html_body, text_body)

    def send_test_email(self) -> Tuple[bool, str]:
        """Send a test email to verify SMTP configuration."""
        if not self.is_configured():
            return False, "Email SMTP configuration is incomplete. Check sender_email, password, and recipient."

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
        return self._send_email(subject, html_body, text_body)

    def _send_email(self, subject: str, html_content: str, text_content: str) -> Tuple[bool, str]:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"NYC Re-Rental Alert <{self.sender_email}>"
        msg["To"] = self.recipient_email

        part1 = MIMEText(text_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        # Attempt 1: Using configured port/protocol
        err1 = None
        try:
            return self._attempt_smtp_send(
                self.smtp_host, self.smtp_port, self.use_ssl, self.use_tls, msg
            )
        except Exception as e:
            err1 = e
            logger.debug(f"[EmailNotifier] Initial SMTP attempt failed: {e}")

        # Attempt 2: If using Gmail, try alternate port (465 SSL vs 587 STARTTLS)
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

        # Construct helpful error message
        err_str = str(err1)
        if "connection unexpectedly closed" in err_str.lower() or "smtpserverdisconnected" in err_str.lower():
            if "gmail" in self.smtp_host.lower():
                clean_err = (
                    "Gmail connection closed by Google.\n"
                    "👉 Cause: Google DOES NOT allow your standard account password or a placeholder for SMTP.\n"
                    "👉 Solution: You must create a 16-character Google 'App Password':\n"
                    "   1. Go to https://myaccount.google.com/apppasswords\n"
                    "   2. Create a password named 'RentalAlerts'\n"
                    "   3. Copy the 16-letter code into sender_password in config.json"
                )
                logger.error(f"[EmailNotifier] {clean_err}")
                return False, clean_err

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

        server.sendmail(self.sender_email, [self.recipient_email], msg.as_string())
        server.quit()
        logger.info(f"[EmailNotifier] Email successfully sent to {self.recipient_email}")
        return True, f"Email sent successfully to {self.recipient_email}"
