"""
╔══════════════════════════════════════════════════════════════╗
║         Amazon Price Updater — Powered by APIFY              ║
║  يحدث السعر في Front Matter + HTML + Schema تلقائياً لكل الصفحات ║
╠══════════════════════════════════════════════════════════════╣
║  v3.1 — Multi-token failover & resume where stopped          ║
║  Compatible with Jekyll templates & water_products.json     ║
╚══════════════════════════════════════════════════════════════╝

التثبيت:
    pip install apify-client pyyaml

الاستخدام:
    python update_prices_apify.py
    python update_prices_apify.py --dry-run     ← معاينة بدون حفظ
    python update_prices_apify.py --page neck   ← تحديث صفحة واحدة فقط
"""

import os
import re
import sys
import json
import time
import argparse
import traceback
import datetime
from pathlib import Path
from apify_client import ApifyClient
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

ACTOR_ID  = "XVDTQc4a7MDTqSTMJ"
SITE_ROOT = Path(".")


def get_apify_tokens() -> list[str]:
    """
    Returns available Apify tokens in order of preference.
    Checks APIFY_TOKEN_1, APIFY_TOKEN_2, ..., and APIFY_TOKEN as fallback.
    """
    tokens = []
    idx = 1
    while True:
        tok = os.environ.get(f"APIFY_TOKEN_{idx}")
        if tok and tok.strip():
            cleaned = tok.strip()
            if cleaned not in tokens:
                tokens.append(cleaned)
            idx += 1
        else:
            break

    # Fallback to APIFY_TOKEN if not already included
    single_tok = os.environ.get("APIFY_TOKEN", "").strip()
    if single_tok and single_tok not in tokens:
        tokens.append(single_tok)

    return tokens


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
#  🔧  جلب تفاصيل المنتجات من Apify مع نظام التبديل والاستئناف
# ════════════════════════════════════════════════════════════════

def fetch_product_details_apify(asins: list[str]) -> dict[str, dict]:
    """
    Fetches live details (price, stars, reviews count, image URL, title)
    for a list of ASINs using Apify with multi-token failover.
    If Token 1 fails or hits its monthly/quota limit mid-run, Token 2
    resumes fetching the remaining unfetched ASINs from where Token 1 stopped.
    """
    tokens = get_apify_tokens()
    if not tokens:
        print("\n❌ Error: No Apify API tokens found.")
        print("   Please set APIFY_TOKEN_1 and/or APIFY_TOKEN_2 in .env")
        sys.exit(1)

    unique_asins = list(dict.fromkeys(asins))
    if not unique_asins:
        return {}

    details: dict[str, dict] = {}
    remaining_asins = list(unique_asins)

    for token_idx, token in enumerate(tokens, start=1):
        if not remaining_asins:
            print(f"\n✨ تم جلب جميع المنتجات بنجاح ({len(details)}/{len(unique_asins)}).")
            break

        masked_token = token[:12] + "..." + token[-4:] if len(token) > 16 else "***"
        print(f"\n🔑 استخدام مفتاح Apify رقم [{token_idx}/{len(tokens)}] ({masked_token})")
        print(f"   🎯 عدد المنتجات المطلوب جلبها الآن: {len(remaining_asins)} منتج(ات)...")

        client = ApifyClient(token)
        urls = [{"url": f"https://www.amazon.com/dp/{asin}"} for asin in remaining_asins]
        run_input = {
            "categoryUrls": urls,
            "maxItemsPerStartUrl": 1,
            "useCaptchaSolver": False
        }

        dataset_id = None
        run_status = None
        run_error_msg = None

        try:
            print(f"   🚀 بدء تشغيل الـ Actor ({ACTOR_ID}) عبر المفتاح {token_idx}...")
            started_run = client.actor(ACTOR_ID).start(run_input=run_input)
            run_id = started_run["id"]
            dataset_id = started_run.get("defaultDatasetId")

            # Wait for the run to finish
            finished_run = client.run(run_id).wait_for_finish()
            if finished_run:
                run_status = finished_run.get("status")
                dataset_id = finished_run.get("defaultDatasetId") or dataset_id
                if run_status != "SUCCEEDED":
                    run_error_msg = finished_run.get("statusMessage") or f"Run finished with status {run_status}"
            else:
                run_status = "UNKNOWN"

        except Exception as exc:
            run_error_msg = str(exc)
            print(f"   ⚠️ استثناء أثناء تشغيل المفتاح {token_idx}: {exc}")

        # قراءة أي بيانات تم إنتاجها في الـ dataset (حتى لو توقف الـ Actor في المنتصف بسبب نفاد الرصيد)
        fetched_count_this_turn = 0
        if dataset_id:
            try:
                items_page = client.dataset(dataset_id).list_items(limit=1000)
                for item in items_page.items:
                    # استخراج ASIN
                    item_url = item.get("url", "")
                    asin_match = re.search(r'/dp/([A-Z0-9]{10})', item_url)
                    asin = item.get("asin") or item.get("originalAsin") or (asin_match.group(1) if asin_match else None)
                    if not asin or asin in details:
                        continue

                    # 1. Price extraction
                    price_str = None
                    price_data = item.get("price")
                    if isinstance(price_data, dict) and "value" in price_data:
                        price_str = str(price_data["value"])
                    elif isinstance(price_data, (int, float)):
                        price_str = str(price_data)
                    elif isinstance(price_data, str):
                        price_str = price_data
                    elif item.get("prices") and isinstance(item.get("prices"), list) and item["prices"]:
                        first = item["prices"][0]
                        if isinstance(first, dict) and "value" in first:
                            price_str = str(first["value"])
                        elif isinstance(first, (int, float, str)):
                            price_str = str(first)

                    price_val = _price_to_numeric_str(price_str) if price_str else "Check Price"

                    # 2. Rating stars
                    rating_val = None
                    raw_stars = item.get("stars") or item.get("rating") or item.get("starRating")
                    if raw_stars is not None:
                        try:
                            if isinstance(raw_stars, (int, float)):
                                rating_val = float(raw_stars)
                            else:
                                stars_match = re.search(r"(\d+(\.\d+)?)", str(raw_stars))
                                if stars_match:
                                    rating_val = float(stars_match.group(1))
                        except (ValueError, TypeError):
                            pass

                    # 3. Reviews count
                    reviews_count = None
                    raw_count = (
                        item.get("reviewsCount")
                        or item.get("reviewCount")
                        or item.get("ratingsCount")
                        or item.get("reviews_count")
                    )
                    if raw_count is not None:
                        try:
                            if isinstance(raw_count, int):
                                reviews_count = raw_count
                            else:
                                count_clean = re.sub(r"[^\d]", "", str(raw_count))
                                if count_clean:
                                    reviews_count = int(count_clean)
                        except (ValueError, TypeError):
                            pass

                    # 4. Image URL
                    image_url = (
                        item.get("thumbnailImage")
                        or item.get("image")
                        or item.get("imageUrl")
                        or item.get("mainImage")
                    )
                    if not image_url and isinstance(item.get("highResolutionImages"), list) and item["highResolutionImages"]:
                        image_url = item["highResolutionImages"][0]

                    # 5. Title
                    title = item.get("title")

                    details[asin] = {
                        "price": price_val,
                        "rating_stars_val": rating_val,
                        "rating_count_val": reviews_count,
                        "image_url": image_url,
                        "title": title
                    }
                    fetched_count_this_turn += 1
                    print(f"      ✅ [{asin}] Price={price_val}, Stars={rating_val}, Reviews={reviews_count}")

            except Exception as e:
                print(f"   ⚠️ خطأ في قراءة بيانات الـ dataset للمفتاح {token_idx}: {e}")

        # تحديث قائمة المنتجات المتبقية التي لم يتم جلبها
        remaining_asins = [a for a in unique_asins if a not in details]
        print(f"   📊 حصيلة المفتاح {token_idx}: تم جلب {fetched_count_this_turn} منتج بنجاح. المتبقي: {len(remaining_asins)} منتج.")

        # التحقق مما إذا كانت جميع المنتجات قد جُلبت
        if not remaining_asins:
            print(f"   🎉 اكتمل جلب جميع المنتجات المطلوبة بواسطة المفتاح {token_idx}!")
            break

        # إذا كانت هناك منتجات متبقية ويوجد مفتاح تالٍ:
        if token_idx < len(tokens):
            if run_error_msg or (run_status and run_status != "SUCCEEDED"):
                print(f"\n   🔄 [تبديل المفتاح] المفتاح {token_idx} توقف أو وصل للحد الأقصى ({run_error_msg or run_status}).")
            else:
                print(f"\n   🔄 [تبديل المفتاح] المفتاح {token_idx} لم يكمل جميع الـ ASINs.")
            print(f"   ➡️ سيتم الآن تشغيل المفتاح رقم {token_idx + 1} لاستكمال جلب الـ {len(remaining_asins)} منتج المتبقية من حيث توقف!")
        else:
            print(f"\n   ⚠️ تم استنفاد جميع المفاتيح المتاحة ({len(tokens)}). بقيت {len(remaining_asins)} منتجات لم يتم جلبها.")

    return details


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
#  🔧  تحديث water_products.json
# ════════════════════════════════════════════════════════════════

def get_water_products_asins() -> list[str]:
    json_path = SITE_ROOT / "tools/water-hardness-checker/water_products.json"
    if not json_path.exists():
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        asins = []
        for cat_id, category in data.items():
            for item in category.get("items", []):
                asin = item.get("asin", "")
                if re.match(r"^[A-Z0-9]{10}$", asin):
                    asins.append(asin)
        return asins
    except Exception:
        return []


def update_water_products(details: dict[str, dict], dry_run: bool = False) -> bool:
    json_path = SITE_ROOT / "tools/water-hardness-checker/water_products.json"
    print("─" * 60)
    print(f"📄 Processing JSON: tools/water-hardness-checker/water_products.json")

    if not json_path.exists():
        print(f"   ⚠️  الملف غير موجود: {json_path}")
        return False

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"   ❌ خطأ في قراءة ملف JSON: {e}")
        return False

    changed = False

    for cat_id, category in data.items():
        items = category.get("items", [])
        for item in items:
            asin = item.get("asin", "")
            if asin in details:
                prod_details = details[asin]
                new_price = prod_details.get("price")
                new_stars_val = prod_details.get("rating_stars_val")
                new_count_val = prod_details.get("rating_count_val")
                new_image_url = prod_details.get("image_url")

                # 1. Update Price
                if new_price:
                    current_price = str(item.get("price", "")).strip()
                    numeric_new_price = _price_to_numeric_str(new_price) if new_price != "Check Price" else new_price
                    if current_price != numeric_new_price:
                        item["price"] = numeric_new_price
                        print(f"      📝 JSON Price  [{asin}]: {current_price!r} → {numeric_new_price!r}")
                        changed = True

                # 2. Update Rating Stars
                if new_stars_val is not None:
                    old_stars = item.get("rating_stars")
                    formatted_stars = _build_rating_stars(new_stars_val, old_stars)
                    if old_stars != formatted_stars:
                        item["rating_stars"] = formatted_stars
                        print(f"      📝 JSON Stars  [{asin}]: {old_stars!r} → {formatted_stars!r}")
                        changed = True

                # 3. Update Rating Count
                if new_count_val is not None:
                    old_count = item.get("rating_count")
                    formatted_count = _build_rating_count(new_count_val, old_count)
                    if old_count != formatted_count:
                        item["rating_count"] = formatted_count
                        print(f"      📝 JSON Reviews [{asin}]: {old_count!r} → {formatted_count!r}")
                        changed = True

                # 4. Update Product Image
                if new_image_url:
                    old_image = item.get("image_url")
                    if old_image != new_image_url:
                        item["image_url"] = new_image_url
                        print(f"      📝 JSON Image [{asin}]: {old_image!r} → {new_image_url!r}")
                        changed = True

    if changed:
        if dry_run:
            print(f"\n   🔍 [DRY-RUN] JSON تغييرات موجودة — لم يتم الحفظ.")
            return True
        else:
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"\n   💾 تم الحفظ: tools/water-hardness-checker/water_products.json")
                return True
            except Exception as e:
                print(f"   ❌ خطأ في حفظ ملف JSON: {e}")
                return False
    else:
        print(f"\n   ℹ️ لا تغييرات مطلوبة في ملف JSON.")
        return False


# ════════════════════════════════════════════════════════════════
#  🚀  الدالة الرئيسية
# ════════════════════════════════════════════════════════════════

def run(dry_run: bool = False, page_filter: str | None = None) -> None:
    print("═" * 60)
    print("  🛒 Amazon Price & Metadata Updater (APIFY) — Oceanside Hair Salon")
    print("═" * 60)

    tokens = get_apify_tokens()
    if not tokens:
        print("\n❌ Error: No Apify API tokens found.")
        print("   Please set APIFY_TOKEN_1 and/or APIFY_TOKEN_2 in .env")
        sys.exit(1)

    print(f"🔑 تم العثور على {len(tokens)} مفتاح(مفاتيح) Apify في البيئة.")

    # 1. Identify which pages to process
    target_pages = {}
    for rel_path, asins in PAGES.items():
        if page_filter and page_filter.lower() not in rel_path.lower():
            continue
        target_pages[rel_path] = asins

    # 2. Check if water_products.json is included
    process_water = False
    if not page_filter or any(kw in page_filter.lower() for kw in ["water", "json", "product"]):
        process_water = True

    # 3. Collect all unique ASINs needed across target pages & water products
    all_asins = []
    for asins in target_pages.values():
        all_asins.extend(asins)
    if process_water:
        all_asins.extend(get_water_products_asins())

    unique_asins = list(dict.fromkeys(all_asins))
    if not unique_asins:
        print("ℹ️ No products to update matching the filter.")
        return

    # 4. Fetch live data for all unique ASINs from Apify (with multi-token failover & resume)
    print(f"\n📦 إجمالي المنتجات المطلوب معالجتها: {len(unique_asins)} منتج.")
    details = fetch_product_details_apify(unique_asins)

    total_updated = 0

    # 5. Process each page
    for rel_path, asins in target_pages.items():
        file_path = SITE_ROOT / rel_path
        print(f"{'─' * 60}")
        print(f"📄 Processing: {rel_path}")

        if not file_path.exists():
            print(f"   ⚠️  الملف غير موجود: {file_path}")
            continue

        page_asins = list(dict.fromkeys(asins))
        html = file_path.read_text(encoding="utf-8")
        page_changed = False

        # Check for YAML Front Matter
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
            for asin in page_asins:
                prod_details = details.get(asin)
                if not prod_details:
                    print(f"   ⚠️  لم يتم جلب بيانات لـ {asin} من Apify (سيتم الاحتفاظ بالقيم الحالية)")
                    continue

                new_price = prod_details["price"]
                new_stars_val = prod_details["rating_stars_val"]
                new_count_val = prod_details["rating_count_val"]
                new_image_url = prod_details["image_url"]

                # Update product in Front Matter
                for product in fm.get("products", []):
                    if product.get("asin") == asin:
                        # 1. Update Price
                        current_price = str(product.get("price", "")).strip()
                        numeric_new_price = _price_to_numeric_str(new_price) if new_price != "Check Price" else new_price
                        if current_price != numeric_new_price:
                            product["price"] = numeric_new_price
                            print(f"      📝 YAML Price  [{asin}]: {current_price!r} → {numeric_new_price!r}")
                            page_changed = True

                        # Stock warning handling
                        if numeric_new_price == "Check Price":
                            target_warning = "Low Stock — Check Sellers or Newer Edition"
                            if product.get("stock_warning") != target_warning:
                                product["stock_warning"] = target_warning
                                print(f"      ⚠️  YAML Stock  [{asin}]: Limited stock notice applied")
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

                        # 4. Update Product Image
                        if new_image_url:
                            old_amazon_image = product.get("amazon_image_url")
                            if old_amazon_image != new_image_url:
                                product["amazon_image_url"] = new_image_url
                                print(f"      📝 YAML Amazon Image [{asin}]: {old_amazon_image!r} → {new_image_url!r}")
                                page_changed = True

                # Update HTML & Schema in the body of the YAML-based page
                if new_price == "Check Price":
                    body, html_changed = update_html(body, asin, "Check Price")
                    body, schema_changed = update_offer_fallback_in_schema(body, asin)
                else:
                    body, html_changed = update_html(body, asin, new_price)
                    body, schema_changed = update_schema(body, asin, new_price)

                if html_changed or schema_changed:
                    page_changed = True

            body, time_changed = update_timestamp(body)
            if time_changed:
                page_changed = True

            if page_changed:
                fm_yaml = yaml.dump(fm, Dumper=IndentDumper, allow_unicode=True, default_flow_style=False, sort_keys=False, indent=2)
                html = f"---\n{fm_yaml}---{body}"
        else:
            # Legacy HTML/Regex-based page
            for asin in page_asins:
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
                html, html_changed = update_html(html, asin, new_price)
                html, schema_changed = update_schema(html, asin, new_price)

                if html_changed or schema_changed:
                    page_changed = True
                else:
                    print(f"      ℹ️  {asin}: السعر لم يتغير")

            html, time_changed = update_timestamp(html)
            if time_changed:
                page_changed = True

        # Save or dry-run report
        if page_changed:
            if dry_run:
                print(f"\n   🔍 [DRY-RUN] تغييرات موجودة — لم يتم الحفظ.")
            else:
                file_path.write_text(html, encoding="utf-8")
                print(f"\n   💾 تم الحفظ: {rel_path}")
            total_updated += 1
        else:
            print(f"\n   ℹ️  لا تغييرات مطلوبة في هذه الصفحة.")

    # 6. Update water_products.json if applicable
    if process_water:
        json_updated = update_water_products(details, dry_run=dry_run)
        if json_updated:
            total_updated += 1

    print(f"\n{'═' * 60}")
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"  🎉 {mode}اكتمل! {total_updated} صفحة/ملف تم تحديثها.")
    print("═" * 60)


# ════════════════════════════════════════════════════════════════
#  🖥️  نقطة الدخول
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Amazon Price Updater (APIFY) — Oceanside Hair Salon",
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
