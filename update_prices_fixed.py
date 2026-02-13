import os
import re
import traceback

# التحديث بناءً على تحذير المكتبة لتعمل مع Creators API
from amazon_creatorsapi import AmazonCreatorsApi
from amazon_creatorsapi import Country

CREDENTIAL_ID = os.environ.get('AMAZON_ACCESS_KEY')
CREDENTIAL_SECRET = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'

file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'

product_map = {
    'B0FGQQ9X2R': 'item-1', 
    'B0F1P5JXCD': 'item-2',
    'B0D4B2T8SR': 'item-3', 
    'B0CQ3TMHPM': 'item-4', 
    'B0CQKPM9V3': 'item-5',
    'B01539X5TA': 'upsell-item'
}

try:
    print("🔌 Connecting to Amazon Creators API...")
    
    # استخدام كلاس Creators API مع إضافة النسخة كما يتطلب التحديث
    amazon = AmazonCreatorsApi(
        credential_id=CREDENTIAL_ID, 
        credential_secret=CREDENTIAL_SECRET, 
        tag=PARTNER_TAG, 
        country=Country.US,
        version="2.1"
    )
    
    asins = list(product_map.keys())
    
    print("📦 Fetching product data...")
    items = amazon.get_items(asins)
    
    print(f"📄 Reading file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    updated_count = 0
    
    for item in items:
        asin = item.asin
        base_id = product_map.get(asin)
        
        if not base_id: continue
        
        new_price = None
        new_url = item.detail_page_url
        
        # استخراج السعر باستخدام هيكلية المكتبة المحدثة
        if item.offers and item.offers.listings:
            new_price = item.offers.listings[0].price.display_amount
            
        if not new_price:
            print(f"⚠️  No price found for {asin}")
            continue
            
        print(f"✅ Found {asin}: {new_price}")
        
        # --- تحديث السعر ---
        if "upsell" in base_id:
            price_pattern = rf'(<span\s+id="{base_id}-price"[^>]*>)([^<]+)(</span>)'
        else:
            price_pattern = rf'(<div\s+class="price-tag"\s+id="{base_id}"[^>]*>)([^<]+)(</div>)'
        
        before_update = html_content
        html_content = re.sub(price_pattern, rf'\g<1>{new_price}\g<3>', html_content, flags=re.DOTALL)
        
        # --- تحديث الرابط ---
        link_id = f"{base_id}-link" if "upsell" in base_id else f"link-{base_id}"
        link_pattern = rf'(<a\s+[^>]*id="{link_id}"[^>]*href=")([^"]+)(")'
        html_content = re.sub(link_pattern, rf'\g<1>{new_url}\g<3>', html_content, flags=re.DOTALL)
        
        if html_content != before_update:
            updated_count += 1

    if updated_count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\n🎉 SUCCESS! Updated {updated_count} products.")
    else:
        print("\nℹ️  No changes needed in HTML.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    traceback.print_exc()
    exit(1)
