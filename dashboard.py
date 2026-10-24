"""
dashboard.py
Lightweight local web dashboard built with standard library http.server.
Allows viewing live listings, managing filters, testing Telegram/Email alerts, and triggering checks.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import threading
import logging
import sys
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from database import Database
from config import load_config, save_config
from notifiers.telegram_notifier import TelegramNotifier
from notifiers.email_notifier import EmailNotifier
from service import ReRentalService

logger = logging.getLogger(__name__)

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NYC Re-Rental Alert Service</title>
<style>
  :root {
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --text-muted: #94a3b8;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --accent: #ef4444;
    --success: #22c55e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background-color: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.5;
  }
  .container { max-width: 1100px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
  .logo { font-size: 22px; font-weight: 800; display: flex; align-items: center; gap: 8px; }
  .logo span { color: var(--accent); }
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
  .stat-val { font-size: 28px; font-weight: 700; color: var(--primary); }
  .stat-label { font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  @media (max-width: 800px) { .two-col { grid-template-columns: 1fr; } }

  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .card h2 { font-size: 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
  
  .form-group { margin-bottom: 14px; }
  label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #cbd5e1; }
  input[type="text"], input[type="password"], input[type="number"], select {
    width: 100%; padding: 10px 12px; background: #0f172a; border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 14px;
  }
  .checkbox-group { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
  .checkbox-group input { width: 16px; height: 16px; }

  .btn {
    background: var(--primary); color: white; border: none; padding: 10px 18px;
    border-radius: 6px; font-weight: 600; cursor: pointer; transition: background 0.2s;
    font-size: 14px; display: inline-flex; align-items: center; gap: 6px;
  }
  .btn:hover { background: var(--primary-hover); }
  .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .btn-outline:hover { background: #334155; }
  .btn-success { background: var(--success); }
  .btn-success:hover { background: #16a34a; }
  
  .badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
  .badge-new { background: #dc2626; color: white; }
  .badge-live { background: #16a34a; color: white; }

  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 12px; border-bottom: 1px solid var(--border); }
  th { color: var(--text-muted); font-size: 12px; text-transform: uppercase; }
  tr:hover { background: rgba(255, 255, 255, 0.02); }

  .toast {
    position: fixed; bottom: 20px; right: 20px; background: #1e293b; border: 1px solid var(--primary);
    padding: 14px 20px; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    display: none; z-index: 1000;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">🏢 ReRental<span>Alert</span> Service</div>
    <div>
      <button class="btn btn-success" onclick="runCheckNow()">⚡ Check Sources Now</button>
    </div>
  </header>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-val" id="stat-seen">...</div>
      <div class="stat-label">Total Listings Watched</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" id="stat-tg">...</div>
      <div class="stat-label">Telegram Alerts Sent</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" id="stat-email">...</div>
      <div class="stat-label">Email Alerts Sent</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" style="font-size: 16px; margin-top: 8px;" id="stat-last">...</div>
      <div class="stat-label">Last Polled</div>
    </div>
  </div>

  <div class="two-col">
    <!-- Telegram Settings -->
    <div class="card">
      <h2>✈️ Telegram Notifications</h2>
      <div class="form-group checkbox-group">
        <input type="checkbox" id="tg_enabled">
        <label for="tg_enabled" style="margin-bottom: 0;">Enable Telegram Notifications</label>
      </div>
      <div class="form-group">
        <label>Telegram Bot Token</label>
        <input type="password" id="tg_token" placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ">
      </div>
      <div class="form-group">
        <label>Telegram Chat ID</label>
        <input type="text" id="tg_chat_id" placeholder="Your Telegram user or chat ID">
      </div>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-outline" onclick="testTelegram()">Test Telegram Alert</button>
      </div>
    </div>

    <!-- Email Settings -->
    <div class="card">
      <h2>📧 Email Notifications</h2>
      <div class="form-group checkbox-group">
        <input type="checkbox" id="email_enabled">
        <label for="email_enabled" style="margin-bottom: 0;">Enable Email Notifications</label>
      </div>
      <div class="form-group">
        <label>Sender Email (Gmail, Outlook, etc.)</label>
        <input type="text" id="email_sender" placeholder="your_email@gmail.com">
      </div>
      <div class="form-group">
        <label>App Password / SMTP Password</label>
        <input type="password" id="email_password" placeholder="App password from Google / email provider">
      </div>
      <div class="form-group">
        <label>Recipient Email Address</label>
        <input type="text" id="email_recipient" placeholder="where_to_send_alerts@gmail.com">
      </div>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-outline" onclick="testEmail()">Test Email Alert</button>
      </div>
    </div>
  </div>

  <!-- Filters Card -->
  <div class="card">
    <h2>🎯 Search Filters (Free & Unlimited)</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
      <div class="form-group">
        <label>Max Rent ($/month)</label>
        <input type="number" id="filter_max_rent" placeholder="e.g. 2500 (blank for no max)">
      </div>
      <div class="form-group">
        <label>Allowed Bedrooms (comma-separated)</label>
        <input type="text" id="filter_beds" placeholder="e.g. Studio, 1BR, 2BR">
      </div>
      <div class="form-group">
        <label>Allowed Boroughs (comma-separated)</label>
        <input type="text" id="filter_boroughs" placeholder="e.g. Manhattan, Brooklyn, Bronx">
      </div>
      <div class="form-group">
        <label>Check Interval (seconds)</label>
        <input type="number" id="poll_interval" value="60" min="15">
      </div>
    </div>
    <div style="margin-top: 12px;">
      <button class="btn" onclick="saveSettings()">💾 Save All Settings</button>
    </div>
  </div>

  <!-- Recent Tracked Listings -->
  <div class="card">
    <h2>📋 Recently Discovered Listings</h2>
    <div style="overflow-x: auto;">
      <table>
        <thead>
          <tr>
            <th>Rent</th>
            <th>Bedrooms</th>
            <th>Address</th>
            <th>Borough</th>
            <th>Source</th>
            <th>Apply / Link</th>
          </tr>
        </thead>
        <tbody id="listings-table-body">
          <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading listings...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<div class="toast" id="toast">Notification</div>

<script>
  function showToast(msg) {
    const t = document.getElementById('toast');
    t.innerText = msg;
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 4000);
  }

  async function loadData() {
    try {
      const res = await fetch('/api/data');
      const data = await res.json();
      
      // Stats
      document.getElementById('stat-seen').innerText = data.stats.total_seen;
      document.getElementById('stat-tg').innerText = data.stats.telegram_alerts_sent;
      document.getElementById('stat-email').innerText = data.stats.email_alerts_sent;
      document.getElementById('stat-last').innerText = data.stats.last_check_time || 'Never';

      // Settings
      const cfg = data.config;
      document.getElementById('tg_enabled').checked = cfg.telegram.enabled || false;
      document.getElementById('tg_token').value = cfg.telegram.bot_token || '';
      document.getElementById('tg_chat_id').value = cfg.telegram.chat_id || '';

      document.getElementById('email_enabled').checked = cfg.email.enabled || false;
      document.getElementById('email_sender').value = cfg.email.sender_email || '';
      document.getElementById('email_password').value = cfg.email.sender_password || '';
      document.getElementById('email_recipient').value = cfg.email.recipient_email || '';

      document.getElementById('filter_max_rent').value = cfg.filters.max_rent || '';
      document.getElementById('filter_beds').value = (cfg.filters.allowed_beds || []).join(', ');
      document.getElementById('filter_boroughs').value = (cfg.filters.allowed_boroughs || []).join(', ');
      document.getElementById('poll_interval').value = cfg.poll_interval_seconds || 60;

      // Listings Table
      const tbody = document.getElementById('listings-table-body');
      tbody.innerHTML = '';
      if (!data.listings || data.listings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #94a3b8;">No listings in database yet. Click "Check Sources Now".</td></tr>';
      } else {
        data.listings.forEach(l => {
          const tr = document.createElement('tr');
          const rentStr = l.rent ? '$' + Number(l.rent).toLocaleString() + '/mo' : 'N/A';
          const applyBtn = l.apply_url ? `<a href="${l.apply_url}" target="_blank" style="color: #3b82f6; font-weight: bold; text-decoration: underline;">Apply</a>` : '<span style="color:#64748b;">Pending</span>';
          tr.innerHTML = `
            <td style="font-weight: bold; color: #22c55e;">${rentStr}</td>
            <td>${l.beds || 'Apartment'}</td>
            <td>${l.address}</td>
            <td>${l.borough || ''}</td>
            <td style="color: #94a3b8; font-size: 13px;">${l.source || ''}</td>
            <td>${applyBtn}</td>
          `;
          tbody.appendChild(tr);
        });
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function saveSettings() {
    const beds = document.getElementById('filter_beds').value.split(',').map(s => s.trim()).filter(Boolean);
    const boroughs = document.getElementById('filter_boroughs').value.split(',').map(s => s.trim()).filter(Boolean);
    const maxRentVal = document.getElementById('filter_max_rent').value;

    const payload = {
      poll_interval_seconds: parseInt(document.getElementById('poll_interval').value) || 60,
      telegram: {
        enabled: document.getElementById('tg_enabled').checked,
        bot_token: document.getElementById('tg_token').value.trim(),
        chat_id: document.getElementById('tg_chat_id').value.trim()
      },
      email: {
        enabled: document.getElementById('email_enabled').checked,
        sender_email: document.getElementById('email_sender').value.trim(),
        sender_password: document.getElementById('email_password').value.trim(),
        recipient_email: document.getElementById('email_recipient').value.trim(),
        smtp_host: "smtp.gmail.com",
        smtp_port: 587,
        use_tls: true
      },
      filters: {
        max_rent: maxRentVal ? parseFloat(maxRentVal) : null,
        allowed_beds: beds,
        allowed_boroughs: boroughs
      }
    };

    const res = await fetch('/api/save-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    showToast(result.message || 'Settings saved successfully!');
    loadData();
  }

  async function testTelegram() {
    showToast('Sending test Telegram message...');
    const res = await fetch('/api/test-telegram', { method: 'POST' });
    const data = await res.json();
    showToast(data.message);
  }

  async function testEmail() {
    showToast('Sending test Email...');
    const res = await fetch('/api/test-email', { method: 'POST' });
    const data = await res.json();
    showToast(data.message);
  }

  async function runCheckNow() {
    showToast('Polling feeds for new listings...');
    const res = await fetch('/api/check-now', { method: 'POST' });
    const data = await res.json();
    showToast(data.message);
    loadData();
  }

  loadData();
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    db = Database()
    service: Optional[ReRentalService] = None

    def log_message(self, format, *args):
        # Silence default request logging to keep console clean
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/api/data":
            stats = self.db.get_stats()
            config = load_config()
            listings = self.db.get_recent_listings(limit=50)
            payload = {
                "stats": stats,
                "config": config,
                "listings": listings
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        if self.path == "/api/save-settings":
            try:
                new_cfg = json.loads(body)
                save_config(new_cfg)
                self._send_json({"success": True, "message": "Settings saved successfully!"})
            except Exception as e:
                self._send_json({"success": False, "message": f"Error saving: {e}"}, status=400)

        elif self.path == "/api/test-telegram":
            cfg = load_config()
            tg = TelegramNotifier(cfg.get("telegram", {}))
            success, msg = tg.send_test_message()
            self._send_json({"success": success, "message": msg})

        elif self.path == "/api/test-email":
            cfg = load_config()
            em = EmailNotifier(cfg.get("email", {}))
            success, msg = em.send_test_email()
            self._send_json({"success": success, "message": msg})

        elif self.path == "/api/check-now":
            try:
                cfg = load_config()
                svc = ReRentalService(cfg)
                matches_count = svc.run_check_cycle()
                msg = f"Check complete! Found and dispatched {matches_count} new alerts." if matches_count > 0 else "Check complete! No new matching listings found right now."
                self._send_json({"success": True, "message": msg})
            except Exception as e:
                self._send_json({"success": False, "message": f"Check failed: {e}"}, status=500)
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def run_dashboard(port: int = 5050):
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"\n==================================================")
    print(f"  🏢 ReRental Alert Service Dashboard is Live!")
    print(f"  Open in your browser: http://localhost:{port}")
    print(f"==================================================\n")
    server.serve_forever()
