import os
import re
import traceback

from amazon_creatorsapi import AmazonCreatorsApi, Country

CREDENTIAL_ID     = os.environ.get('AMAZON_ACCESS_KEY')
CREDENTIAL_SECRET = os.environ.get('AMAZON_SECRET_KEY')
PARTNER_TAG       = 'oceansidehair-20'

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
        credential_id     = CREDENTIAL_ID,
        credential_secret = CREDENTIAL_SECRET,
        tag               = PARTNER_TAG,
        country           = Country.US,
        version           = "3.1"
    )

    asins = list(product_map.keys())

    print("📦 Fetching product data...")
    # بدون resources = يجلب كل شيء (أكثر أماناً)
    products_list = amazon.get_items(asins)

    if not products_list:
        print("⚠️ No items returned from API.")
        exit(0)

    print(f"📄 Reading file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    updated_count = 0

    for item in products_list:
        if not hasattr(item, 'asin'):
            continue

        asin     = item.asin
        base_id  = product_map.get(asin)

        if not base_id:
            continue

        new_price = None
        new_url   = None

        # ── استخراج الرابط ────────────────────────────────────
        if hasattr(item, 'detail_page_url') and item.detail_page_url:
            new_url = item.detail_page_url

        # ── استخراج السعر من offers_v2 (الصحيح) ──────────────
        try:
            listings = item.offers_v2.listings   # هذه LIST

            # نبحث أولاً عن Buy Box Winner، وإلا نأخذ أول عرض
            chosen = None
            for lst in listings:
                if getattr(lst, 'is_buy_box_winner', False):
                    chosen = lst
                    break
            if chosen is None and listings:
                chosen = listings[0]

            if chosen:
                # محاولة display_amount مباشرةً
                try:
                    new_price = chosen.price.money.display_amount
                except AttributeError:
                    pass

                # احتياطي: نبني السعر من amount + currency
                if not new_price:
                    try:
                        amount   = chosen.price.money.amount
                        currency = chosen.price.money.currency
                        symbol   = "$" if currency == "USD" else currency + " "
                        new_price = f"{symbol}{amount:.2f}"
                    except (AttributeError, TypeError):
                        pass

        except AttributeError:
            pass

        # ── تحقق وأبلغ ───────────────────────────────────────
        if not new_price:
            print(f"⚠️  No price found for {asin} — possibly out of stock")
        if not new_url:
            print(f"⚠️  No URL found for {asin}")

        if not new_price or not new_url:
            continue

        print(f"✅ {asin} → {new_price}")

        before_update = html_content

        # ── تحديث السعر في HTML ───────────────────────────────
        if "upsell" in base_id:
            price_pattern = rf'(<span\s+id="{base_id}-price"[^>]*>)([^<]+)(</span>)'
        else:
            price_pattern = rf'(<div\s+class="price-tag"\s+id="{base_id}"[^>]*>)([^<]+)(</div>)'

        html_content = re.sub(
            price_pattern,
            rf'\g<1>{new_price}\g<3>',
            html_content,
            flags=re.DOTALL
        )

        # ── تحديث الرابط في HTML ──────────────────────────────
        link_id      = f"{base_id}-link" if "upsell" in base_id else f"link-{base_id}"
        link_pattern = rf'(<a\s+[^>]*id="{link_id}"[^>]*href=")([^"]+)(")'

        html_content = re.sub(
            link_pattern,
            rf'\g<1>{new_url}\g<3>',
            html_content,
            flags=re.DOTALL
        )

        if html_content != before_update:
            updated_count += 1

    # ── حفظ الملف ─────────────────────────────────────────────
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