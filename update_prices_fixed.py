import os
import re
import traceback

from amazon_creatorsapi import AmazonCreatorsApi, Country

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
    print("🔌 Connecting to Amazon Creators API (Version 3.1)...")
    
    amazon = AmazonCreatorsApi(
        credential_id=CREDENTIAL_ID, 
        credential_secret=CREDENTIAL_SECRET, 
        tag=PARTNER_TAG, 
        country=Country.US,
        version="3.1"
    )
    
    asins = list(product_map.keys())
    
    # 🟢 السر هنا: يجب أن نحدد بدقة البيانات التي نحتاجها من سيرفرات أمازون
    request_resources = [
        "itemInfo.title",
        "offersV2.listings.price",
        "images.primary.large"
    ]
    
    print("📦 Fetching product data...")
    # تمرير الموارد (resources) مع الطلب
    items = amazon.get_items(asins, resources=request_resources)
    
    if not items:
        print("⚠️ No items returned from API.")
        exit(0)
        
    print(f"📄 Reading file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    updated_count = 0
    
    for item in items:
        if not hasattr(item, 'asin'):
            continue
            
        asin = item.asin
        base_id = product_map.get(asin)
        
        if not base_id: 
            continue
        
        new_price = None
        new_url = None
        
        # جلب الرابط
        if hasattr(item, 'detail_page_url') and item.detail_page_url:
            new_url = item.detail_page_url
            
        # 🟢 التعديل السحري هنا: استخدام offers_v2 بدلاً من offers
        if hasattr(item, 'offers_v2') and item.offers_v2 and hasattr(item.offers_v2, 'listings') and item.offers_v2.listings:
            listing = item.offers_v2.listings
            
            # حسب التحديث الجديد للمكتبة، السعر قد يكون مخزناً هنا
            if hasattr(listing.price, 'display_amount') and listing.price.display_amount:
                new_price = listing.price.display_amount
            elif hasattr(listing.price, 'money') and hasattr(listing.price.money, 'amount'):
                new_price = f"${listing.price.money.amount}" # إضافة رمز العملة في حال رجع كرقم فقط
                
        if not new_price or not new_url:
            print(f"⚠️  Missing price or URL for {asin} (Product might be out of stock)")
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