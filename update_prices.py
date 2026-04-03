"""
╔══════════════════════════════════════════════════════════════╗
║         Amazon Price Updater — Oceanside Hair Salon          ║
║  يحدث السعر في HTML + Product Schema تلقائياً لكل الصفحات   ║
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
#  🗺️  خريطة الصفحات: مسار الملف  →  [(ASIN, رابط الأفيليت)]
# ════════════════════════════════════════════════════════════════

PAGES = {
    "blog/best-electric-shavers-sensitive-skin-2025/index.html": [
        ("B07PW4MTHV", "https://amzn.to/3YhLpDJ"),
        ("B0F1P5JXCD", "https://amzn.to/3MNumXN"),
        ("B0D4B2T8SR", "https://amzn.to/4pXKkxa"),
        ("B0CQ3TMHPM", "https://amzn.to/3MV9I8c"),
        ("B0CQKPM9V3", "https://amzn.to/3MVR9Rd"),
        ("B01539X5TA", "https://amzn.to/3KT6YaJ"),  
    ],
    "blog/best-anti-frizz-products-oceanside/index.html": [
        ("B0DQTXH4S8", "https://amzn.to/3YQqPdI"),
        ("B073CWSQ51", "https://amzn.to/3Yl6TQ3"),
        ("B0B7QX7PPF", "https://amzn.to/4aGUfT4"),
        ("B0B532VM9Q", "https://amzn.to/4qumicL"),
        ("B08R4YZXTM", "https://amzn.to/4qCtkfR"),
        ("B07JQ67JHF", "https://amzn.to/49hmJAl"),
        ("B0DQTXH4S8", "https://amzn.to/49d65So"),
    ],
    "blog/best-shower-filters-water-softeners-hard-water-hair/index.html": [
        ("B01MUBU0YC", "https://amzn.to/4jXpYBK"),
        ("B0DJDDQG26", "https://amzn.to/4bhsgJO"),
        ("B00BWIWYGC", "https://amzn.to/4rg4KSc"),
        ("B0D8RGF49F", "https://www.amazon.com/dp/B0D8RGF49F"),
        ("B010MR6T2I", "https://amzn.to/4afzT2q"),
        ("B075ZBH2RP", "https://amzn.to/4k80kdW"),
    ],
    "blog/shampoos-that-work-hard-water-hair/index.html": [
        ("B01N23J5C1", "https://www.amazon.com/dp/B01N23J5C1"),
        ("B01NAQI2AZ", "https://amzn.to/49LqXR3"),
        ("B0CT6TPGNJ", "https://amzn.to/4sPuG8L"),
        ("B08XB2BQC1", "https://amzn.to/4pT2jEb"),
        ("B0001Y74XG", "https://amzn.to/4r885Tm"),
        ("B07N7LCD2Z", "https://amzn.to/461Gx9S"),
        ("B000UPEDXU", "https://amzn.to/4qVLQzG"),
    ],
    "blog/electric-shavers/best-for-acne-ingrown-hair/index.html": [
        ("B0BZDPFH45", "https://amzn.to/4lyI5Pd"),
        ("B07X342321", "https://amzn.to/4lBY67d"),
        ("B0FHDF5YQN", "https://amzn.to/4lGCXsE"),
        ("B000VVT94G", "https://amzn.to/415enbg"),
    ],
    "blog/electric-shavers/best-for-neck/index.html": [
        ("B0BZDPFH45", "https://amzn.to/4rSv84s"),
        ("B0FGQQ9X2R", "https://amzn.to/4syYkyE"),
        ("B0F1PKHWNX", "https://amzn.to/4bwzHfZ"),
        ("B0D4B2T8SR", "https://amzn.to/4lMNMcw"),
        ("B07X342321", "https://amzn.to/4lBY67d"),
    ],
}

# ════════════════════════════════════════════════════════════════
#  🔧  دوال جلب الأسعار
# ════════════════════════════════════════════════════════════════

def fetch_prices(api: AmazonCreatorsApi, asins: list[str]) -> dict[str, str]:
    prices = {}
    for i in range(0, len(asins), 10):
        batch = list(dict.fromkeys(asins[i:i+10]))
        try:
            items = api.get_items(batch)
            for item in items:
                asin = item.asin
                price_str = _extract_price(item)
                if price_str:
                    prices[asin] = price_str
                    print(f"   ✅ {asin}: {price_str}")
                else:
                    print(f"   ⚠️  {asin}: السعر غير متاح")
            if i + 10 < len(asins):
                time.sleep(1)
        except Exception as e:
            print(f"   ❌ خطأ في جلب الـ batch {batch}: {e}")
    return prices

def _extract_price(item) -> str | None:
    try:
        listings = item.offers_v2.listings
        if not listings: return None
        chosen = next((l for l in listings if getattr(l, "is_buy_box_winner", False)), None)
        
        # 🟢 التعديل هنا: إضافة لاختيار العنصر الأول إذا كان chosen فارغاً
        if chosen is None: chosen = listings 
        
        try:
            val = chosen.price.money.display_amount
            if val: return val
        except AttributeError: pass
        try:
            amount   = chosen.price.money.amount
            currency = chosen.price.money.currency
            symbol   = "$" if currency == "USD" else f"{currency} "
            return f"{symbol}{float(amount):.2f}"
        except (AttributeError, TypeError, ValueError): pass
    except AttributeError: pass
    return None

def _price_to_numeric_str(price_str: str) -> str:
    return re.sub(r"[^\d.]", "", price_str)

def _cast_price(numeric_str: str, original_value) -> float | str:
    try: f = float(numeric_str)
    except ValueError: return numeric_str
    if isinstance(original_value, (int, float)): return f
    return numeric_str

# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث HTML — حماية ضد التداخل (Anti-Cascade)
# ════════════════════════════════════════════════════════════════

def update_html(html_content: str, affiliate_url: str, new_price: str) -> str:
    numeric = _price_to_numeric_str(new_price)
    slug = affiliate_url.rstrip("/").split("/")[-1]
    changed = False

    # --- الخطة أ: السعر موجود "داخل" الرابط (مثل Nivea Upsell) ---
    # يبحث عن href، ثم يبحث داخله عن price-tag
    pattern_inside = re.compile(
        r'(href="https://amzn\.to/' + re.escape(slug) + r'"[^>]*>.*?(?:id|class)="price-tag"[^>]*>.*?(?:</small>|\$)\s*)([\d.,]+)',
        re.DOTALL | re.IGNORECASE
    )
    
    def replacer_inside(m: re.Match) -> str:
        nonlocal changed
        if m.group(2) != numeric:
            changed = True
            print(f"      📝 HTML [Upsell]: {m.group(2)} → {numeric}")
        return m.group(1) + numeric

    new_html = pattern_inside.sub(replacer_inside, html_content)
    
    # إذا تم التحديث بنجاح، نخرج من الدالة (لا حاجة للخطة ب)
    if changed:
        return new_html

    # --- الخطة ب: السعر موجود "قبل" الرابط (المنتجات العادية) ---
    # الحاجز السحري: (?:(?!(?:class|id)="price-tag").)*?
    # هذا الحاجز يمنع الكود من القفز من منتج إلى آخر مهما حدث!
    pattern_before = re.compile(
        r'((?:class|id)="price-tag"[^>]*>.*?(?:</small>|\$)\s*)([\d.,]+)((?:(?!(?:class|id)="price-tag").)*?href="https://amzn\.to/' + re.escape(slug) + r'")',
        re.DOTALL | re.IGNORECASE
    )

    def replacer_before(m: re.Match) -> str:
        nonlocal changed
        if m.group(2) != numeric:
            changed = True
            print(f"      📝 HTML [Regular]: {m.group(2)} → {numeric}")
        return m.group(1) + numeric + m.group(3)

    new_html = pattern_before.sub(replacer_before, html_content)
    return new_html


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث Schema (JSON-LD)
# ════════════════════════════════════════════════════════════════

def update_schema(html_content: str, affiliate_url: str, new_price: str) -> str:
    numeric = _price_to_numeric_str(new_price)
    slug = affiliate_url.rstrip("/").split("/")[-1]
    
    _SCRIPT_RE = re.compile(
        r'(<script\s+type="application/ld\+json"[^>]*>)(.*?)(</script>)',
        re.DOTALL | re.IGNORECASE
    )

    def script_replacer(m: re.Match) -> str:
        content = m.group(2)
        
        # الحاجز: (?:(?!"url").)*? يمنع الكود من تغيير سعر منتج آخر في الشرح
        offer_re = re.compile(
            r'("url":\s*"https://amzn\.to/' + re.escape(slug) + r'/?(?:(?!"url").)*?"price":\s*")([^"]+)(")',
            re.DOTALL | re.IGNORECASE
        )

        def price_replacer(pm: re.Match) -> str:
            if pm.group(2) != numeric:
                print(f"      📝 Schema: {pm.group(2)} → {numeric}")
            return pm.group(1) + numeric + pm.group(3)

        updated = offer_re.sub(price_replacer, content)
        return m.group(1) + updated + m.group(3)

    return _SCRIPT_RE.sub(script_replacer, html_content)

def _walk_schema(obj, affiliate_url: str, numeric_str: str):
    modified = False
    if isinstance(obj, dict):
        obj_url  = obj.get("url", "") or obj.get("@id", "")
        is_offer = obj.get("@type") in ("Offer", "AggregateOffer")

        if is_offer and _urls_match(obj_url, affiliate_url):
            if "price" in obj:
                original_value = obj["price"]
                obj["price"]   = _cast_price(numeric_str, original_value)
                modified = True

        for key, val in obj.items():
            sub_modified, obj[key] = _walk_schema(val, affiliate_url, numeric_str)
            if sub_modified: modified = True

    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_modified, obj[idx] = _walk_schema(item, affiliate_url, numeric_str)
            if sub_modified: modified = True

    return modified, obj

def _urls_match(url1: str, url2: str) -> bool:
    if not url1 or not url2: return False
    if url1.rstrip("/") == url2.rstrip("/"): return True
    asin1 = re.search(r"/dp/([A-Z0-9]{10})", url1)
    asin2 = re.search(r"/dp/([A-Z0-9]{10})", url2)
    if asin1 and asin2: return asin1.group(1) == asin2.group(1)
    slug1 = re.search(r"amzn\.to/(\w+)", url1)
    slug2 = re.search(r"amzn\.to/(\w+)", url2)
    if slug1 and slug2: return slug1.group(1) == slug2.group(1)
    return False

# ════════════════════════════════════════════════════════════════
#  🚀  الدالة الرئيسية
# ════════════════════════════════════════════════════════════════

def run(dry_run: bool = False, page_filter: str | None = None):
    print("═" * 60)
    print("  🛒 Amazon Price Updater — Oceanside Hair Salon")
    print("═" * 60)

    print("\n🔌 Connecting to Amazon Creators API...")
    api = AmazonCreatorsApi(
        credential_id     = CREDENTIAL_ID,
        credential_secret = CREDENTIAL_SECRET,
        version           = API_VERSION,
        tag               = PARTNER_TAG,
        country           = Country.US,
    )
    print("✅ Connected.\n")

    total_updated = 0

    for rel_path, products in PAGES.items():
        if page_filter and page_filter.lower() not in rel_path.lower():
            continue

        file_path = SITE_ROOT / rel_path
        print(f"{'─'*60}")
        print(f"📄 Checking: {rel_path}")

        if not file_path.exists():
            print(f"   ⚠️  الملف غير موجود: {file_path}")
            continue

        asins = list(dict.fromkeys(asin for asin, _ in products))
        print(f"   📦 Fetching {len(asins)} ASINs from Amazon API...")
        prices = fetch_prices(api, asins)

        if not prices:
            print("   ⚠️  لم يتم الحصول على أي سعر لهذه الصفحة.")
            continue

        html = file_path.read_text(encoding="utf-8")
        original_html = html

        for asin, aff_url in products:
            new_price = prices.get(asin)
            if not new_price:
                continue

            print(f"\n   🏷️  {asin} → {new_price}")
            html = update_html(html, aff_url, new_price)
            html = update_schema(html, aff_url, new_price)

        if html != original_html:
            if dry_run:
                print(f"\n   🔍 [DRY-RUN] التغييرات موجودة — لم يتم الحفظ.")
            else:
                file_path.write_text(html, encoding="utf-8")
                print(f"\n   💾 تم الحفظ: {rel_path}")
            total_updated += 1
        else:
            print(f"\n   ℹ️  لا تغييرات مطلوبة.")

    print(f"\n{'═'*60}")
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"  🎉 {mode}اكتمل! {total_updated} صفحة تم تحديثها.")
    print("═" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Price Updater")
    parser.add_argument("--dry-run",  action="store_true", help="معاينة التغييرات بدون حفظ الملفات")
    parser.add_argument("--page",     type=str, default=None, help="تحديث صفحة واحدة فقط (مثال: --page neck)")
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run, page_filter=args.page)
    except KeyboardInterrupt:
        print("\n⚠️  تم الإيقاف بواسطة المستخدم.")
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
        traceback.print_exc()
        exit(1)