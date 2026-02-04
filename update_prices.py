import os
import re
import hashlib
import hmac
import base64
from datetime import datetime
from urllib.parse import quote
import requests
import json

# 1. إعداد بيانات الاتصال
ACCESS_KEY = os.environ.get('AMAZON_ACCESS_KEY')
SECRET_KEY = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG = 'oceansidehair-20'
HOST = 'webservices.amazon.com'
REGION = 'us-east-1'

# 2. مسار الملف
file_path = 'blog/best-electric-shavers-sensitive-skin-2025/index.html'

def sign(key, msg):
    """توقيع الرسالة باستخدام HMAC-SHA256"""
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    """إنشاء مفتاح التوقيع"""
    k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, 'aws4_request')
    return k_signing

def get_amazon_product_info(asins):
    """
    استدعاء Amazon PA API مباشرة باستخدام requests
    """
    
    # التاريخ والوقت
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')
    
    # إعداد الـ request
    method = 'POST'
    service = 'ProductAdvertisingAPI'
    canonical_uri = '/paapi5/getitems'
    
    # الـ payload (البيانات المرسلة)
    payload = {
        "ItemIds": asins,
        "PartnerTag": PARTNER_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.com",
        "Resources": [
            "ItemInfo.Title",
            "Offers.Listings.Price",
            "DetailPageURL"
        ]
    }
    
    payload_json = json.dumps(payload)
    
    # الـ headers
    canonical_headers = f'content-encoding:amz-1.0\ncontent-type:application/json; charset=utf-8\nhost:{HOST}\nx-amz-date:{amz_date}\nx-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems\n'
    signed_headers = 'content-encoding;content-type;host;x-amz-date;x-amz-target'
    
    # Hash الـ payload
    payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    # الـ canonical request
    canonical_request = f'{method}\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}'
    
    # الـ string للتوقيع
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f'{date_stamp}/{REGION}/{service}/aws4_request'
    string_to_sign = f'{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()}'
    
    # التوقيع
    signing_key = get_signature_key(SECRET_KEY, date_stamp, REGION, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    
    # الـ authorization header
    authorization_header = f'{algorithm} Credential={ACCESS_KEY}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
    
    # إرسال الـ request
    headers = {
        'content-encoding': 'amz-1.0',
        'content-type': 'application/json; charset=utf-8',
        'host': HOST,
        'x-amz-date': amz_date,
        'x-amz-target': 'com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems',
        'Authorization': authorization_header
    }
    
    url = f'https://{HOST}{canonical_uri}'
    
    response = requests.post(url, data=payload_json, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ API Error: {response.status_code}")
        print(f"Response: {response.text}")
        return None

try:
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
    api_response = get_amazon_product_info(asins)
    
    if not api_response:
        print("❌ Failed to get response from Amazon API")
        exit(1)
    
    updated_count = 0
    
    # معالجة النتائج
    if 'ItemsResult' in api_response and 'Items' in api_response['ItemsResult']:
        items = api_response['ItemsResult']['Items']
        
        for item in items:
            asin = item['ASIN']
            base_id = product_map.get(asin)
            
            if not base_id:
                continue
            
            # استخراج السعر
            new_price = None
            if 'Offers' in item and 'Listings' in item['Offers']:
                if len(item['Offers']['Listings']) > 0:
                    listing = item['Offers']['Listings'][0]
                    if 'Price' in listing and 'DisplayAmount' in listing['Price']:
                        new_price = listing['Price']['DisplayAmount']
            
            # استخراج الرابط
            new_url = item.get('DetailPageURL')
            
            if not new_price or not new_url:
                print(f"\n⚠️  Incomplete data for ASIN: {asin} (skipping)")
                continue
            
            print(f"\n🔄 Processing ASIN: {asin} ({base_id})")
            print(f"   New Price: {new_price}")
            print(f"   New URL: {new_url[:50]}...")
            
            # --- تحديث السعر ---
            if "upsell" in base_id:
                price_pattern = rf'(<span\s+id="{base_id}-price"[^>]*>)([^<]+)(</span>)'
            else:
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
