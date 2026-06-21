import os
import json
import csv
import math
import sys

# Configure UTF-8 encoding for Windows console output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'homewater_zip_database.json')
CSV_PATH = os.path.join(BASE_DIR, 'uscities.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'zips')

def is_supported(data):
    """
    Determines if a ZIP code has valid water hardness data.
    """
    if not data:
        return False
    attrs = data.get('waterAttributes', {})
    if not attrs:
        return False
    
    h_total = attrs.get('hardness_total', {})
    h_camag = attrs.get('hardness_camag', {})
    
    val_total = h_total.get('value') if isinstance(h_total, dict) else None
    val_camag = h_camag.get('value') if isinstance(h_camag, dict) else None
    
    return val_total is not None or val_camag is not None

def shard_db_with_fallbacks():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Master database file not found at: {DB_PATH}")
        return
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: US Cities database not found at: {CSV_PATH}")
        return

    print(f"📖 Loading master database from {DB_PATH}...")
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except Exception as e:
        print(f"❌ Error loading master database JSON: {e}")
        return

    print(f"📖 Loading US cities coordinates from {CSV_PATH}...")
    all_zip_coords = {}
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat = float(row['lat'])
                    lng = float(row['lng'])
                    # 'zips' column is space-separated list of zip codes
                    zips_list = row['zips'].split()
                    for z in zips_list:
                        z_clean = z.strip().zfill(5)
                        if z_clean not in all_zip_coords:
                            all_zip_coords[z_clean] = (lat, lng)
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return

    # 1. Identify all supported ZIP codes (those with valid water quality/hardness data)
    supported_zips = {}
    for zip_code, data in db.items():
        zip_str = str(zip_code).strip().zfill(5)
        if is_supported(data):
            supported_zips[zip_str] = data

    print(f"✅ Found {len(supported_zips):,} supported ZIP codes with water hardness data.")
    print(f"✅ Found {len(all_zip_coords):,} total US ZIP code coordinates in CSV.")

    # 2. Extract coordinates and convert to 3D Cartesian coordinates on unit sphere
    # x = cos(lat) * cos(lng)
    # y = cos(lat) * sin(lng)
    # z = sin(lat)
    supported_cartesian = {}
    for z in supported_zips:
        if z in all_zip_coords:
            lat, lng = all_zip_coords[z]
            lat_rad = math.radians(lat)
            lng_rad = math.radians(lng)
            x = math.cos(lat_rad) * math.cos(lng_rad)
            y = math.cos(lat_rad) * math.sin(lng_rad)
            z_val = math.sin(lat_rad)
            supported_cartesian[z] = (x, y, z_val)

    print(f"📍 {len(supported_cartesian):,} supported ZIP codes mapped to Cartesian coordinates.")

    # 3. Calculate closest supported ZIP code using 3D dot product maximization
    # This avoids trigonometry in the inner loop completely!
    print("⏳ Calculating closest supported locations for all unsupported ZIP codes (Cartesian Optimization)...")
    
    # We unpack for speed
    supported_list = list(supported_cartesian.items()) # list of (zip, (x, y, z))
    
    fallback_cache = {}
    unsupported_count = 0
    mapped_count = 0
    
    for z, coords in all_zip_coords.items():
        if z in supported_zips:
            continue
        
        unsupported_count += 1
        lat_rad = math.radians(coords[0])
        lng_rad = math.radians(coords[1])
        x0 = math.cos(lat_rad) * math.cos(lng_rad)
        y0 = math.cos(lat_rad) * math.sin(lng_rad)
        z0 = math.sin(lat_rad)
        
        closest_zip = None
        max_dot = -2.0 # dot product range is [-1, 1]
        
        # Inner loop: only 3 multiplications and 2 additions!
        for sz, (sz_x, sz_y, sz_z) in supported_list:
            dot = x0 * sz_x + y0 * sz_y + z0 * sz_z
            if dot > max_dot:
                max_dot = dot
                closest_zip = sz
        
        if closest_zip:
            fallback_cache[z] = closest_zip
            mapped_count += 1

    print(f"🎯 Mapped {mapped_count:,} out of {unsupported_count:,} unsupported ZIP codes to their nearest monitored location.")

    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created directory: {OUTPUT_DIR}")

    # 4. Group all entries by their 3-digit prefix
    shards = {}
    
    # Add supported entries
    for z, data in supported_zips.items():
        prefix = z[:3]
        if prefix not in shards:
            shards[prefix] = {}
        shards[prefix][z] = data

    # Add fallback entries
    for z, sz in fallback_cache.items():
        prefix = z[:3]
        if prefix not in shards:
            shards[prefix] = {}
        if sz in supported_zips:
            shards[prefix][z] = sz

    print("⚙️ Writing sharded database files...")
    
    # Write shard files
    written_count = 0
    for prefix, prefix_data in shards.items():
        shard_path = os.path.join(OUTPUT_DIR, f"{prefix}.json")
        try:
            with open(shard_path, 'w', encoding='utf-8') as f:
                json.dump(prefix_data, f, ensure_ascii=False, separators=(',', ':'))
            written_count += 1
        except Exception as e:
            print(f"❌ Error writing shard {prefix}.json: {e}")

    print(f"🎉 Success! Database split and mapped into {written_count} files in '{OUTPUT_DIR}'.")

if __name__ == '__main__':
    shard_db_with_fallbacks()
