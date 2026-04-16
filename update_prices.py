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
import json
import time
import argparse
import traceback
from pathlib import Path
import datetime
from amazon_creatorsapi import AmazonCreatorsApi, Country

# ════════════════════════════════════════════════════════════════
#  ⚙️  إعدادات عامة
# ════════════════════════════════════════════════════════════════

CREDENTIAL_ID     = os.environ.get("AMAZON_ACCESS_KEY")
CREDENTIAL_SECRET = os.environ.get("AMAZON_SECRET_KEY")
PARTNER_TAG       = "oceansidehair-20"
API_VERSION       = "3.1"

SITE_ROOT = Path(".")

# ════════════════════════════════════════════════════════════════
#  🗺️  خريطة الصفحات: مسار الملف  →  [ASIN, ...]
#
#  ✅ v2 change: Affiliate URLs removed — ASIN is now the sole key
#     for both HTML and Schema matching. Much simpler & safer.
# ════════════════════════════════════════════════════════════════

PAGES: dict[str, list[str]] = {
    "blog/best-electric-shavers-sensitive-skin-2025/index.html": [
        "B07PW4MTHV",
        "B0F1P5JXCD",
        "B0D4B2T8SR",
        "B0CQ3TMHPM",
        "B0CQKPM9V3",
        "B01539X5TA",
    ],
    "blog/best-anti-frizz-products-oceanside/index.html": [
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
}

# ════════════════════════════════════════════════════════════════
#  🔧  جلب الأسعار من Amazon API
# ════════════════════════════════════════════════════════════════

def fetch_prices(api: AmazonCreatorsApi, asins: list[str]) -> dict[str, str]:
    """
    Fetches live prices for a list of ASINs from the Amazon Creators API.
    Returns a dict mapping ASIN → numeric price string (e.g. "49.96").
    ASINs with no available price are silently skipped.
    """
    prices: dict[str, str] = {}
    # Deduplicate while preserving order, then batch in groups of 10 (API limit)
    unique_asins = list(dict.fromkeys(asins))
    for i in range(0, len(unique_asins), 10):
        batch = unique_asins[i : i + 10]
        try:
            items = api.get_items(batch)
            for item in items:
                price_str = _extract_price(item)
                if price_str:
                    prices[item.asin] = price_str
                    print(f"   ✅ {item.asin}: {price_str}")
                else:
                    print(f"   ⚠️  {item.asin}: السعر غير متاح (out of stock or restricted)")
        except Exception as exc:
            print(f"   ❌ خطأ في جلب الـ batch {batch}: {exc}")
        # Respect Amazon API rate limits between batches
        if i + 10 < len(unique_asins):
            time.sleep(1)
    return prices


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
        # Prefer the Buy Box winner for the most accurate/current price
        chosen = next((l for l in listings if getattr(l, "is_buy_box_winner", False)), None)
        if chosen is None:
            chosen = listings[0]  # Fallback to first listing

        # Attempt 1: use the pre-formatted display_amount (e.g. "$49.96")
        try:
            val = chosen.price.money.display_amount
            if val:
                # Strip everything except digits and the decimal point
                return re.sub(r"[^\d.]", "", val)
        except AttributeError:
            pass

        # Attempt 2: build numeric string from raw amount + currency
        try:
            amount = float(chosen.price.money.amount)
            return f"{amount:.2f}"
        except (AttributeError, TypeError, ValueError):
            pass

    except AttributeError:
        pass
    return None


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث HTML — استهداف <span data-asin="ASIN">
# ════════════════════════════════════════════════════════════════

def update_html(html: str, asin: str, new_price: str) -> tuple[str, bool]:
    """
    Finds <span data-asin="ASIN">OLD_PRICE</span> and replaces the
    text content with new_price. The data-asin attribute is the
    single, unambiguous anchor — no URL slug matching needed.

    Returns (updated_html, was_changed).
    """
    # Pattern: opening tag with data-asin attribute (allows other attrs too),
    # then captures the current price text, then the closing tag.
    # The [^<]+ ensures we only replace text nodes, never nested HTML.
    pattern = re.compile(
        r'(<span\b[^>]*\bdata-asin="' + re.escape(asin) + r'"[^>]*>)'  # ① opening tag
        r'([^<]+)'                                                         # ② current price text
        r'(</span>)',                                                       # ③ closing tag
        re.IGNORECASE,
    )

    changed = False

    def replacer(m: re.Match) -> str:
        nonlocal changed
        current = m.group(2).strip()
        if current != new_price:
            changed = True
            print(f"      📝 HTML  [{asin}]: {current!r} → {new_price!r}")
        # Preserve the original whitespace/indentation style around the number
        return m.group(1) + new_price + m.group(3)

    updated = pattern.sub(replacer, html)
    return updated, changed


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث Schema JSON-LD — مطابقة عبر "sku"
# ════════════════════════════════════════════════════════════════

# Regex that isolates every <script type="application/ld+json"> block
_SCRIPT_RE = re.compile(
    r'(<script\s[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
    re.DOTALL | re.IGNORECASE,
)


def update_schema(html: str, asin: str, new_price: str) -> tuple[str, bool]:
    """
    Parses every JSON-LD <script> block in the page, then walks the
    JSON object tree looking for Offer / AggregateOffer nodes whose
    "sku" field matches the ASIN.  Updates "price" to new_price and
    re-serialises the JSON back into the HTML.

    Using JSON parsing (not regex) means no risk of cross-contaminating
    prices between products that share a page.

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
            return m.group(0)  # Leave malformed block untouched

        block_changed, obj = _walk_and_update(obj, asin, new_price)
        if block_changed:
            changed = True
            # Re-serialise with matching indentation (2-space, no trailing space)
            updated_json = json.dumps(obj, ensure_ascii=False, indent=2)
            return m.group(1) + "\n" + updated_json + "\n    " + m.group(3)
        return m.group(0)

    updated_html = _SCRIPT_RE.sub(script_replacer, html)
    return updated_html, changed


def _walk_and_update(obj: object, asin: str, new_price: str) -> tuple[bool, object]:
    """
    Recursively walks a parsed JSON object (dict or list).
    When it finds a dict whose @type is "Offer" or "AggregateOffer"
    AND whose "sku" matches the target ASIN, it updates "price".

    Returns (was_modified, updated_obj).
    """
    modified = False

    if isinstance(obj, dict):
        offer_type = obj.get("@type", "")
        is_offer = offer_type in ("Offer", "AggregateOffer")
        sku_match = obj.get("sku", "") == asin

        if is_offer and sku_match and "price" in obj:
            old_price = str(obj["price"])
            if old_price != new_price:
                print(f"      📝 Schema [{asin}]: {old_price!r} → {new_price!r}")
                modified = True
            # Always write as a string to stay consistent with Google's
            # recommended format and avoid float precision surprises
            obj["price"] = new_price

        # Recurse into all child values regardless
        for key, val in obj.items():
            child_changed, obj[key] = _walk_and_update(val, asin, new_price)
            if child_changed:
                modified = True

    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            child_changed, obj[idx] = _walk_and_update(item, asin, new_price)
            if child_changed:
                modified = True

    return modified, obj

def update_timestamp(html_content: str) -> tuple[str, bool]:
    # تنسيق الوقت ليناسب توقيت كاليفورنيا (Pacific Time) بما أن جمهورك في Oceanside
    # مثال: "February 20, 2025 at 10:30 AM PT"
    now_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p PT")
    changed = False
    
    # البحث عن السبان الخاص بالتاريخ وتحديثه
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
    print("  🛒 Amazon Price Updater v2 — Oceanside Hair Salon")
    print("═" * 60)

    print("\n🔌 Connecting to Amazon Creators API...")
    api = AmazonCreatorsApi(
        credential_id=CREDENTIAL_ID,
        credential_secret=CREDENTIAL_SECRET,
        version=API_VERSION,
        tag=PARTNER_TAG,
        country=Country.US,
    )
    print("✅ Connected.\n")

    total_updated = 0

    for rel_path, asins in PAGES.items():
        # Optional single-page filter (e.g. --page neck)
        if page_filter and page_filter.lower() not in rel_path.lower():
            continue

        file_path = SITE_ROOT / rel_path
        print(f"{'─' * 60}")
        print(f"📄 Processing: {rel_path}")

        if not file_path.exists():
            print(f"   ⚠️  الملف غير موجود: {file_path}")
            continue

        # Deduplicate ASINs for this page before hitting the API
        unique_asins = list(dict.fromkeys(asins))
        print(f"   📦 Fetching {len(unique_asins)} ASIN(s) from Amazon API...")
        prices = fetch_prices(api, unique_asins)

        if not prices:
            print("   ⚠️  لم يتم الحصول على أي سعر لهذه الصفحة.")
            continue

        html = file_path.read_text(encoding="utf-8")
        original_html = html
        page_changed = False

        for asin in unique_asins:
            new_price = prices.get(asin)
            if not new_price:
                # ⚠️ هنا يتدخل نظام الحماية
                print(f"\n   ⚠️  API Failed for {asin} → Applying Fallback (Removing Price)")
                
                # 1. تحديث HTML ليضع كلمة Check Price بدل الرقم السعري القديم
                html, html_changed = update_html(html, asin, "Check Price")
                
                # 2. خطوة هامة للـ SEO: تحديث Schema لكي لا ترسل سعراً قديماً لجوجل
                html, schema_changed = update_schema(html, asin, "Out of Stock / Check Link") 
                
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
            elif prices.get(asin):
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