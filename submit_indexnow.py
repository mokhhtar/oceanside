"""
╔══════════════════════════════════════════════════════════════╗
║         Bing & Search Engines IndexNow Submitter             ║
║  يرسل جميع روابط sitemap.xml فورياً إلى Bing عبر IndexNow     ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Force standard output to UTF-8 to prevent UnicodeEncodeError on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SITE_HOST = "oceansidehairsalon.com"
KEY_FILE_NAME = "c7e481b29a304f5e8d9102c3b4a5f678.txt"
KEY = "c7e481b29a304f5e8d9102c3b4a5f678"
SITE_ROOT = Path(".")

def ensure_key_file():
    key_path = SITE_ROOT / KEY_FILE_NAME
    if not key_path.exists():
        key_path.write_text(KEY, encoding="utf-8")
        print(f"✅ Created IndexNow Key file: {KEY_FILE_NAME}")

def get_urls_from_sitemap():
    sitemap_path = SITE_ROOT / "sitemap.xml"
    if not sitemap_path.exists():
        print("❌ sitemap.xml not found!")
        return []
    
    content = sitemap_path.read_text(encoding="utf-8")
    urls = re.findall(r'<loc>(https://oceansidehairsalon\.com/[^<]*)</loc>', content)
    unique_urls = list(dict.fromkeys(urls))
    return unique_urls

def submit_to_indexnow(urls):
    if not urls:
        print("ℹ️ No URLs found to submit.")
        return

    endpoint = "https://api.indexnow.org/indexnow"
    payload = {
        "host": SITE_HOST,
        "key": KEY,
        "keyLocation": f"https://{SITE_HOST}/{KEY_FILE_NAME}",
        "urlList": urls
    }

    data_json = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_json,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )

    print(f"🚀 Submitting {len(urls)} URLs to IndexNow (Bing / Yandex)...")
    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            if status in (200, 202):
                print(f"🎉 Success! IndexNow returned HTTP status {status}. Bing notified successfully!")
            else:
                print(f"⚠️ IndexNow returned HTTP status: {status}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error submitting to IndexNow: {e.code} - {e.reason}")
        print(e.read().decode('utf-8', errors='ignore'))
    except Exception as exc:
        print(f"❌ Unexpected Error: {exc}")

if __name__ == "__main__":
    ensure_key_file()
    urls = get_urls_from_sitemap()
    print(f"📄 Found {len(urls)} URLs in sitemap.xml.")
    submit_to_indexnow(urls)
