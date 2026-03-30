"""
Site-specific scrapers for each Argentine retailer.
Uses Playwright (headless Chromium) to handle JS-rendered pages.
Each scraper navigates directly to the known product URL.
"""
import re
import time
from typing import Optional


# ── URLs directas de producto ────────────────────────────────────────────────────

PRODUCT_URLS = {
    "Mercado Libre": "https://www.mercadolibre.com.ar/smart-tv-tcl-mini-led-smt-65p-4k-65c6k-google-tv/p/MLA57770372",
    "Fravega":       "https://www.fravega.com/p/smart-tv-tcl-65-4k-mini-led-65c6k-google-tv-502880/",
    "On City":       "https://www.oncity.com/smart-qd-mini-led-tv-tcl-65--qd-4k-3840-x-2160-65c6k-155162/p",
    "Naldo":         "https://www.naldo.com.ar/65-l65c6k-miniled-4k-google-bt-ctrl-voz-505892-1/p?skuId=45298",
    "Cetrogar":      "https://www.cetrogar.com.ar/smart-tv-tcl-65-mini-led-65c6k-uhd-google-tv-rv.html",
}


# ── Price parsing helpers ────────────────────────────────────────────────────────

def _parse_ars(text: str | None) -> Optional[int]:
    """
    Convert Argentine price formats to integer ARS.
    Handles: '$1.399.999', '$116.666,58', '1350000'
    In Argentina: period = thousands separator, comma = decimal separator.
    """
    if not text:
        return None
    text = text.strip().lstrip("$").strip()
    if "," in text:
        text = text.split(",")[0]
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_installments(body: str) -> tuple[Optional[int], Optional[bool]]:
    """Parse 12-month installment amount and interest-free flag from page text."""
    patterns = [
        r"12\s*(?:cuotas?|meses?|x)\s*(?:sin\s*inter[eé]s\s*)?(?:de\s*)?\$\s*([\d.,]+)",
        r"12\s*(?:cuotas?|meses?|x)\s*(?:de\s*)?\$\s*([\d.,]+)",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, body, re.IGNORECASE):
            amount = _parse_ars(m.group(1))
            if amount and 10_000 < amount < 2_000_000:
                context = body[max(0, m.start() - 60):m.end() + 60]
                interest_free = bool(re.search(r"sin\s*inter[eé]s", context, re.IGNORECASE))
                return amount, interest_free
    return None, None


def _find_price(page, selectors: list[str]) -> Optional[int]:
    """Try a list of CSS selectors until one returns a valid price."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                price = _parse_ars(el.inner_text())
                if price and price > 10_000:
                    return price
        except Exception:
            pass
    return None


def _extract_price_from_body(body: str, min_ars: int = 300_000, max_ars: int = 8_000_000) -> Optional[int]:
    """Fallback: find the first price in body text within the expected TV price range."""
    body_clean = re.sub(r"\d+\s*(?:cuotas?|meses?|x)\s*(?:sin\s*inter[eé]s\s*)?(?:de\s*)?\$[\d.,]+", "", body)
    body_clean = re.sub(r"sin\s*impuestos?\s*[\w\s]*\$[\d.,]+", "", body_clean, flags=re.IGNORECASE)
    for m in re.finditer(r"\$([\d.,]+)", body_clean):
        price = _parse_ars(m.group(1))
        if price and min_ars <= price <= max_ars:
            return price
    return None


# ── Base helper ──────────────────────────────────────────────────────────────────

def _scrape_direct(ctx, name: str, url: str, selectors: list[str], wait: int = 3) -> dict:
    """
    Navigate directly to a product URL and extract price + installments.
    selectors: list of CSS selectors to try for the cash price.
    """
    page = ctx.new_page()
    result = {
        "retailer": name,
        "cash_price_ars": None,
        "installment_12m_ars": None,
        "interest_free": None,
        "product_url": url,
    }
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(wait)

        body = page.inner_text("body")

        cash_price = _find_price(page, selectors)
        if not cash_price:
            cash_price = _extract_price_from_body(body)

        installment, interest_free = _parse_installments(body)

        result.update({
            "cash_price_ars": cash_price,
            "installment_12m_ars": installment,
            "interest_free": interest_free,
            "product_url": page.url,
        })
    except Exception as e:
        print(f"[{name}] Error: {e}")
    finally:
        page.close()
    return result


# ── Mercado Libre ────────────────────────────────────────────────────────────────

def scrape_mercadolibre(ctx) -> dict:
    return _scrape_direct(
        ctx,
        name="Mercado Libre",
        url=PRODUCT_URLS["Mercado Libre"],
        selectors=[
            ".ui-pdp-price__second-line .andes-money-amount__fraction",
            ".andes-money-amount__fraction",
            ".price-tag-fraction",
            "[class*='price-tag'] [class*='fraction']",
        ],
        wait=4,
    )


# ── Frávega ──────────────────────────────────────────────────────────────────────

def scrape_fravega(ctx) -> dict:
    return _scrape_direct(
        ctx,
        name="Fravega",
        url=PRODUCT_URLS["Fravega"],
        selectors=[
            "[data-test-id='cash-price'] span",
            "[class*='CashPrice']",
            "[class*='cash-price']",
            "[class*='CurrentPrice']",
            "[class*='current-price']",
            "span[class*='Price']",
            "span[class*='price']",
        ],
        wait=3,
    )


# ── On City ──────────────────────────────────────────────────────────────────────

def scrape_oncity(ctx) -> dict:
    return _scrape_direct(
        ctx,
        name="On City",
        url=PRODUCT_URLS["On City"],
        selectors=[
            ".special-price .price",
            ".product-price-special",
            ".price-box .price",
            "[class*='specialPrice']",
            "[class*='finalPrice'] .price",
            "span[class*='price']",
        ],
        wait=3,
    )


# ── Naldo ────────────────────────────────────────────────────────────────────────

def scrape_naldo(ctx) -> dict:
    return _scrape_direct(
        ctx,
        name="Naldo",
        url=PRODUCT_URLS["Naldo"],
        selectors=[
            ".special-price .price",
            ".price-box .price",
            ".product-info-price .price",
            "[class*='skuBestPrice']",
            "[class*='bestPrice']",
            "span[class*='price']",
        ],
        wait=3,
    )


# ── Cetrogar ─────────────────────────────────────────────────────────────────────

def scrape_cetrogar(ctx) -> dict:
    return _scrape_direct(
        ctx,
        name="Cetrogar",
        url=PRODUCT_URLS["Cetrogar"],
        selectors=[
            ".special-price .price",
            "[data-price-type='finalPrice'] .price",
            ".price-box .special-price .price",
            ".price-box .price",
            "span[class*='precio']",
            "span[class*='price']",
        ],
        wait=3,
    )


# ── Run all scrapers ─────────────────────────────────────────────────────────────

def run_all() -> list[dict]:
    from playwright.sync_api import sync_playwright

    scrapers = [
        scrape_mercadolibre,
        scrape_fravega,
        scrape_oncity,
        scrape_naldo,
        scrape_cetrogar,
    ]

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-AR",
        )
        for fn in scrapers:
            print(f"[scrapers] Running {fn.__name__}...")
            try:
                results.append(fn(ctx))
            except Exception as e:
                print(f"[scrapers] {fn.__name__} failed: {e}")
        ctx.close()
        browser.close()

    return results
