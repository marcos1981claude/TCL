"""
TCL 65C6K — Daily Price Tracker
Run this script daily at 23:00 ART via Windows Task Scheduler.
"""
import sys
from datetime import date

import config
import scrapers as scraper_module
import notifier
import storage
from storage import PriceRecord


def check_alerts(record: dict, yesterday: dict[str, int | None]) -> list[str]:
    """Return a list of triggered alert reasons for a single record."""
    reasons = []
    price = record["cash_price_ars"]
    retailer = record["retailer"]

    if price is None:
        return reasons

    # Alert 1: price below threshold
    if price < config.PRICE_ALERT_THRESHOLD:
        reasons.append(
            f"precio debajo de ${config.PRICE_ALERT_THRESHOLD:,.0f}".replace(",", ".")
        )

    # Alert 2: any 12-month installment plan available
    if record["installment_12m_ars"] is not None:
        reasons.append("plan 12 cuotas disponible")

    # Alert 3: price dropped >5% vs yesterday
    prev = yesterday.get(retailer)
    if prev and price < prev * (1 - config.PRICE_DROP_PCT):
        pct = (prev - price) / prev * 100
        reasons.append(f"bajó {pct:.1f}% vs ayer")

    return reasons


def main():
    print("=" * 60)
    print(f"TCL 65C6K Price Tracker — {date.today()}")
    print("=" * 60)

    # 1. Scrape all retailers
    print("\n[1/4] Scraping retailers...")
    raw_results = scraper_module.run_all()

    # 2. Convert to PriceRecord objects
    today = date.today().isoformat()
    records = [
        PriceRecord(
            date=today,
            retailer=r["retailer"],
            cash_price_ars=r["cash_price_ars"],
            installment_12m_ars=r["installment_12m_ars"],
            interest_free=r["interest_free"],
            product_url=r["product_url"],
        )
        for r in raw_results
    ]

    # 3. Print summary
    print("\n[2/4] Results:")
    fmt = lambda p: f"${p:>12,.0f}".replace(",", ".") if p else "        N/D"
    for rec in records:
        cuota = f"  | 12c: {fmt(rec.installment_12m_ars)}" if rec.installment_12m_ars else ""
        si = " (sin interés)" if rec.interest_free else ""
        print(f"  {rec.retailer:<20} contado: {fmt(rec.cash_price_ars)}{cuota}{si}")

    # 4. Save to CSV
    print("\n[3/4] Saving to CSV...")
    storage.save_records(records)
    print(f"  Saved {len(records)} records -> {config.PRICES_FILE}")

    # 5. Check alert conditions
    print("\n[4/4] Checking alert conditions...")
    yesterday_prices = storage.load_yesterday_prices()

    alerts: list[tuple[PriceRecord, str]] = []
    for rec in records:
        reasons = check_alerts(
            {
                "retailer": rec.retailer,
                "cash_price_ars": rec.cash_price_ars,
                "installment_12m_ars": rec.installment_12m_ars,
            },
            yesterday_prices,
        )
        for reason in reasons:
            alerts.append((rec, reason))
            print(f"  ALERTA [{rec.retailer}]: {reason}")

    if alerts:
        triggered_records = list({id(r): r for r, _ in alerts}.values())
        reasons_summary = "; ".join({reason for _, reason in alerts})
        print(f"\n  Enviando alertas a {len(triggered_records)} retailer(s)...")
        notifier.notify(triggered_records, reasons_summary)
    else:
        print("  Sin alertas — no se envían notificaciones.")

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
