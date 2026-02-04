import os
import re
from amazon_paapi import AmazonAPI

# 1. إعداد الاتصال (يتم جلب المفاتيح من GitHub Secrets)
ACCESS_KEY = os.environ.get('AMAZON_ACCESS_KEY')
SECRET_KEY = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20' # المعرف الخاص بك
HOST = 'webservices.amazon.com'
REGION = 'us-east-1'

try:
    amazon = AmazonAPI(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, HOST, REGION)

    # 2. قائمة المنتجات والـ IDs الخاصة بها في ملف HTML
    # الهيكل: 'ASIN': 'ID_الأساسي'
    product_map = {
        'B0FGQQ9X2R': 'item-1', 
        'B0F1P5JXCD': 'item-2',
        'B0D4B2T8SR': 'item-3', 
        'B0CQ3TMHPM': 'item-4', 
        'B0CQKPM9V3': 'item-5',
        'B01539X5TA': 'upsell-item' # هذا للمنتج الإضافي
    }

    # 3. قراءة ملف HTML
    file_path = 'test.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 4. جلب البيانات من أمازون وتحديث الملف
    print("bring data from amazon")
    
    # نرسل كل الـ ASINs في طلب واحد لتوفير الوقت والـ Quota
    asins = list(product_map.keys())
    items = amazon.get_items(item_ids=asins)

    for item in items:
        asin = item.asin
        base_id = product_map[asin]
        
        # جلب السعر الجديد والرابط الجديد
        new_price = item.offers.listings[0].price.formatted_amount
        new_url = item.detail_page_url
        
        print(f"done for {asin}: price {new_price}")

        # أ. تحديث السعر (البحث عن العنصر الذي يحمل id="price-item-x")
        price_id = f"price-{base_id}" if "upsell" not in base_id else f"{base_id}-price"
        price_pattern = rf'(id="{price_id}"[^>]*>)(.*?)(</)'
        html_content = re.sub(price_pattern, f'\\1{new_price}\\3', html_content)

        # ب. تحديث الرابط (البحث عن العنصر الذي يحمل id="link-item-x")
        link_id = f"link-{base_id}" if "upsell" not in base_id else f"{base_id}-link"
        link_pattern = rf'(id="{link_id}"[^>]*href=")(.*?)(")'
        html_content = re.sub(link_pattern, f'\\1{new_url}\\3', html_content)

    # 5. حفظ الملف بعد التعديلات
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✅ تم تحديث جميع الأسعار والروابط بنجاح في ملف test.html")

except Exception as e:
    print(f"❌  error: {e}")
