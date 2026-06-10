"""
╔══════════════════════════════════════════════════════════════╗
║         Amazon Price Updater — Oceanside Hair Salon          ║
║  يحدث السعر في HTML + Product Schema تلقائياً لكل الصفحات   ║
╠══════════════════════════════════════════════════════════════╣
║  v2 — ASIN-based matching (data-asin + sku)                  ║
║  No more fragile regex on affiliate URL slugs.               ║
╚══════════════════════════════════════════════════════════════╝

التثبيت:
    pip install python-amazon-paapi

الاستخدام:
    python update_prices.py
    python update_prices.py --dry-run     ← معاينة بدون حفظ
    python update_prices.py --page neck   ← تحديث صفحة واحدة فقط
"""

import os
import re
import sys
import json
import time
import argparse
import traceback
from pathlib import Path
import datetime
from amazon_creatorsapi import AmazonCreatorsApi, Country
import yaml

class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(IndentDumper, self).increase_indent(flow, False)

# Force standard output to UTF-8 to prevent UnicodeEncodeError on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# تحميل متغيرات البيئة من ملف .env محلي إذا كان موجوداً
env_path = Path(".") / ".env"
if env_path.exists():
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    val_clean = val.strip().strip('"').strip("'")
                    os.environ[key.strip()] = val_clean
    except Exception as e:
        print(f"⚠️ Warning: Failed to read .env file: {e}")

# ════════════════════════════════════════════════════════════════
#  ⚙️  إعدادات عامة
# ════════════════════════════════════════════════════════════════

# نقرأ المفاتيح بأمان تام من متغيرات البيئة فقط
CREDENTIAL_ID     = os.environ.get("AMAZON_ACCESS_KEY", "")
CREDENTIAL_SECRET = os.environ.get("AMAZON_SECRET_KEY", "")
PARTNER_TAG       = "oceansidehair-20"
API_VERSION       = "3.1"

SITE_ROOT = Path(".")

# ════════════════════════════════════════════════════════════════
#  🗺️  خريطة الصفحات: مسار الملف  →  [ASIN, ...]
# ════════════════════════════════════════════════════════════════

PAGES: dict[str, list[str]] = {
    "blog/best-electric-shavers-sensitive-skin-2025/index.html": [
        "B0FGQQ9X2R",
        "B0F1P5JXCD",
        "B0D4B2T8SR",
        "B0CQ3TMHPM",
        "B0CQKPM9V3",
        "B01539X5TA",
    ],
    "blog/best-anti-frizz-products-oceanside/index.html": [
        "B07PW4MTHV",
        "B0DQTXH4S8",
        "B073CWSQ51",
        "B0B7QX7PPF",
        "B0B532VM9Q",
        "B08R4YZXTM",
        "B07JQ67JHF",
    ],
    "blog/best-shower-filters-water-softeners-hard-water-hair/index.html": [
        "B01MUBU0YC",
        "B0DJDDQG26",
        "B00BWIWYGC",
        "B0D8RGF49F",
        "B010MR6T2I",
        "B075ZBH2RP",
    ],
    "blog/shampoos-that-work-hard-water-hair/index.html": [
        "B01N23J5C1",
        "B01NAQI2AZ",
        "B0CT6TPGNJ",
        "B08XB2BQC1",
        "B0001Y74XG",
        "B07N7LCD2Z",
        "B000UPEDXU",
    ],
    "blog/electric-shavers/best-for-acne-ingrown-hair/index.html": [
        "B0BZDPFH45",
        "B07X342321",
        "B0FHDF5YQN",
        "B000VVT94G",
    ],
    "blog/electric-shavers/best-for-neck/index.html": [
        "B0BZDPFH45",
        "B0FGQQ9X2R",
        "B0F1PKHWNX",
        "B0D4B2T8SR",
        "B07X342321",
    ],
    "blog/shaving/best-shaving-cream-hard-water/index.html": [
        "B0084GVSWG",
        "B07PGWPMD8",
        "B002A5OLHQ",
        "B000GHYXG4"
    ],
}

# ════════════════════════════════════════════════════════════════
#  🔧  جلب تفاصيل المنتجات من Amazon API (الأسعار، التقييمات، الصور)
# ════════════════════════════════════════════════════════════════

def fetch_product_details(api: AmazonCreatorsApi, asins: list[str]) -> dict[str, dict]:
    """
    Fetches live details (price, stars, reviews count, image URL) for a list of ASINs from the Amazon Creators API.
    Returns a dict mapping ASIN → details dict.
    Runs successfully even if the product is out of stock.
    """
    details: dict[str, dict] = {}
    unique_asins = list(dict.fromkeys(asins))
    
    from amazon_creatorsapi.models import GetItemsResource
    resources = [
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_PRICE,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_AVAILABILITY,
        GetItemsResource.OFFERS_V2_DOT_LISTINGS_DOT_IS_BUY_BOX_WINNER,
        GetItemsResource.CUSTOMER_REVIEWS_DOT_COUNT,
        GetItemsResource.CUSTOMER_REVIEWS_DOT_STAR_RATING,
        GetItemsResource.IMAGES_DOT_PRIMARY_DOT_LARGE,
        GetItemsResource.ITEM_INFO_DOT_TITLE,
    ]

    for i in range(0, len(unique_asins), 10):
        batch = unique_asins[i : i + 10]
        try:
            items = api.get_items(batch, resources=resources)
            for item in items:
                # 1. Extract Price
                price_str = _extract_price(item)
                price_val = _price_to_numeric_str(price_str) if price_str else "Check Price"
                
                # 2. Extract rating stars and reviews count
                rating_val, reviews_count = _extract_reviews_and_stars(item)
                
                # 3. Extract image URL
                image_url = _extract_image_url(item)
                
                # 4. Extract title
                title = None
                try:
                    if item.item_info and item.item_info.title:
                        title = item.item_info.title.display_value
                except AttributeError:
                    pass

                details[item.asin] = {
                    "price": price_val,
                    "rating_stars_val": rating_val,
                    "rating_count_val": reviews_count,
                    "image_url": image_url,
                    "title": title
                }
                print(f"   ✅ {item.asin}: Price={price_val}, Stars={rating_val}, Reviews={reviews_count}, Image={'Yes' if image_url else 'No'}")
        except Exception as exc:
            print(f"   ❌ خطأ في جلب الـ batch {batch}: {exc}")
        if i + 10 < len(unique_asins):
            time.sleep(1)
    return details


def _extract_reviews_and_stars(item) -> tuple[float | None, int | None]:
    try:
        reviews = item.customer_reviews
        if reviews:
            count = getattr(reviews, "count", None)
            rating = getattr(reviews, "star_rating", None)
            rating_val = getattr(rating, "value", None) if rating else None
            return rating_val, count
    except AttributeError:
        pass
    return None, None


def _extract_image_url(item) -> str | None:
    try:
        images = item.images
        if images and images.primary and images.primary.large:
            return images.primary.large.url
    except AttributeError:
        pass
    return None


def _build_rating_stars(val: float, original_val: str | None = None) -> str:
    stars = "★" * round(val) + "☆" * (5 - round(val))
    if original_val and "/5" in str(original_val):
        return f"{val:.1f}/5 {stars}"
    return f"{val:.1f} {stars}"


def _build_rating_count(count: int, original_val: str | None = None) -> str:
    formatted_count = f"{count:,}"
    if original_val and "ratings" in str(original_val).lower():
        suffix = "Ratings" if "Ratings" in str(original_val) else "ratings"
        return f"{formatted_count} {suffix}"
    return f"{formatted_count} Ratings"


def _extract_price(item) -> str | None:
    """
    Attempts to extract a display price from an API item object.
    Tries the Buy Box winner first; falls back to the first listing.
    Returns a plain numeric string like "49.96", or None if unavailable.
    """
    try:
        listings = item.offers_v2.listings
        if not listings:
            return None
        chosen = next((l for l in listings if getattr(l, "is_buy_box_winner", False)), None)
        if chosen is None:
            chosen = listings[0]

        try:
            val = chosen.price.money.display_amount
            if val:
                return re.sub(r"[^\d.]", "", val)
        except AttributeError:
            pass

        try:
            amount = float(chosen.price.money.amount)
            return f"{amount:.2f}"
        except (AttributeError, TypeError, ValueError):
            pass

    except AttributeError:
        pass
    return None


def _price_to_numeric_str(price_str: str) -> str:
    """
    Strips non-numeric symbols and formats the number to always have 2 decimal places.
    """
    clean_str = re.sub(r"[^\d.]", "", str(price_str))
    try:
        return f"{float(clean_str):.2f}"
    except ValueError:
        return clean_str


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث HTML — استهداف <span data-asin="ASIN">
# ════════════════════════════════════════════════════════════════

def update_html(html: str, asin: str, new_price: str) -> tuple[str, bool]:
    """
    Finds <span data-asin="ASIN">OLD_PRICE</span> and replaces the
    text content with new_price.
    Returns (updated_html, was_changed).
    """
    numeric = _price_to_numeric_str(new_price) if new_price != "Check Price" else new_price
    pattern = re.compile(
        r'(<span\b[^>]*\bdata-asin="' + re.escape(asin) + r'"[^>]*>)'
        r'([^<]+)'
        r'(</span>)',
        re.IGNORECASE,
    )

    changed = False

    def replacer(m: re.Match) -> str:
        nonlocal changed
        current = m.group(2).strip()
        if current != numeric:
            changed = True
            print(f"      📝 HTML  [{asin}]: {current!r} → {numeric!r}")
        return m.group(1) + numeric + m.group(3)

    updated = pattern.sub(replacer, html)
    return updated, changed


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث Schema JSON-LD — مطابقة عبر "sku"
# ════════════════════════════════════════════════════════════════

_SCRIPT_RE = re.compile(
    r'(<script\s[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
    re.DOTALL | re.IGNORECASE,
)


def update_schema(html: str, asin: str, new_price: str) -> tuple[str, bool]:
    """
    Parses every JSON-LD <script> block in the page, then walks the
    JSON object tree looking for Offer / AggregateOffer nodes whose
    "sku" field matches the ASIN. Updates schema to add/update price,
    shippingDetails, availability, and merchantReturnPolicy.
    Returns (updated_html, was_changed).
    """
    numeric = _price_to_numeric_str(new_price)
    changed = False

    def script_replacer(m: re.Match) -> str:
        nonlocal changed
        raw_json = m.group(2)
        try:
            obj = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            print(f"      ⚠️  JSON parse error in schema block: {exc}")
            return m.group(0)

        block_changed, obj = _walk_and_update(obj, asin, numeric)
        if block_changed:
            changed = True
            updated_json = json.dumps(obj, ensure_ascii=False, indent=2)
            return m.group(1) + "\n" + updated_json + "\n    " + m.group(3)
        return m.group(0)

    updated_html = _SCRIPT_RE.sub(script_replacer, html)
    return updated_html, changed


def _walk_and_update(obj: object, asin: str, numeric_str: str) -> tuple[bool, object]:
    """
    Recursively walks a parsed JSON object. Updates/rebuilds "offers" if needed.
    """
    modified = False

    if isinstance(obj, dict):
        # 1. Rebuild offers if it was removed previously
        if obj.get("@type") == "Product" and obj.get("sku") == asin:
            if "offers" not in obj:
                new_offer = {
                    "@type": "Offer",
                    "sku": asin,
                    "price": numeric_str,
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                    "shippingDetails": {
                        "@type": "OfferShippingDetails",
                        "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": "USD"},
                        "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "US"},
                        "deliveryTime": {
                            "@type": "ShippingDeliveryTime",
                            "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "d"},
                            "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 5, "unitCode": "d"}
                        }
                    },
                    "hasMerchantReturnPolicy": {
                        "@type": "MerchantReturnPolicy",
                        "applicableCountry": "US",
                        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                        "merchantReturnDays": 30,
                        "returnMethod": "https://schema.org/ReturnByMail",
                        "returnFees": "https://schema.org/FreeReturn"
                    }
                }
                if "url" in obj:
                    new_offer["url"] = obj["url"]
                    
                obj["offers"] = new_offer
                print(f"      ✨ Schema [{asin}]: Rebuilt 'offers' block with price, URL, and shipping/return policies")
                modified = True
                 
        # 2. Standard update if the offer already exists
        if obj.get("@type") in ("Offer", "AggregateOffer") and obj.get("sku") == asin:
            if str(obj.get("price")) != numeric_str:
                print(f"      📝 Schema [{asin}]: Price updated to {numeric_str}")
                obj["price"] = numeric_str
                modified = True
            
            if obj.get("availability") == "https://schema.org/OutOfStock":
                obj["availability"] = "https://schema.org/InStock"
                print(f"      🔄 Schema [{asin}]: Marked back as InStock")
                modified = True

            if "shippingDetails" not in obj:
                obj["shippingDetails"] = {
                    "@type": "OfferShippingDetails",
                    "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": "USD"},
                    "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "US"},
                    "deliveryTime": {
                        "@type": "ShippingDeliveryTime",
                        "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "d"},
                        "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 5, "unitCode": "d"}
                    }
                }
                print(f"      📦 Schema [{asin}]: Added missing shippingDetails")
                modified = True
                
            if "hasMerchantReturnPolicy" not in obj:
                obj["hasMerchantReturnPolicy"] = {
                    "@type": "MerchantReturnPolicy",
                    "applicableCountry": "US",
                    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                    "merchantReturnDays": 30,
                    "returnMethod": "https://schema.org/ReturnByMail",
                    "returnFees": "https://schema.org/FreeReturn"
                }
                print(f"      🔄 Schema [{asin}]: Added missing hasMerchantReturnPolicy")
                modified = True
                
        for key, val in list(obj.items()):
            sub_modified, obj[key] = _walk_and_update(val, asin, numeric_str)
            if sub_modified:
                modified = True
            
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_modified, obj[idx] = _walk_and_update(item, asin, numeric_str)
            if sub_modified:
                modified = True
            
    return modified, obj


def update_offer_fallback_in_schema(html: str, asin: str) -> tuple[str, bool]:
    """
    Finds a Product schema block matching ASIN, saves sku & url on it, and deletes
    its "offers" field so Google doesn't index an outdated price or out-of-stock item.
    Returns (updated_html, was_changed).
    """
    changed = False

    def script_replacer(m: re.Match) -> str:
        nonlocal changed
        raw_json = m.group(2)
        try:
            obj = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            print(f"      ⚠️  JSON parse error in schema block: {exc}")
            return m.group(0)

        block_changed, obj = _walk_schema_fallback(obj, asin)
        if block_changed:
            changed = True
            updated_json = json.dumps(obj, ensure_ascii=False, indent=2)
            return m.group(1) + "\n" + updated_json + "\n    " + m.group(3)
        return m.group(0)

    updated_html = _SCRIPT_RE.sub(script_replacer, html)
    return updated_html, changed


def _walk_schema_fallback(obj: object, asin: str) -> tuple[bool, object]:
    modified = False

    if isinstance(obj, dict):
        if obj.get("@type") == "Product" and "offers" in obj:
            offer = obj["offers"]
            if isinstance(offer, dict) and offer.get("sku") == asin:
                # Save ASIN (sku) and affiliate URL to Product block before deleting offer
                obj["sku"] = asin 
                if "url" in offer:
                    obj["url"] = offer["url"]
                
                del obj["offers"]
                print(f"      🗑️ Schema: Removed 'offers' but saved URL for {asin}")
                modified = True
                
        for key, val in list(obj.items()):
            sub_modified, obj[key] = _walk_schema_fallback(val, asin)
            if sub_modified:
                modified = True
            
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_modified, obj[idx] = _walk_schema_fallback(item, asin)
            if sub_modified:
                modified = True
            
    return modified, obj


def update_timestamp(html_content: str) -> tuple[str, bool]:
    """
    Updates the price timestamp to Pacific Time.
    """
    now_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p PT")
    changed = False
    
    pattern = re.compile(
        r'(<span\s+id="price-timestamp"[^>]*>)(.*?)(</span>)',
        re.IGNORECASE | re.DOTALL
    )
    
    def replacer(m: re.Match) -> str:
        nonlocal changed
        if m.group(2) != now_str:
            print(f"      🕒 Timestamp updated to: {now_str}")
            changed = True
        return m.group(1) + now_str + m.group(3)

    updated_html = pattern.sub(replacer, html_content)
    return updated_html, changed


# ════════════════════════════════════════════════════════════════
#  🚀  الدالة الرئيسية
# ════════════════════════════════════════════════════════════════

def run(dry_run: bool = False, page_filter: str | None = None) -> None:
    print("═" * 60)
    print("  🛒 Amazon Price & Metadata Updater v3 — Oceanside Hair Salon")
    print("═" * 60)

    if not CREDENTIAL_ID or not CREDENTIAL_SECRET:
        print("\n❌ Error: Amazon API credentials (AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY) are missing.")
        print("   Please set the environment variables AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY.")
        sys.exit(1)

    try:
        print("\n🔌 Connecting to Amazon Creators API...")
        api = AmazonCreatorsApi(
            credential_id=CREDENTIAL_ID,
            credential_secret=CREDENTIAL_SECRET,
            version=API_VERSION,
            tag=PARTNER_TAG,
            country=Country.US,
        )
        print("✅ Connected.\n")
    except Exception as exc:
        print(f"❌ Failed to connect to Amazon API: {exc}")
        sys.exit(1)

    total_updated = 0

    for rel_path, asins in PAGES.items():
        if page_filter and page_filter.lower() not in rel_path.lower():
            continue

        file_path = SITE_ROOT / rel_path
        print(f"{'─' * 60}")
        print(f"📄 Processing: {rel_path}")

        if not file_path.exists():
            print(f"   ⚠️  الملف غير موجود: {file_path}")
            continue

        unique_asins = list(dict.fromkeys(asins))
        
        print(f"   📦 Fetching {len(unique_asins)} ASIN(s) metadata from Amazon API...")
        details = fetch_product_details(api, unique_asins)

        html = file_path.read_text(encoding="utf-8")
        original_html = html
        page_changed = False

        # Try to parse front matter to check if it's a data-driven page
        fm = None
        body = html
        if html.startswith("---"):
            parts = html.split("---", 2)
            if len(parts) >= 3:
                try:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict) and "products" in fm:
                        body = parts[2]
                    else:
                        fm = None
                except Exception as e:
                    print(f"      ⚠️  Error parsing Front Matter YAML: {e}")
                    fm = None

        if fm is not None:
            # YAML-based dynamic page
            for asin in unique_asins:
                prod_details = details.get(asin)
                if not prod_details:
                    print(f"\n   ⚠️  Failed to fetch details for {asin}")
                    continue
                
                new_price = prod_details["price"]
                new_stars_val = prod_details["rating_stars_val"]
                new_count_val = prod_details["rating_count_val"]
                new_image_url = prod_details["image_url"]

                # Update product price in Front Matter
                for product in fm.get("products", []):
                    if product.get("asin") == asin:
                        # 1. Update Price
                        current_price = str(product.get("price", "")).strip()
                        numeric_new_price = _price_to_numeric_str(new_price) if new_price != "Check Price" else new_price
                        if current_price != numeric_new_price:
                            product["price"] = numeric_new_price
                            print(f"      📝 YAML Price  [{asin}]: {current_price!r} → {numeric_new_price!r}")
                            page_changed = True
                            
                        # handle stock warnings automatically
                        if numeric_new_price == "Check Price":
                            if "stock_warning" not in product:
                                product["stock_warning"] = "Temporarily Out of Stock"
                                print(f"      ⚠️  YAML Stock  [{asin}]: Product out of stock, added warning")
                                page_changed = True
                        else:
                            if "stock_warning" in product:
                                del product["stock_warning"]
                                print(f"      🔄 YAML Stock  [{asin}]: Product back in stock, removed warning")
                                page_changed = True

                        # 2. Update Rating Stars
                        if new_stars_val is not None:
                            old_stars = product.get("rating_stars")
                            formatted_stars = _build_rating_stars(new_stars_val, old_stars)
                            if old_stars != formatted_stars:
                                product["rating_stars"] = formatted_stars
                                print(f"      📝 YAML Stars  [{asin}]: {old_stars!r} → {formatted_stars!r}")
                                page_changed = True

                        # 3. Update Rating Count
                        if new_count_val is not None:
                            old_count = product.get("rating_count")
                            formatted_count = _build_rating_count(new_count_val, old_count)
                            if old_count != formatted_count:
                                product["rating_count"] = formatted_count
                                print(f"      📝 YAML Reviews [{asin}]: {old_count!r} → {formatted_count!r}")
                                page_changed = True

                        # 4. Update Product Image (Legal direct CDN hotlink)
                        if new_image_url:
                            old_amazon_image = product.get("amazon_image_url")
                            if old_amazon_image != new_image_url:
                                product["amazon_image_url"] = new_image_url
                                print(f"      📝 YAML Amazon Image [{asin}]: {old_amazon_image!r} → {new_image_url!r}")
                                page_changed = True

            body, time_changed = update_timestamp(body)
            if time_changed:
                page_changed = True

            if page_changed:
                fm_yaml = yaml.dump(fm, Dumper=IndentDumper, allow_unicode=True, default_flow_style=False, sort_keys=False, indent=2)
                html = f"---\n{fm_yaml}---{body}"
        else:
            # Legacy HTML/Regex-based page
            for asin in unique_asins:
                prod_details = details.get(asin)
                if not prod_details:
                    continue
                new_price = prod_details["price"]
                
                if new_price == "Check Price":
                    print(f"\n   ⚠️  Failed to fetch price for {asin} → Applying Fallback (Check Price)")
                    html, html_changed = update_html(html, asin, "Check Price")
                    html, schema_changed = update_offer_fallback_in_schema(html, asin)
                    
                    if html_changed or schema_changed:
                        page_changed = True
                    continue

                print(f"\n   🏷️  {asin} → ${new_price}")

                # ── 1. Update the visible HTML price (<span data-asin="ASIN">) ──
                html, html_changed = update_html(html, asin, new_price)

                # ── 2. Update the JSON-LD Schema price ("sku": "ASIN") ──────────
                html, schema_changed = update_schema(html, asin, new_price)

                if html_changed or schema_changed:
                    page_changed = True
                else:
                    print(f"      ℹ️  {asin}: السعر لم يتغير")
                    
            html, time_changed = update_timestamp(html)
        if time_changed:
            page_changed = True
            
        # ── Save the file (or report in dry-run mode) ────────────────────────
        if page_changed:
            if dry_run:
                print(f"\n   🔍 [DRY-RUN] تغييرات موجودة — لم يتم الحفظ.")
            else:
                file_path.write_text(html, encoding="utf-8")
                print(f"\n   💾 تم الحفظ: {rel_path}")
            total_updated += 1
        else:
            print(f"\n   ℹ️  لا تغييرات مطلوبة في هذه الصفحة.")

    print(f"\n{'═' * 60}")
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"  🎉 {mode}اكتمل! {total_updated} صفحة تم تحديثها.")
    print("═" * 60)


# ════════════════════════════════════════════════════════════════
#  🖥️  نقطة الدخول
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Amazon Price Updater v2 — Oceanside Hair Salon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="معاينة التغييرات بدون حفظ الملفات",
    )
    parser.add_argument(
        "--page",
        type=str,
        default=None,
        metavar="KEYWORD",
        help="تحديث صفحة واحدة فقط (مثال: --page neck)",
    )
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run, page_filter=args.page)
    except KeyboardInterrupt:
        print("\n⚠️  تم الإيقاف بواسطة المستخدم.")
    except Exception as exc:
        print(f"\n❌ خطأ غير متوقع: {exc}")
        traceback.print_exc()
        raise SystemExit(1)