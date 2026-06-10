"""
╔══════════════════════════════════════════════════════════════╗
║        Amazon Price Updater (APIFY FALLBACK)                 ║
║  يستخدم Apify Actor: XVDTQc4a7MDTqSTMJ لجلب الأسعار كخطة ب   ║
╚══════════════════════════════════════════════════════════════╝

التثبيت:
    pip install apify-client

الاستخدام:
    python update_prices_apify.py
    python update_prices_apify.py --dry-run
"""

import os
import re
import sys
import json
import time
import datetime
import argparse
import traceback
from pathlib import Path
from apify_client import ApifyClient

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

# يجب وضع مفتاح Apify في المتغيرات البيئية
APIFY_TOKEN = os.environ.get("APIFY_TOKEN") 
ACTOR_ID = "XVDTQc4a7MDTqSTMJ"

SITE_ROOT = Path(".")

# ════════════════════════════════════════════════════════════════
#  🗺️  خريطة الصفحات
# ════════════════════════════════════════════════════════════════

PAGES = {
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
#  🔧  دوال جلب الأسعار (باستخدام Apify)
# ════════════════════════════════════════════════════════════════

def fetch_prices_apify(asins: list[str]) -> dict[str, str]:
    if not APIFY_TOKEN:
        print(" ❌ تنبيه: لم يتم العثور على مفتاح APIFY_TOKEN!")
        return {}

    client = ApifyClient(APIFY_TOKEN)
    prices = {}
    
    # تحويل الـ ASINs إلى روابط منتجات لتغذية الـ Actor
    urls = [{"url": f"https://www.amazon.com/dp/{asin}"} for asin in asins]
    
    # إعدادات الـ Input الخاصة بـ Actor (XVDTQc4a7MDTqSTMJ)
    run_input = {
        "categoryUrls": urls,  # 🟢 التعديل هنا: تم تغيير الاسم بناءً على طلب Apify
        "maxItemsPerStartUrl": 1,
        "useCaptchaSolver": False
    }

    try:
        print(f"   🚀 جاري تشغيل Apify لجلب {len(asins)} منتجات. قد يستغرق هذا دقيقة...")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        # قراءة البيانات المستخرجة
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # استخراج ASIN من الرابط أو من البيانات
            item_url = item.get("url", "")
            asin_match = re.search(r'/dp/([A-Z0-9]{10})', item_url)
            asin = item.get("asin") or (asin_match.group(1) if asin_match else None)
            
            if not asin: continue

            # استخراج السعر (عادة Apify يعيده ككائن فيه value أو كنص مباشر)
            price_data = item.get("price")
            if isinstance(price_data, dict) and "value" in price_data:
                prices[asin] = str(price_data["value"])
            elif isinstance(price_data, (int, float)):
                prices[asin] = str(price_data)
            elif isinstance(price_data, str):
                prices[asin] = price_data
            
            if asin in prices:
                print(f"      ✅ Apify جلب: {asin} -> {prices[asin]}")

    except Exception as e:
        print(f"   ❌ حدث خطأ أثناء الاتصال بـ Apify: {e}")

    return prices

def _price_to_numeric_str(price_str: str) -> str:
    # إزالة أي نصوص أو رموز (مثل $) والإبقاء على الأرقام والنقطة فقط
    clean_str = re.sub(r"[^\d.]", "", str(price_str))
    
    try:
        # تحويل الرقم وتنسيقه ليحتوي دائماً على صفرين عشريين (مثال: 20 -> 20.00)
        return f"{float(clean_str):.2f}"
    except ValueError:
        # في حال وجود نص غير قابل للتحويل، نعيده كما هو
        return clean_str

# ════════════════════════════════════════════════════════════════
#  🛠️  دوال تحديث HTML و Schema و التاريخ
# ════════════════════════════════════════════════════════════════

def update_html(html_content: str, asin: str, new_price: str) -> str:
    numeric = _price_to_numeric_str(new_price) if new_price != "Check Price" else new_price
    changed = False

    pattern = re.compile(
        r'(<span\s+data-asin="' + re.escape(asin) + r'"[^>]*>)(.*?)(</span>)',
        re.IGNORECASE | re.DOTALL
    )
    
    def replacer(m: re.Match) -> str:
        nonlocal changed
        if m.group(2) != numeric:
            changed = True
            print(f"      📝 HTML [{asin}]: {m.group(2)} → {numeric}")
        return m.group(1) + numeric + m.group(3)

    return pattern.sub(replacer, html_content)


def update_schema(html_content: str, asin: str, new_price: str) -> str:
    numeric = _price_to_numeric_str(new_price)
    _SCRIPT_RE = re.compile(r'(<script\s+type="application/ld\+json"[^>]*>)(.*?)(</script>)', re.DOTALL | re.IGNORECASE)

    def script_replacer(m: re.Match) -> str:
        content = m.group(2)
        try:
            data = json.loads(content)
            modified, new_data = _walk_schema_update(data, asin, numeric)
            if modified:
                return m.group(1) + "\n" + json.dumps(new_data, indent=2, ensure_ascii=False) + "\n" + m.group(3)
        except json.JSONDecodeError: pass
        return m.group(0)
    return _SCRIPT_RE.sub(script_replacer, html_content)

def _walk_schema_update(obj, asin: str, numeric_str: str):
    modified = False
    if isinstance(obj, dict):
        
        # 🟢 1. إعادة بناء كائن العرض إذا تم حذفه مسبقاً
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
                
                # استرجاع رابط الأفيليت وإعادته للعرض
                if "url" in obj:
                    new_offer["url"] = obj["url"]
                    
                obj["offers"] = new_offer
                print(f"      ✨ Schema [{asin}]: Rebuilt 'offers' block with price, URL, and shipping/return policies")
                modified = True
                 
        # 2. التحديث العادي إذا كان كائن العرض موجوداً أصلاً
        if obj.get("@type") in ("Offer", "AggregateOffer") and obj.get("sku") == asin:
            if str(obj.get("price")) != numeric_str:
                print(f"      📝 Schema [{asin}]: Price updated to {numeric_str}")
                obj["price"] = numeric_str
                modified = True
            
            if obj.get("availability") == "https://schema.org/OutOfStock":
                obj["availability"] = "https://schema.org/InStock"
                print(f"      🔄 Schema [{asin}]: Marked back as InStock")
                modified = True

            # التأكد من وجود سياسات الشحن والإرجاع في العروض الحالية
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
            sub_modified, obj[key] = _walk_schema_update(val, asin, numeric_str)
            if sub_modified: modified = True
            
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_modified, obj[idx] = _walk_schema_update(item, asin, numeric_str)
            if sub_modified: modified = True
            
    return modified, obj

  
def update_offer_fallback_in_schema(html_content: str, asin: str) -> str:
    _SCRIPT_RE = re.compile(r'(<script\s+type="application/ld\+json"[^>]*>)(.*?)(</script>)', re.DOTALL | re.IGNORECASE)

    def script_replacer(m: re.Match) -> str:
        content = m.group(2)
        try:
            data = json.loads(content)
            modified, new_data = _walk_schema_fallback(data, asin)
            if modified:
                return m.group(1) + "\n" + json.dumps(new_data, indent=2, ensure_ascii=False) + "\n" + m.group(3)
        except json.JSONDecodeError: pass
        return m.group(0)
    return _SCRIPT_RE.sub(script_replacer, html_content)


def _walk_schema_fallback(obj, asin: str):
    modified = False
    if isinstance(obj, dict):
        if obj.get("@type") == "Product" and "offers" in obj:
            offer = obj["offers"]
            if isinstance(offer, dict) and offer.get("sku") == asin:
                
                # 🟢 خطوة الإنقاذ: نحفظ الـ ASIN والرابط داخل المنتج نفسه
                obj["sku"] = asin 
                if "url" in offer:
                    obj["url"] = offer["url"]
                
                # الآن يمكننا حذف كائن العرض بأمان تام
                del obj["offers"]
                print(f"      🗑️ Schema: Removed 'offers' but saved URL for {asin}")
                modified = True
                
        for key, val in list(obj.items()):
            sub_modified, obj[key] = _walk_schema_fallback(val, asin)
            if sub_modified: modified = True
            
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_modified, obj[idx] = _walk_schema_fallback(item, asin)
            if sub_modified: modified = True
            
    return modified, obj


def update_timestamp(html_content: str) -> str:
    now_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p PT")
    pattern = re.compile(r'(<span\s+id="price-timestamp"[^>]*>)(.*?)(</span>)', re.IGNORECASE | re.DOTALL)
    
    def replacer(m: re.Match) -> str:
        if m.group(2) != now_str:
            print(f"      🕒 Timestamp updated to: {now_str}")
        return m.group(1) + now_str + m.group(3)
    return pattern.sub(replacer, html_content)


# ════════════════════════════════════════════════════════════════
#  🚀  الدالة الرئيسية
# ════════════════════════════════════════════════════════════════

def run(dry_run: bool = False, page_filter: str | None = None):
    print("═" * 60)
    print("  🛒 Amazon Price Updater (Powered by APIFY)")
    print("═" * 60)

    total_updated = 0

    for rel_path, products in PAGES.items():
        if page_filter and page_filter.lower() not in rel_path.lower(): continue

        file_path = SITE_ROOT / rel_path
        print(f"\n📄 Checking: {rel_path}")

        if not file_path.exists():
            print(f"   ⚠️  الملف غير موجود: {file_path}")
            continue

        asins = list(dict.fromkeys(products))
        
        # جلب الأسعار من Apify
        prices = fetch_prices_apify(asins)

        html = file_path.read_text(encoding="utf-8")
        original_html = html

        for asin in products:
            new_price = prices.get(asin)
            
            if not new_price:
                # ⚠️ خطة الطوارئ في حال فشل Apify أيضاً في جلب السعر
                print(f"   ⚠️  لم يتم جلب السعر لـ {asin} → Applying Fallback")
                html = update_html(html, asin, "Check Price")
                
                # استدعاء الدالة الجديدة التي تحتفظ بالـ Offer بدل حذفه
                html = update_offer_fallback_in_schema(html, asin)
                continue

            print(f"\n   🏷️  {asin} → {new_price}")
            html = update_html(html, asin, new_price)
            html = update_schema(html, asin, new_price)

        # تحديث التاريخ
        html = update_timestamp(html)

        if html != original_html:
            if dry_run:
                print(f"\n   🔍 [DRY-RUN] التغييرات موجودة — لم يتم الحفظ.")
            else:
                file_path.write_text(html, encoding="utf-8")
                print(f"\n   💾 تم الحفظ: {rel_path}")
            total_updated += 1

    print(f"\n{'═'*60}")
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"  🎉 {mode}اكتمل! {total_updated} صفحة تم تحديثها.")
    print("═" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Price Updater - Apify")
    parser.add_argument("--dry-run",  action="store_true", help="معاينة التغييرات بدون حفظ")
    parser.add_argument("--page",     type=str, default=None, help="تحديث صفحة واحدة فقط")
    args = parser.parse_args()

    try:
        run(dry_run=args.dry_run, page_filter=args.page)
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
        traceback.print_exc()
        exit(1)