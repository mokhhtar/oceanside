import os
import re
import traceback
from amazon_creatorsapi import AmazonCreatorsApi
from amazon_creatorsapi import Country

# إعداد المفاتيح (من بيئة GitHub)
CREDENTIAL_ID = os.environ.get('AMAZON_ACCESS_KEY') # المفتاح الطويل من Creators API
CREDENTIAL_SECRET = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'

file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'

try:
    print("🔌 Connecting to Amazon Creators API...")
    
    # --- التحديث للمطابقة 100% مع الوثيقة ---
    amazon = AmazonCreatorsApi(
        credential_id=CREDENTIAL_ID, 
        credential_secret=CREDENTIAL_SECRET, 
        tag=PARTNER_TAG, 
        country=Country.US,
        version="2.2"  # تمت إضافة الإصدار كما في النص الذي أرسلته
    )
    
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
    items = amazon.get_items(asins)
    
    updated_count = 0
    
    for item in items:
        asin = item.asin
        base_id = product_map.get(asin)
        
        if not base_id: continue
        
        new_price = None
        new_url = item.detail_page_url
        
        # محاولة استخراج السعر
        if item.offers and item.offers.listings:
            new_price = item.offers.listings[0].price.formatted_amount
        
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
        html_content = re.sub(price_pattern, rf'\1{new_price}\3', html_content, flags=re.DOTALL)
        
        # --- تحديث الرابط ---
        link_id = f"{base_id}-link" if "upsell" in base_id else f"link-{base_id}"
        link_pattern = rf'(<a\s+[^>]*id="{link_id}"[^>]*href=")([^"]+)(")'
        
        html_content = re.sub(link_pattern, rf'\1{new_url}\3', html_content, flags=re.DOTALL)
        
        if html_content != before_update:
            updated_count += 1

    if updated_count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\n🎉 SUCCESS! Updated {updated_count} products.")
    else:
        print("\nℹ️  No changes needed.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    traceback.print_exc()
    exit(1)
