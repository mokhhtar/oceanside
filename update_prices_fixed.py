import os
import re

try:
    from amazon.paapi import AmazonApi
except ImportError:
    print("❌ Please install: pip install python-amazon-paapi")
    exit(1)

# 1. إعداد الاتصال
ACCESS_KEY = os.environ.get('AMAZON_ACCESS_KEY')
SECRET_KEY = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'
COUNTRY = 'US'

# 2. مسار الملف
file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'

try:
    # استخدام المكتبة الصحيحة
    amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, COUNTRY)
    
    product_map = {
        'B0FGQQ9X2R': 'item-1', 
        'B0F1P5JXCD': 'item-2',
        'B0D4B2T8SR': 'item-3', 
        'B0CQ3TMHPM': 'item-4', 
        'B0CQKPM9V3': 'item-5',
        'B01539X5TA': 'upsell-item'
    }
    
    # قراءة الملف
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print(f"📄 Reading file: {file_path}")
    print(f"📦 Fetching data for {len(product_map)} products from Amazon API...")
    
    asins = list(product_map.keys())
    
    # استدعاء API
    items = amazon.get_items(asins)
    
    updated_count = 0
    
    for item in items.items:
        asin = item.asin
        base_id = product_map.get(asin)
        
        if not base_id:
            continue
        
        # الحصول على السعر والرابط
        new_price = None
        new_url = item.detail_page_url
        
        # محاولة الحصول على السعر
        try:
            if item.offers and item.offers.listings:
                listing = item.offers.listings[0]
                if listing.price:
                    new_price = listing.price.display_amount
        except:
            pass
        
        if not new_price or not new_url:
            print(f"\n⚠️  Incomplete data for ASIN: {asin} (skipping)")
            continue
        
        print(f"\n🔄 Processing ASIN: {asin} ({base_id})")
        print(f"   New Price: {new_price}")
        print(f"   New URL: {new_url[:50]}...")
        
        # --- تحديث السعر ---
        if "upsell" in base_id:
            # For upsell item: <span id="upsell-item-price">
            price_pattern = rf'(<span\s+id="{base_id}-price"[^>]*>)([^<]+)(</span>)'
        else:
            # For regular items: <div class="price-tag" id="item-X">
            price_pattern = rf'(<div\s+class="price-tag"\s+id="{base_id}"[^>]*>)([^<]+)(</div>)'
        
        before_price = html_content
        html_content = re.sub(price_pattern, rf'\1{new_price}\3', html_content, flags=re.DOTALL)
        
        if html_content != before_price:
            print(f"   ✅ Price updated successfully")
            updated_count += 1
        else:
            print(f"   ⚠️  Price pattern not found")
        
        # --- تحديث الرابط ---
        if "upsell" in base_id:
            link_id = f"{base_id}-link"
        else:
            link_id = f"link-{base_id}"
        
        # Pattern more flexible: any attributes before href
        link_pattern = rf'(<a\s+[^>]*id="{link_id}"[^>]*href=")([^"]+)(")'
        
        before_link = html_content
        html_content = re.sub(link_pattern, rf'\1{new_url}\3', html_content, flags=re.DOTALL)
        
        if html_content != before_link:
            print(f"   ✅ Link updated successfully")
        else:
            print(f"   ⚠️  Link pattern not found")
    
    # حفظ التعديلات
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n" + "="*60)
    print(f"✅ SUCCESS! Updated {updated_count} prices")
    print(f"📝 File saved: {file_path}")
    print("="*60)
    
except Exception as e:
    print(f"\n❌ ERROR occurred: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
