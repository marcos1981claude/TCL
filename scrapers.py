"""
TCL 65C6K Price Tracker — Improved Scrapers
Uses Playwright with hierarchical selector strategies and better anti-bot handling.
Based on HasData's methodology for resilient e-commerce scraping.
"""
import re
import time
import random
from typing import Optional
from decimal import Decimal


# ── Product URLs ──────────────────────────────────────────────────────────────

PRODUCT_URLS = {
    "Mercado Libre": "https://www.mercadolibre.com.ar/smart-tv-tcl-mini-led-smt-65p-4k-65c6k-google-tv/p/MLA57770372",
    "Fravega":       "https://www.fravega.com/p/smart-tv-tcl-65-4k-mini-led-65c6k-google-tv-502880/",
    "On City":       "https://www.oncity.com/smart-qd-mini-led-tv-tcl-65--qd-4k-3840-x-2160-65c6k-155162/p",
    "Naldo":         "https://www.naldo.com.ar/65-l65c6k-miniled-4k-google-bt-ctrl-voz-505892-1/p?skuId=45298",
    "Cetrogar":      "https://www.cetrogar.com.ar/smart-tv-tcl-65-mini-led-65c6k-uhd-google-tv-rv.html",
}

# Random user agents to reduce bot detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


# ── Price Parsing ─────────────────────────────────────────────────────────────

def _parse_ars(text: str | None) -> Optional[int]:
    """
    Parse Argentine price formats to integer ARS.
    Handles: '$1.399.999', '$116.666,58', '1350000'
    In Argentina: period = thousands separator, comma = decimal separator.
    """
    if not text:
        return None
    text = str(text).strip().lstrip("$").strip()
    if "," in text:
        text = text.split(",")[0]
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_installments(body: str) -> tuple[Optional[int], Optional[bool]]:
    """
    Parse 12-month installment amount and interest-free flag from page text.
    Uses multiple regex patterns for robustness.
    """
    patterns = [
        r"12\s*(?:cuotas?|meses?|x)\s*(?:sin\s*inter[eé]s\s*)?(?:de\s*)?\$\s*([\d.,]+)",
        r"12\s*(?:cuotas?|meses?|x)\s*(?:de\s*)?\$\s*([\d.,]+)",
        r"\$\s*([\d.,]+)\s*(?:x|en)\s*12\s*(?:cuotas?|meses?)",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, body, re.IGNORECASE):
            amount = _parse_ars(m.group(1))
            if amount and 10_000 < amount < 2_000_000:
                context = body[max(0, m.start() - 60) : m.end() + 60]
                interest_free = bool(
                    re.search(r"sin\s*inter[eé]s", context, re.IGNORECASE)
                )
                return amount, interest_free
    return None, None


def _find_price_by_selector(page, selectors: list[str]) -> Optional[int]:
    """Try a list of CSS selectors until one returns a valid price."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                price = _parse_ars(text)
                if price and price > 10_000:
                    return price
        except Exception:
            pass
    return None


def _find_price_by_json_ld(page) -> Optional[int]:
    """Extract price from JSON-LD structured data (most reliable)."""
    try:
        script = page.query_selector('script[type="application/ld+json"]')
        if script:
            import json
            content = script.inner_html()
            data = json.loads(content)
            if isinstance(data, dict) and "offers" in data:
                offers = data["offers"]
                if isinstance(offers, list):
                    offers = offers[0]
                if isinstance(offers, dict) and "price" in offers:
                    return _parse_ars(str(offers["price"]))
    except Exception:
        pass
    return None


def _extract_price_from_body(
    body: str, min_ars: int = 300_000, max_ars: int = 8_000_000
) -> Optional[int]:
    """
    Fallback: find the first price in body text within the expected TV price range.
    Filters out installment prices and tax info.
    """
    body_clean = re.sub(
        r"\d+\s*(?:cuotas?|meses?|x)\s*(?:sin\s*inter[eé]s\s*)?(?:de\s*)?\$[\d.,]+",
        "",
        body,
    )
    body_clean = re.sub(
        r"sin\s*impuestos?\s*[\w\s]*\$[\d.,]+", "", body_clean, flags=re.IGNORECASE
    )
    for m in re.finditer(r"\$([\d.,]+)", body_clean):
        price = _parse_ars(m.group(1))
        if price and min_ars <= price <= max_ars:
            return price
    return None


def _wait_for_selector(page, selector: str, timeout: int = 5000) -> bool:
    """Wait for a selector to appear on the page."""
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except Exception:
        return False


def _random_delay(min_sec: float = 2, max_sec: float = 5):
    """Add random delay to mimic human behavior."""
    time.sleep(random.uniform(min_sec, max_sec))


# ── Site-Specific Scrapers ────────────────────────────────────────────────────

def _scrape_direct(
    ctx, name: str, url: str, selectors: list[str], wait_selector: Optional[str] = None
) -> dict:
    """
    Generic scraper: navigate to URL, try multiple selector strategies.
    Tries: JSON-LD → CSS selectors → body text extraction.
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
        print(f"  [{name}] Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        _random_delay(2, 4)

        # If specified, wait for a key selector (e.g., price element)
        if wait_selector:
            _wait_for_selector(page, wait_selector, timeout=5000)

        body = page.inner_text("body")

        # Strategy 1: Try JSON-LD (most reliable)
        cash_price = _find_price_by_json_ld(page)
        
        # Strategy 2: Try CSS selectors
        if not cash_price:
            cash_price = _find_price_by_selector(page, selectors)
        
        # Strategy 3: Extract from body text
        if not cash_price:
            cash_price = _extract_price_from_body(body)

        # Parse installments
        installment, interest_free = _parse_installments(body)

        result.update(
            {
                "cash_price_ars": cash_price,
                "installment_12m_ars": installment,
                "interest_free": interest_free,
                "product_url": page.url,
            }
        )
        print(f"  [{name}] ✓ Price: ${cash_price:,}" if cash_price else f"  [{name}] ✗ Price not found")

    except Exception as e:
        print(f"  [{name}] ✗ Error: {e}")
    finally:
        page.close()
    return result


# Mercado Libre
def scrape_mercadolibre(ctx) -> dict:
    return _scrape_direct(
        ctx,
        name="Mercado Libre",
        url=PRODUCT_URLS["Mercado Libre"],
        selectors=[
            ".ui-pdp-price__second-line .andes-money-amount__fraction",
            ".andes-money-amount__fraction",
            "[class*='price-tag'][class*='fraction']",
            ".ui-pdp-price span[class*='fraction']",
            "span.price-tag-fraction",
        ],
        wait_selector=".ui-pdp-price",
    )


# Frávega
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
        ],
        wait_selector="[data-test-id='cash-price']",
    )


# On City
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
            "[class*='finalPrice']",
            "span[class*='price']",
        ],
        wait_selector=".price-box",
    )


# Naldo
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
        wait_selector=".price-box",
    )


# Cetrogar
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
        wait_selector=".price-box",
    )


# ── Main Runner ───────────────────────────────────────────────────────────────

def run_all() -> list[dict]:
    """Run all scrapers with anti-bot measures."""
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
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
            permissions=["geolocation"],
            geolocation={"latitude": -34.6037, "longitude": -58.3816},
        )
        
        for fn in scrapers:
            print(f"\n[scrapers] Running {fn.__name__}...")
            try:
                results.append(fn(ctx))
            except Exception as e:
                print(f"[scrapers] {fn.__name__} failed: {e}")
            _random_delay(3, 6)  # Random delay between scrapers
        
        ctx.close()
        browser.close()

    return results
