"""
╔══════════════════════════════════════════════════════════════╗
║         Amazon Price Updater — Oceanside Hair Salon          ║
║  يحدث السعر في HTML + Product Schema تلقائياً لكل الصفحات   ║
╚══════════════════════════════════════════════════════════════╝

التثبيت:
    pip install python-amazon-paapi beautifulsoup4 requests lxml

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
from copy import deepcopy
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from amazon_creatorsapi import AmazonCreatorsApi, Country

# ════════════════════════════════════════════════════════════════
#  ⚙️  إعدادات عامة
# ════════════════════════════════════════════════════════════════

CREDENTIAL_ID     = os.environ.get('AMAZON_ACCESS_KEY')
CREDENTIAL_SECRET = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG       = "oceansidehair-20"
API_VERSION       = "3.1"

# مجلد جذر موقعك (غيّره حسب مسار مشروعك)
SITE_ROOT = Path(".")   # أو مثلاً Path("C:/Users/mok24/mysite")

# ════════════════════════════════════════════════════════════════
#  🗺️  خريطة الصفحات: مسار الملف  →  [(ASIN, رابط الأفيليت)]
# ════════════════════════════════════════════════════════════════

PAGES = {
    # ── Sensitive Skin Electric Shavers ─────────────────────────
    "blog/best-electric-shavers-sensitive-skin-2025/index.html": [
        ("B0FGQQ9X2R", "https://amzn.to/3YhLpDJ"),
        ("B0F1P5JXCD", "https://amzn.to/3MNumXN"),
        ("B0D4B2T8SR", "https://amzn.to/4pXKkxa"),
        ("B0CQ3TMHPM", "https://amzn.to/3MV9I8c"),
        ("B0CQKPM9V3", "https://amzn.to/3MVR9Rd"),
        ("B01539X5TA", "https://amzn.to/3KT6YaJ"),  # رابط ثانٍ لنفس المنتج
    ],

    # ── Anti-Frizz Products ──────────────────────────────────────
    "blog/best-anti-frizz-products-oceanside/index.html": [
        ("B0DQTXH4S8", "https://amzn.to/3YQqPdI"),
        ("B073CWSQ51", "https://amzn.to/3Yl6TQ3"),
        ("B0B7QX7PPF", "https://amzn.to/4aGUfT4"),
        ("B0B532VM9Q", "https://amzn.to/4qumicL"),
        ("B08R4YZXTM", "https://amzn.to/4qCtkfR"),
        ("B07JQ67JHF", "https://amzn.to/49hmJAl"),
        ("B0DQTXH4S8", "https://amzn.to/49d65So"),
    ],

    # ── Shower Filters ───────────────────────────────────────────
    "blog/best-shower-filters-water-softeners-hard-water-hair/index.html": [
        ("B01MUBU0YC", "https://amzn.to/4jXpYBK"),
        ("B0DJDDQG26", "https://amzn.to/4bhsgJO"),
        ("B00BWIWYGC", "https://amzn.to/4rg4KSc"),
        ("B0D8RGF49F", "https://www.amazon.com/dp/B0D8RGF49F"),
        ("B010MR6T2I", "https://amzn.to/4afzT2q"),
        ("B075ZBH2RP", "https://amzn.to/4k80kdW"),
    ],

    # ── Hard Water Shampoos ──────────────────────────────────────
    "blog/shampoos-that-work-hard-water-hair/index.html": [
        ("B01N23J5C1", "https://www.amazon.com/dp/B01N23J5C1"),
        ("B01NAQI2AZ", "https://amzn.to/49LqXR3"),
        ("B0CT6TPGNJ", "https://amzn.to/4sPuG8L"),
        ("B08XB2BQC1", "https://amzn.to/4pT2jEb"),
        ("B0001Y74XG", "https://amzn.to/4r885Tm"),
        ("B07N7LCD2Z", "https://amzn.to/461Gx9S"),
        ("B000UPEDXU", "https://amzn.to/4qVLQzG"),
    ],

    # ── Best for Acne / Ingrown Hair ─────────────────────────────
    "blog/electric-shavers/best-for-acne-ingrown-hair/index.html": [
        ("B0BZDPFH45", "https://amzn.to/4lyI5Pd"),
        ("B07X342321", "https://amzn.to/4lBY67d"),
        ("B0FHDF5YQN", "https://amzn.to/4lGCXsE"),
        ("B000VVT94G", "https://amzn.to/415enbg"),
    ],

    # ── Best for Neck ────────────────────────────────────────────
    "blog/electric-shavers/best-for-neck/index.html": [
        ("B0BZDPFH45", "https://amzn.to/4rSv84s"),
        ("B0FGQQ9X2R", "https://amzn.to/4syYkyE"),
        ("B0F1PKHWNX", "https://amzn.to/4bwzHfZ"),
        ("B0D4B2T8SR", "https://amzn.to/4lMNMcw"),
        ("B07X342321", "https://amzn.to/4lBY67d"),
    ],
}

# ════════════════════════════════════════════════════════════════
#  🔧  دوال مساعدة
# ════════════════════════════════════════════════════════════════

def build_session() -> requests.Session:
    """
    ينشئ Session مُحسَّن مع:
    - Connection Pooling (إعادة استخدام TCP connections)
    - Retry تلقائي عند فشل الاتصال
    """
    session = requests.Session()

    # إعادة المحاولة 3 مرات عند أخطاء الشبكة أو 5xx
    retry = Retry(
        total=3,
        backoff_factor=0.5,          # ينتظر 0.5s ، 1s ، 2s بين المحاولات
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,          # عدد الـ connection pools
        pool_maxsize=20,              # أقصى اتصالات متزامنة لكل pool
    )
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session


def resolve_short_url(short_url: str, session: requests.Session) -> str:
    """
    يحوّل رابط amzn.to القصير إلى الرابط الكامل.
    يستخدم Session مشتركة لـ Connection Pooling.
    """
    if "amzn.to" not in short_url:
        return short_url
    try:
        r = session.get(short_url, allow_redirects=True, timeout=10)
        return r.url
    except Exception:
        return short_url


def bulk_resolve_urls(
    urls: list[str],
    session: requests.Session,
    max_workers: int = 8,
) -> dict[str, str]:
    """
    يحلّ قائمة روابط قصيرة بالتوازي (ThreadPoolExecutor).
    يعيد dict: {short_url: full_url}

    مثال: 10 روابط تُحلّ في ~1.5s بدلاً من ~5s بشكل تسلسلي.
    """
    results: dict[str, str] = {}
    # الروابط الطويلة لا تحتاج حلّاً — نضيفها مباشرة
    short_urls = [u for u in urls if "amzn.to" in u]
    for u in urls:
        if "amzn.to" not in u:
            results[u] = u

    if not short_urls:
        return results

    print(f"   🔗 Resolving {len(short_urls)} short URLs in parallel (workers={max_workers})...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(resolve_short_url, url, session): url
            for url in short_urls
        }
        for future in as_completed(future_to_url):
            original = future_to_url[future]
            try:
                results[original] = future.result()
            except Exception:
                results[original] = original   # fallback للرابط الأصلي

    return results


def fetch_prices(api: AmazonCreatorsApi, asins: list[str]) -> dict[str, str]:
    """
    يجلب السعر لقائمة ASIN (حتى 10 في طلب واحد).
    يعيد dict: {ASIN: "display_price"}
    """
    prices = {}

    # Amazon API تقبل حتى 10 ASINs في كل طلب
    for i in range(0, len(asins), 10):
        batch = list(dict.fromkeys(asins[i:i+10]))  # إزالة التكرار مع الحفاظ على الترتيب
        try:
            items = api.get_items(batch)
            for item in items:
                asin = item.asin
                price_str = _extract_price(item)
                if price_str:
                    prices[asin] = price_str
                    print(f"   ✅ {asin}: {price_str}")
                else:
                    print(f"   ⚠️  {asin}: السعر غير متاح (قد يكون نافد أو لم يعد مدرجاً)")
            if i + 10 < len(asins):
                time.sleep(1)  # تجنب rate limiting
        except Exception as e:
            print(f"   ❌ خطأ في جلب الـ batch {batch}: {e}")

    return prices


def _extract_price(item) -> str | None:
    """يستخرج السعر من item بكل الطرق الممكنة."""
    try:
        listings = item.offers_v2.listings
        if not listings:
            return None

        # نفضّل Buy Box Winner
        chosen = next((l for l in listings if getattr(l, "is_buy_box_winner", False)), None)
        if chosen is None:
            chosen = listings[0]

        # display_amount مباشرة
        try:
            val = chosen.price.money.display_amount
            if val:
                return val
        except AttributeError:
            pass

        # بناء السعر يدوياً
        try:
            amount   = chosen.price.money.amount
            currency = chosen.price.money.currency
            symbol   = "$" if currency == "USD" else f"{currency} "
            return f"{symbol}{float(amount):.2f}"
        except (AttributeError, TypeError, ValueError):
            pass

    except AttributeError:
        pass

    return None


def _price_to_numeric_str(price_str: str) -> str:
    """يحوّل "$29.99" أو "29.99" إلى "29.99" (نص رقمي نظيف)."""
    return re.sub(r"[^\d.]", "", price_str)


def _cast_price(numeric_str: str, original_value) -> float | str:
    """
    يحافظ على نوع السعر الأصلي في الـ Schema:
    - إذا كان الأصل float/int  → يعيد float  (e.g. 29.99)
    - إذا كان الأصل str        → يعيد str    (e.g. "29.99")

    هذا مهم لأن بعض validators يرفضون "339.99" (نص) بينما يتوقعون 339.99 (رقم).
    """
    try:
        f = float(numeric_str)
    except ValueError:
        return numeric_str   # fallback: أعد النص كما هو

    if isinstance(original_value, (int, float)):
        return f
    return numeric_str       # الأصل نص → نعيد نصاً


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث HTML
# ════════════════════════════════════════════════════════════════

def update_html(html_content: str, affiliate_url: str, new_price: str, new_affiliate_url: str) -> str:
    """
    يحدث السعر والرابط في HTML.

    الاستراتيجية:
    1. يبحث عن رابط أمازون بنفس href (القصير أو الطويل)
    2. يرتقي إلى .price-cta-area
    3. يحدث .price-tag بداخله
    4. يحدث href الرابط نفسه
    """
    soup = BeautifulSoup(html_content, "lxml")
    changed = False

    # نبحث عن كل روابط أمازون في الصفحة
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")

        # مطابقة الرابط القصير أو الطويل
        if href.rstrip("/") != affiliate_url.rstrip("/"):
            # محاولة مطابقة جزء ASIN في الرابط الطويل
            asin_in_href  = re.search(r"/dp/([A-Z0-9]{10})", href)
            asin_in_target = re.search(r"/dp/([A-Z0-9]{10})", affiliate_url)
            if not (asin_in_href and asin_in_target and
                    asin_in_href.group(1) == asin_in_target.group(1)):
                continue

        # ارتقاء إلى حاوية السعر
        price_area = a_tag.find_parent(class_="price-cta-area")
        if not price_area:
            continue

        price_tag = price_area.find(class_="price-tag")
        if not price_tag:
            continue

        # استخراج رقم السعر بدون $ وعملة
        numeric = _price_to_numeric_str(new_price)

        # إعادة بناء محتوى .price-tag مع الحفاظ على <small> و .sale-badge
        # نمط: <small>$</small>XX.XX
        small_tag = price_tag.find("small")
        sale_badge = price_tag.find(class_="sale-badge")

        # امسح المحتوى ثم أعد بناءه
        price_tag.clear()
        if small_tag:
            new_small = soup.new_tag("small")
            new_small.string = small_tag.get_text()
            price_tag.append(new_small)

        price_tag.append(numeric)

        if sale_badge:
            price_tag.append(" ")
            price_tag.append(deepcopy(sale_badge))

        # تحديث href الرابط بالـ affiliate الجديد
        a_tag["href"] = new_affiliate_url

        changed = True
        print(f"      📝 HTML: price-tag → {new_price}")

    return str(soup) if changed else html_content


# ════════════════════════════════════════════════════════════════
#  🛠️  تحديث Product Schema (JSON-LD)
# ════════════════════════════════════════════════════════════════

def update_schema(html_content: str, affiliate_url: str, new_price: str) -> str:
    """
    يحدث حقل "price" في JSON-LD schema داخل الـ HTML.
    يحافظ على نوع القيمة الأصلية (float أو str) لتوافق Google Rich Results.
    """
    soup = BeautifulSoup(html_content, "lxml")
    numeric_str = _price_to_numeric_str(new_price)
    changed = False

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        modified, data = _walk_schema(data, affiliate_url, numeric_str)
        if modified:
            script.string = json.dumps(data, indent=2, ensure_ascii=False)
            changed = True
            print(f"      📝 Schema: price → {numeric_str}")

    return str(soup) if changed else html_content


def _walk_schema(obj, affiliate_url: str, numeric_str: str):
    """
    يمشي بشكل تكراري عبر JSON-LD ويحدث حقل price.
    يحافظ على نوع القيمة الأصلية (float إذا كانت رقماً، str إذا كانت نصاً).
    """
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
            if sub_modified:
                modified = True

    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_modified, obj[idx] = _walk_schema(item, affiliate_url, numeric_str)
            if sub_modified:
                modified = True

    return modified, obj


def _urls_match(url1: str, url2: str) -> bool:
    """مطابقة مرنة بين رابطين (قصير أو طويل)."""
    if not url1 or not url2:
        return False
    if url1.rstrip("/") == url2.rstrip("/"):
        return True
    # مطابقة ASIN
    asin1 = re.search(r"/dp/([A-Z0-9]{10})", url1)
    asin2 = re.search(r"/dp/([A-Z0-9]{10})", url2)
    if asin1 and asin2:
        return asin1.group(1) == asin2.group(1)
    # مطابقة amzn.to slug
    slug1 = re.search(r"amzn\.to/(\w+)", url1)
    slug2 = re.search(r"amzn\.to/(\w+)", url2)
    if slug1 and slug2:
        return slug1.group(1) == slug2.group(1)
    return False


# ════════════════════════════════════════════════════════════════
#  🚀  الدالة الرئيسية
# ════════════════════════════════════════════════════════════════

def run(dry_run: bool = False, page_filter: str | None = None):
    print("═" * 60)
    print("  🛒 Amazon Price Updater — Oceanside Hair Salon")
    print("═" * 60)

    # ── تهيئة API ────────────────────────────────────────────────
    print("\n🔌 Connecting to Amazon Creators API...")
    api = AmazonCreatorsApi(
        credential_id     = CREDENTIAL_ID,
        credential_secret = CREDENTIAL_SECRET,
        version           = API_VERSION,
        tag               = PARTNER_TAG,
        country           = Country.US,
    )
    print("✅ Connected.")

    # ── Session مشتركة لكل الصفحات (Connection Pooling) ─────────
    http_session = build_session()
    print("✅ HTTP Session ready.\n")

    total_updated = 0

    for rel_path, products in PAGES.items():

        # فلترة حسب الـ --page إن وجد
        if page_filter and page_filter.lower() not in rel_path.lower():
            continue

        file_path = SITE_ROOT / rel_path
        print(f"{'─'*60}")
        print(f"📄 Checking: {rel_path}")

        if not file_path.exists():
            print(f"   ⚠️  الملف غير موجود: {file_path}")
            continue

        # ── جلب الأسعار من API ───────────────────────────────────
        asins = list(dict.fromkeys(asin for asin, _ in products))
        print(f"   📦 Fetching {len(asins)} ASINs from Amazon API...")
        prices = fetch_prices(api, asins)

        if not prices:
            print("   ⚠️  لم يتم الحصول على أي سعر لهذه الصفحة.")
            continue

        # ── قراءة HTML ───────────────────────────────────────────
        html = file_path.read_text(encoding="utf-8")
        original_html = html

        # ── حل الروابط القصيرة بالتوازي (Session مشتركة) ────────
        unique_urls = list(dict.fromkeys(url for _, url in products))
        resolved_urls = bulk_resolve_urls(unique_urls, http_session)

        # ── تطبيق التحديثات ──────────────────────────────────────
        for asin, aff_url in products:
            new_price = prices.get(asin)
            if not new_price:
                continue

            full_aff_url = resolved_urls.get(aff_url, aff_url)
            print(f"\n   🏷️  {asin} → {new_price}")

            # تحديث HTML
            html = update_html(html, aff_url, new_price, full_aff_url)

            # تحديث Schema
            html = update_schema(html, aff_url, new_price)

        # ── حفظ ─────────────────────────────────────────────────
        if html != original_html:
            if dry_run:
                print(f"\n   🔍 [DRY-RUN] التغييرات موجودة — لم يتم الحفظ.")
            else:
                file_path.write_text(html, encoding="utf-8")
                print(f"\n   💾 تم الحفظ: {rel_path}")
            total_updated += 1
        else:
            print(f"\n   ℹ️  لا تغييرات مطلوبة.")

    # ── إغلاق الـ Session ────────────────────────────────────────
    http_session.close()

    # ── ملخص ─────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"  🎉 {mode}اكتمل! {total_updated} صفحة تم تحديثها.")
    print("═" * 60)


# ════════════════════════════════════════════════════════════════
#  📌  Entry Point
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Price Updater")
    parser.add_argument("--dry-run",  action="store_true",
                        help="معاينة التغييرات بدون حفظ الملفات")
    parser.add_argument("--page",     type=str, default=None,
                        help="تحديث صفحة واحدة فقط (مثال: --page neck)")
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run, page_filter=args.page)
    except KeyboardInterrupt:
        print("\n⚠️  تم الإيقاف بواسطة المستخدم.")
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
        traceback.print_exc()
        exit(1)