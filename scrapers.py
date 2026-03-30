"""
Site-specific scrapers for each Argentine retailer.
Uses Playwright (headless Chromium) to handle JS-rendered pages.
"""
import re
import time
from typing import Optional


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
    """
    Parse 12-month installment amount and interest-free flag from page text.
    """
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
    """
    Fallback: find the first price in body text within the expected TV price range.
    Ignores 'sin impuestos' sub-prices and installment amounts.
    """
    # Strip installment context lines to avoid false positives
    body_clean = re.sub(r"\d+\s*(?:cuotas?|meses?|x)\s*(?:sin\s*inter[eé]s\s*)?(?:de\s*)?\$[\d.,]+", "", body)
    body_clean = re.sub(r"sin\s*impuestos?\s*[\w\s]*\$[\d.,]+", "", body_clean, flags=re.IGNORECASE)

    for m in re.finditer(r"\$([\d.,]+)", body_clean):
        price = _parse_ars(m.group(1))
        if price and min_ars <= price <= max_ars:
            return price
    return None


# ── Base helper ──────────────────────────────────────────────────────────────────

def _scrape(playwright_context, name: str, search_url: str, scrape_fn) -> dict:
    page = playwright_context.new_page()
    result = {
        "retailer": name,
        "cash_price_ars": None,
        "installment_12m_ars": None,
        "interest_free": None,
        "product_url": search_url,
    }
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(2)
        result.update(scrape_fn(page))
    except Exception as e:
        print(f"[{name}] Error: {e}")
    finally:
        page.close()
    return result


# ── Mercado Libre ────────────────────────────────────────────────────────────────

def scrape_mercadolibre(ctx) -> dict:
    def _fn(page):
        search_url = page.url
        product_url = search_url
        navigated = False
        try:
            # Try multiple link selectors for MeLi search results
            selectors = [
                "a.poly-component__title",
                "a[class*='ui-search-link__title-card']",
                "li.ui-search-layout__item h2 a",
                "li.ui-search-layout__item a[href*='MLAr']",
                "li.ui-search-layout__item a[href*='.com.ar']",
            ]
            for sel in selectors:
                first = page.query_selector(sel)
                if first:
                    href = first.get_attribute("href")
                    if href and "mercadolibre" in href:
                        page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                        time.sleep(3)
                        product_url = page.url
                        navigated = (product_url != search_url)
                        break
        except Exception:
            pass

        body = page.inner_text("body")
        cash_price = _find_price(page, [
            ".ui-pdp-price__second-line .andes-money-amount__fraction",
            "span.andes-money-amount__fraction",
            ".price-tag-fraction",
        ])
        # Only use body fallback if we're on a product page
        if not cash_price and navigated:
            cash_price = _extract_price_from_body(body)

        installment, interest_free = _parse_installments(body) if navigated else (None, None)

        return {
            "cash_price_ars": cash_price,
            "installment_12m_ars": installment,
            "interest_free": interest_free,
            "product_url": product_url,
        }

    return _scrape(ctx, "Mercado Libre",
                   "https://listado.mercadolibre.com.ar/tcl-65c6k",
                   _fn)


# ── Frávega ──────────────────────────────────────────────────────────────────────

def scrape_fravega(ctx) -> dict:
    def _fn(page):
        try:
            first = page.query_selector(
                "a[data-test-id='product-card-link'], "
                "a[href*='/p/'], article a, .ProductCard a"
            )
            if first:
                href = first.get_attribute("href")
                if href and not href.startswith("http"):
                    href = "https://www.fravega.com" + href
                if href:
                    page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                    time.sleep(3)
        except Exception:
            pass

        body = page.inner_text("body")

        # Try CSS selectors first, then fall back to body text extraction
        cash_price = _find_price(page, [
            "[data-test-id='cash-price'] span",
            "[class*='CashPrice']",
            "[class*='cash-price']",
            "[class*='CurrentPrice']",
            "[class*='current-price']",
            "span[class*='Price']",
            "span[class*='price']",
        ])
        if not cash_price:
            cash_price = _extract_price_from_body(body)

        installment, interest_free = _parse_installments(body)

        return {
            "cash_price_ars": cash_price,
            "installment_12m_ars": installment,
            "interest_free": interest_free,
            "product_url": page.url,
        }

    return _scrape(ctx, "Fravega",
                   "https://www.fravega.com/l/?keyword=TCL+65C6K",
                   _fn)


# ── On City ──────────────────────────────────────────────────────────────────────

def scrape_oncity(ctx) -> dict:
    def _fn(page):
        try:
            first = page.query_selector(".product-item a, .product-card a, article a")
            if first:
                href = first.get_attribute("href")
                if href and not href.startswith("http"):
                    href = "https://www.oncity.com.ar" + href
                page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                time.sleep(2)
        except Exception:
            pass

        body = page.inner_text("body")
        cash_price = _find_price(page, [
            ".special-price .price",
            ".product-price-special",
            ".price-box .price",
            "span[class*='price']",
        ])
        if not cash_price:
            cash_price = _extract_price_from_body(body)

        installment, interest_free = _parse_installments(body)

        return {
            "cash_price_ars": cash_price,
            "installment_12m_ars": installment,
            "interest_free": interest_free,
            "product_url": page.url,
        }

    return _scrape(ctx, "On City",
                   "https://www.oncity.com.ar/catalogsearch/result/?q=TCL+65C6K",
                   _fn)


# ── Naldo ────────────────────────────────────────────────────────────────────────

def scrape_naldo(ctx) -> dict:
    def _fn(page):
        search_url = page.url
        navigated = False
        try:
            first = page.query_selector(
                "a.product-item-link, .product-name a, "
                "[class*='product-title'] a, article a"
            )
            if first:
                title = (first.inner_text() or "").upper()
                href = first.get_attribute("href") or ""
                # Only navigate if the product is TCL-related
                if "TCL" in title or "TCL" in href.upper() or "65C6K" in href.upper():
                    page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                    time.sleep(2)
                    navigated = (page.url != search_url)
        except Exception:
            pass

        if not navigated:
            return {
                "cash_price_ars": None,
                "installment_12m_ars": None,
                "interest_free": None,
                "product_url": search_url,
            }

        body = page.inner_text("body")
        cash_price = _find_price(page, [
            ".special-price .price",
            ".price-box .price",
            ".product-info-price .price",
            "span[class*='price']",
        ])
        if not cash_price:
            cash_price = _extract_price_from_body(body)

        installment, interest_free = _parse_installments(body)

        return {
            "cash_price_ars": cash_price,
            "installment_12m_ars": installment,
            "interest_free": interest_free,
            "product_url": page.url,
        }

    return _scrape(ctx, "Naldo",
                   "https://www.naldo.com.ar/buscar?q=TCL+65C6K",
                   _fn)


# ── Cetrogar ─────────────────────────────────────────────────────────────────────

def scrape_cetrogar(ctx) -> dict:
    def _fn(page):
        try:
            first = page.query_selector(".product-item-link, .product-name a, article a")
            if first:
                href = first.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = "https://www.cetrogar.com.ar" + href
                    page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                    time.sleep(2)
        except Exception:
            pass

        body = page.inner_text("body")
        cash_price = _find_price(page, [
            ".special-price .price",
            "[data-price-type='finalPrice'] .price",
            ".price-box .special-price .price",
            ".price-box .price",
            "span[class*='precio']",
        ])
        if not cash_price:
            cash_price = _extract_price_from_body(body)

        installment, interest_free = _parse_installments(body)

        return {
            "cash_price_ars": cash_price,
            "installment_12m_ars": installment,
            "interest_free": interest_free,
            "product_url": page.url,
        }

    return _scrape(ctx, "Cetrogar",
                   "https://www.cetrogar.com.ar/catalogsearch/result/?q=TCL+65C6K",
                   _fn)


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
