import os
import re
from amazon_paapi import AmazonApi 

# 1. إعداد الاتصال
ACCESS_KEY = os.environ.get('AMAZON_ACCESS_KEY')
SECRET_KEY = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'
HOST = 'webservices.amazon.com'
REGION = 'us-east-1'

# 2. مسار الملف الجديد الخاص بك
file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'

try:
    amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, HOST, REGION)

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

    print(f"Fetching data from Amazon for: {file_path}")
    
    asins = list(product_map.keys())
    items = amazon.get_items(item_ids=asins)

for item in items:
        asin = item.asin
        base_id = product_map[asin]
        
        if item.offers and item.offers.listings:
            new_price = item.offers.listings[0].price.formatted_amount
            new_url = item.detail_page_url
            
            print(f"تم جلب بيانات {asin}: السعر {new_price}")

            # 1. تحديث السعر (استخدام base_id مباشرة كما هو في ملفك)
            price_id = base_id if "upsell" not in base_id else f"{base_id}-price"
            price_pattern = rf'(id="{price_id}"[^>]*>)(.*?)(</)'
            html_content = re.sub(price_pattern, f'\\1{new_price}\\3', html_content)

            # 2. تحديث الرابط (استخدام link- قبل base_id كما هو في ملفك)
            link_id = f"link-{base_id}" if "upsell" not in base_id else f"{base_id}-link"
            link_pattern = rf'(id="{link_id}"[^>]*href=")(.*?)(")'
            html_content = re.sub(link_pattern, f'\\1{new_url}\\3', html_content)

    # حفظ التعديلات في نفس المسار
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✅ Success! File updated successfully.")

except Exception as e:
    print(f"❌ Error occurred: {e}")
