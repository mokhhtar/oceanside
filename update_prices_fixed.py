import os
import re
import json
import traceback
import requests

# 1. إعداد المتغيرات (من بيئة GitHub)
CREDENTIAL_ID = os.environ.get('AMAZON_ACCESS_KEY')
CREDENTIAL_SECRET = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'
# نقطة النهاية الرسمية للولايات المتحدة
ENDPOINT = "https://api.amazon.com/creators/api/v2/items" 

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
    
    # 2. إعداد الهيدرز (Headers) المطلوبة للاتصال
    # لاحظ أن الواجهة الجديدة تعتمد على إرسال المفاتيح في الهيدر بطريقة محددة
    headers = {
        "Content-Type": "application/json",
        "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems", # قد تختلف نقطة النهاية، سنستخدم طريقة الـ OAuth/Direct
        "X-Creator-Credential-Id": CREDENTIAL_ID,
        "X-Creator-Credential-Secret": CREDENTIAL_SECRET
    }
    
    # قائمة المنتجات (ASINs)
    asins = list(product_map.keys())

    # 3. إعداد الحمولة (Payload) حسب توثيق أمازون
    # نطلب معلومات السعر (Offers) ومعلومات المنتج (ItemInfo)
    payload = {
        "ItemIds": asins,
        "Resources": [
            "Offers.Listings.Price",
            "ItemInfo.Title",
            "Images.Primary.Large"
        ],
        "PartnerTag": PARTNER_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.com"
    }

    # 4. إرسال الطلب (POST Request)
    response = requests.post(
        ENDPOINT,
        headers=headers,
        json=payload
    )

    # التحقق من نجاح الطلب
    if response.status_code != 200:
        print(f"❌ API Error: Status {response.status_code}")
        print(response.text)
        exit(1)
        
    data = response.json()
    
    # قراءة ملف الـ HTML
    print(f"📄 Reading file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    updated_count = 0
    
    # 5. معالجة الاستجابة
    # يجب التأكد من بنية الـ JSON العائدة من أمازون، نفترض البنية القياسية لـ PA-API 5.0/Creators
    items = data.get('ItemsResult', {}).get('Items', [])
    
    for item in items:
        asin = item.get('ASIN')
        base_id = product_map.get(asin)
        
        if not base_id: continue
        
        new_price = None
        new_url = item.get('DetailPageURL')
        
        # استخراج السعر من البنية (تأكد من توافق هذا مع الاستجابة الفعلية)
        try:
            offers = item.get('Offers', {}).get('Listings', [])
            if offers:
                new_price = offers[0].get('Price', {}).get('DisplayAmount')
        except Exception as e:
            print(f"⚠️ Error parsing price for {asin}: {e}")
            
        if not new_price:
            print(f"⚠️  No price found for {asin}")
            continue
            
        print(f"✅ Found {asin}: {new_price}")
        
        # --- تحديث السعر في الـ HTML ---
        if "upsell" in base_id:
            price_pattern = rf'(<span\s+id="{base_id}-price"[^>]*>)([^<]+)(</span>)'
        else:
            price_pattern = rf'(<div\s+class="price-tag"\s+id="{base_id}"[^>]*>)([^<]+)(</div>)'
        
        before_update = html_content
        html_content = re.sub(price_pattern, rf'\g<1>{new_price}\g<3>', html_content, flags=re.DOTALL)
        
        # --- تحديث الرابط في الـ HTML ---
        if new_url:
            link_id = f"{base_id}-link" if "upsell" in base_id else f"link-{base_id}"
            link_pattern = rf'(<a\s+[^>]*id="{link_id}"[^>]*href=")([^"]+)(")'
            html_content = re.sub(link_pattern, rf'\g<1>{new_url}\g<3>', html_content, flags=re.DOTALL)
        
        if html_content != before_update:
            updated_count += 1

    # حفظ الملف إذا تم التحديث
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
