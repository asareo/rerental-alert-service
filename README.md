# 🏢 NYC Re-Rental Instant Alert Service

A completely free, self-hosted replacement for `rerentalalert.com`.

Provides **instant notifications to Telegram and Email** the moment a new affordable housing re-rental is posted across New York City—without paying any monthly subscriptions.

---

## ⚡ Features

- **Instant Telegram Alerts**: Delivers rich push notifications directly to your private chat or Telegram channel via your own Telegram bot.
- **Instant Email Alerts**: Sends clean, mobile-responsive HTML alerts with big rent badges, property details, and direct application links.
- **Customizable Search Filters (Free & Unlimited)**:
  - Filter by **Max Rent** (e.g. `<= $2,500/mo`)
  - Filter by **Bedrooms** (Studio, 1BR, 2BR, 3BR+)
  - Filter by **Borough** (Manhattan, Brooklyn, Queens, Bronx, Staten Island)
  - Or receive alerts on **all** listings with zero restrictions
- **Multi-Source Aggregator**:
  - Live broadcast feed (`t.me/s/rerentalalert`)
  - Live browse catalog across all 12 agency sources (NYC HDC, Reside NY, Pronto, Taxace, MGNY, etc.)
- **Persistent SQLite Deduplication**: Ensures you never receive duplicate alerts for the same apartment.
- **Zero Third-Party Dependencies**: Built entirely with Python's standard library. No `pip install` required!
- **Built-in Local Web Dashboard**: View active listings, adjust filters, test alerts with 1 click at `http://localhost:5050`.

---

## 🚀 Quick Start Guide

### 1. Interactive Setup (Easiest)

Run the interactive setup wizard in PowerShell or terminal:

```bash
cd C:\Users\oasar\.gemini\antigravity\scratch\rerental-alert-service
python app.py --setup
```

The wizard will guide you through entering your Telegram bot credentials, email settings, and rental filters.

---

### 2. Manual Configuration (`config.json`)

You can also edit `config.json` directly:

```json
{
  "poll_interval_seconds": 60,
  "baseline_on_first_run": true,
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN_FROM_BOTFATHER",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID"
  },
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": true,
    "sender_email": "your_email@gmail.com",
    "sender_password": "YOUR_GMAIL_APP_PASSWORD",
    "recipient_email": "your_email@gmail.com"
  },
  "filters": {
    "max_rent": 2800,
    "allowed_beds": ["1BR", "2BR"],
    "allowed_boroughs": ["Brooklyn", "Queens"],
    "keywords": []
  }
}
```

---

## 🔑 How to Get Your Credentials (Takes 2 Minutes)

### ✈️ Telegram Setup

1. **Create a Bot**:
   - Open Telegram and message **[@BotFather](https://t.me/botfather)**.
   - Send `/newbot`, name it (e.g. `MyReRentalAlertBot`), and choose a username ending in `bot`.
   - Copy the HTTP API token (e.g. `7123456789:AAH...`).
2. **Get Your Chat ID**:
   - In Telegram, open your new bot and press **Start**.
   - Message **[@userinfobot](https://t.me/userinfobot)**; it will reply with your `Id` number (e.g. `987654321`).
3. Enter both into `config.json` (or the dashboard).

---

### 📧 Email Setup (Gmail / Outlook)

#### For Gmail:
1. Ensure **2-Step Verification** is active on your Google account.
2. Go to **[Google App Passwords](https://myaccount.google.com/apppasswords)**.
3. Generate a new App Password named `ReRental Alerts` (a 16-character code like `abcd efgh ijkl mnop`).
4. Set:
   - `sender_email`: `your_email@gmail.com`
   - `sender_password`: `your 16-character app password`
   - `recipient_email`: `wherever you want to receive alerts`

#### For Outlook / Hotmail:
- `smtp_host`: `smtp.office365.com`
- `smtp_port`: `587`
- `use_tls`: `true`

---

## 🧪 Testing Your Alerts

To verify everything is connected before starting the monitor:

```bash
python app.py --test
```

This sends an immediate test notification to your Telegram and Email!

---

## 🏃 Running the Service

### Option A: Standard Terminal / Console
```bash
python app.py
```
Or double-click `run_service.bat`.

### Option B: Local Web Dashboard
```bash
python app.py --dashboard
```
Or double-click `run_dashboard.bat`. Open [http://localhost:5050](http://localhost:5050) in your browser to view live listings, change filters on the fly, and trigger manual scans.

### Option C: 24/7 Windows Background Service (Automatic on Boot)
Right-click `install_windows_task.ps1` and select **Run with PowerShell** (or run in pwsh):
```powershell
.\install_windows_task.ps1
```
This registers a Windows Scheduled Task that boots automatically in the background without keeping any console window open!

To remove the scheduled task:
```powershell
.\uninstall_windows_task.ps1
```

---

## 📊 Checking Statistics
```bash
python app.py --stats
```
Outputs the number of cataloged listings, total alerts dispatched, and recent postings.
