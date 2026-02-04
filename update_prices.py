import os
import re
# تغيير الاستدعاء ليتوافق مع التحديث الجديد
from amazon_paapi import AmazonApi 

ACCESS_KEY = os.environ.get('AMAZON_ACCESS_KEY')
SECRET_KEY = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'
HOST = 'webservices.amazon.com'
REGION = 'us-east-1'

try:
    # استخدام AmazonApi بدلاً من AmazonAPI
    amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, HOST, REGION)

    product_map = {
        'B0FGQQ9X2R': 'item-1', 
        'B0F1P5JXCD': 'item-2',
        'B0D4B2T8SR': 'item-3', 
        'B0CQ3TMHPM': 'item-4', 
        'B0CQKPM9V3': 'item-5',
        'B01539X5TA': 'upsell-item'
    }

file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'
with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print("Fetching data from Amazon Creators API...")
    
    asins = list(product_map.keys())
    # جلب البيانات
    items = amazon.get_items(item_ids=asins)

    for item in items:
        asin = item.asin
        base_id = product_map[asin]
        
        # التأكد من وجود عروض وسعر للمنتج لتجنب الأخطاء
        if item.offers and item.offers.listings:
            new_price = item.offers.listings[0].price.formatted_amount
            new_url = item.detail_page_url
            
            print(f"Updated {asin}: {new_price}")

            # تحديث السعر في HTML
            price_id = f"price-{base_id}" if "upsell" not in base_id else f"{base_id}-price"
            price_pattern = rf'(id="{price_id}"[^>]*>)(.*?)(</)'
            html_content = re.sub(price_pattern, f'\\1{new_price}\\3', html_content)

            # تحديث الرابط في HTML
            link_id = f"link-{base_id}" if "upsell" not in base_id else f"{base_id}-link"
            link_pattern = rf'(id="{link_id}"[^>]*href=")(.*?)(")'
            html_content = re.sub(link_pattern, f'\\1{new_url}\\3', html_content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✅ Success! Prices and Links updated.")

except Exception as e:
    print(f"❌ Error details: {e}")
