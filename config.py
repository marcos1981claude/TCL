import os
from dotenv import load_dotenv

load_dotenv()

# ── Alert thresholds ────────────────────────────────────────────────────────────
PRICE_ALERT_THRESHOLD = 1_350_000   # ARS — alert if any retailer goes below this
PRICE_DROP_PCT        = 0.05        # Alert if price drops more than 5% vs yesterday

# ── Product search term ─────────────────────────────────────────────────────────
SEARCH_TERM = "TCL 65C6K"

# ── Email ───────────────────────────────────────────────────────────────────────
EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))

# ── Telegram ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── WhatsApp (CallMeBot) ────────────────────────────────────────────────────────
WHATSAPP_PHONE   = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")

# ── Storage ─────────────────────────────────────────────────────────────────────
DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")
PRICES_FILE = os.path.join(DATA_DIR, "prices.csv")
