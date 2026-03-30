"""
Sends alerts via Telegram only.
"""
import requests
import config


def _fmt_price(price_ars: int | None) -> str:
    if price_ars is None:
        return "N/D"
    return f"${price_ars:,.0f}".replace(",", ".")


def build_message(records: list) -> str:
    lines = ["ALERTA PRECIO - TCL 65C6K\n"]
    for r in records:
        lines.append(f"Retailer: {r.retailer}")
        lines.append(f"Contado: {_fmt_price(r.cash_price_ars)} ARS")
        if r.installment_12m_ars:
            sin = " (sin interes)" if r.interest_free else ""
            lines.append(f"12 cuotas: {_fmt_price(r.installment_12m_ars)}/mes{sin}")
        lines.append(f"Link: {r.product_url}")
        lines.append("")
    return "\n".join(lines).strip()


def send_telegram(message: str) -> bool:
    if not all([config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID]):
        print("[notifier] Telegram not configured.")
        return False
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message},
            timeout=15,
        )
        resp.raise_for_status()
        print("[notifier] Telegram message sent.")
        return True
    except Exception as e:
        print(f"[notifier] Telegram error: {e}")
        return False


def notify(triggered_records: list, reason: str):
    subject = f"TCL 65C6K - Alerta de precio ({reason})"
    body = build_message(triggered_records)
    send_telegram(body)
