import os
import json
import re
from bs4 import BeautifulSoup

def update_schema_in_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all JSON-LD blocks
    script_pattern = re.compile(r'(<script[^>]*type=["\']application/ld\+json["\'][^>]*>)([\s\S]*?)(</script>)', re.IGNORECASE)
    
    modified = False
    new_content = content
    
    def process_node(node):
        changed = False
        if isinstance(node, dict):
            # Check for Offer
            if node.get('@type') == 'Offer':
                if 'shippingDetails' not in node:
                    node['shippingDetails'] = {
                        "@type": "OfferShippingDetails",
                        "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": "USD"},
                        "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "US"},
                        "deliveryTime": {
                            "@type": "ShippingDeliveryTime",
                            "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "d"},
                            "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 5, "unitCode": "d"}
                        }
                    }
                    changed = True
                if 'hasMerchantReturnPolicy' not in node:
                    node['hasMerchantReturnPolicy'] = {
                        "@type": "MerchantReturnPolicy",
                        "applicableCountry": "US",
                        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                        "merchantReturnDays": 30,
                        "returnMethod": "https://schema.org/ReturnByMail",
                        "returnFees": "https://schema.org/FreeReturn"
                    }
                    changed = True

            # Check for Product
            if node.get('@type') == 'Product':
                if 'description' not in node:
                    name = node.get('name', 'this product')
                    node['description'] = f"A highly rated and recommended {name} for your personal care needs."
                    changed = True
                
                # Global identifier (brand or gtin/sku)
                has_global_id = any(k in node for k in ['brand', 'gtin', 'gtin8', 'gtin12', 'gtin13', 'gtin14', 'mpn', 'sku'])
                if not has_global_id:
                    node['brand'] = {
                        "@type": "Brand",
                        "name": "Generic"
                    }
                    changed = True

            # Recursively process dict values
            for k, v in node.items():
                if process_node(v):
                    changed = True

        elif isinstance(node, list):
            for item in node:
                if process_node(item):
                    changed = True
                    
        return changed

    def replace_json_ld(match):
        nonlocal modified
        start_tag = match.group(1)
        json_content = match.group(2)
        end_tag = match.group(3)
        
        try:
            data = json.loads(json_content)
            if process_node(data):
                modified = True
                # Format json nicely
                new_json = json.dumps(data, indent=2)
                # Apply indentation to match original script tag formatting roughly
                return f"{start_tag}\n{new_json}\n    {end_tag}"
            return match.group(0)
        except json.JSONDecodeError:
            # If JSON is invalid, return original
            return match.group(0)

    new_content = script_pattern.sub(replace_json_ld, content)

    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated schema in {file_path}")
        return True
    return False

def main():
    repo_dir = r"c:\Users\mok24\OneDrive\Documents\GitHub\oceanside"
    exclude_dirs = ['_site', '.git', 'node_modules']
    
    updated_count = 0
    for root, dirs, files in os.walk(repo_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                if update_schema_in_html(file_path):
                    updated_count += 1
                    
    print(f"Finished. Updated {updated_count} files.")

if __name__ == '__main__':
    main()
