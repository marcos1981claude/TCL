"""
Handles reading/writing the price history CSV.
"""
import csv
import os
from datetime import date
from dataclasses import dataclass, fields, astuple
from typing import Optional

import config


@dataclass
class PriceRecord:
    date: str
    retailer: str
    cash_price_ars: Optional[int]
    installment_12m_ars: Optional[int]
    interest_free: Optional[bool]
    product_url: str


_FIELDNAMES = [f.name for f in fields(PriceRecord)]


def _ensure_file():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.PRICES_FILE):
        with open(config.PRICES_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_FIELDNAMES).writeheader()


def save_records(records: list[PriceRecord]):
    _ensure_file()
    with open(config.PRICES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        for r in records:
            writer.writerow(
                {
                    "date": r.date,
                    "retailer": r.retailer,
                    "cash_price_ars": r.cash_price_ars,
                    "installment_12m_ars": r.installment_12m_ars,
                    "interest_free": r.interest_free,
                    "product_url": r.product_url,
                }
            )


def load_yesterday_prices() -> dict[str, Optional[int]]:
    """Returns {retailer: cash_price_ars} for the most recent previous day."""
    _ensure_file()
    today = date.today().isoformat()
    latest: dict[str, Optional[int]] = {}
    with open(config.PRICES_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["date"] < today and row["cash_price_ars"]:
                latest[row["retailer"]] = int(row["cash_price_ars"])
    return latest
