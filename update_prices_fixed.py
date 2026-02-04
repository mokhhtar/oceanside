import os
import re
import traceback

try:
    # الإصلاح 1: تعديل طريقة الاستيراد
    from amazon_paapi import AmazonApi
except ImportError:
    print("❌ Please install: pip install python-amazon-paapi")
    exit(1)

# 1. إعداد الاتصال
ACCESS_KEY = os.environ.get('AMAZON_ACCESS_KEY')
SECRET_KEY = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'
# الإصلاح 2: إضافة الـ Host والـ Region الصحيحين لأمازون أمريكا
HOST = 'webservices.amazon.com'
REGION = 'us-east-1'

# 2. مسار الملف
file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'

try:
    # الإصلاح 3: تمرير المعاملات بالترتيب الذي تقبله المكتبة
    amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, HOST, REGION)
    
    product_map = {
        'B0FGQQ9X2R': 'item-1', 
        'B0F1P5JXCD': 'item-2',
        'B0D4B2T8SR': 'item-3', 
        'B0CQ3TMHPM': 'item-4', 
        'B0CQKPM9V3': 'item-5',
        'B01539X5TA': 'upsell-item'
    }
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print(f"📄 Reading file: {file_path}")
    asins = list(product_map.keys())
    
    # طلب البيانات
    items_response = amazon.get_items(item_ids=asins)
    
    updated_count = 0
    
    # الوصول الصحيح لنتائج البحث
    for item in items_response:
        asin = item.asin
        base_id = product_map.get(asin)
        
        if not base_id: continue
        
        new_price = None
        new_url = item.detail_page_url
        
        # الإصلاح 4: استخدام formatted_amount
        try:
            if item.offers and item.offers.listings:
                listing = item.offers.listings[0]
                if listing.price:
                    new_price = listing.price.formatted_amount
        except: pass
        
        if not new_price or not new_url:
            print(f"⚠️  Incomplete data for ASIN: {asin} (skipping)")
            continue
        
        print(f"\n🔄 Processing ASIN: {asin} ({base_id})")
        
        # --- تحديث السعر ---
        if "upsell" in base_id:
            price_pattern = rf'(<span\s+id="{base_id}-price"[^>]*>)([^<]+)(</span>)'
        else:
            price_pattern = rf'(<div\s+class="price-tag"\s+id="{base_id}"[^>]*>)([^<]+)(</div>)'
        
        html_content = re.sub(price_pattern, rf'\1{new_price}\3', html_content, flags=re.DOTALL)
        
        # --- تحديث الرابط ---
        link_id = f"{base_id}-link" if "upsell" in base_id else f"link-{base_id}"
        link_pattern = rf'(<a\s+[^>]*id="{link_id}"[^>]*href=")([^"]+)(")'
        
        before_update = html_content
        html_content = re.sub(link_pattern, rf'\1{new_url}\3', html_content, flags=re.DOTALL)
        
        if html_content != before_update:
            updated_count += 1
            print(f"   ✅ Updated: {new_price}")

    # حفظ الملف
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✅ SUCCESS! Total updates: {updated_count}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    traceback.print_exc()
    exit(1)
