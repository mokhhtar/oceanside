import os
import json
import sys

# Configure UTF-8 encoding for Windows console output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# The master database file (place it in the same directory as this script)
DB_PATH = os.path.join(BASE_DIR, 'homewater_zip_database.json')
OUTPUT_DIR = os.path.join(BASE_DIR, 'zips')

def shard_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Master database file not found at: {DB_PATH}")
        print("Please place your undivided 'homewater_zip_database.json' file in the same folder as this script.")
        return

    print(f"📖 Loading master database from {DB_PATH}...")
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")
        return

    total_zips = len(db)
    print(f"✅ Loaded {total_zips:,} ZIP codes.")

    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created directory: {OUTPUT_DIR}")

    # Group by first 3 digits
    shards = {}
    for zip_code, data in db.items():
        # Ensure zip code is a string of length 5
        zip_str = str(zip_code).strip().zfill(5)
        prefix = zip_str[:3]
        if prefix not in shards:
            shards[prefix] = {}
        shards[prefix][zip_str] = data

    print(f"⚙️ Splitting database into 3-digit prefix files...")
    
    # Write shard files
    written_count = 0
    for prefix, prefix_data in shards.items():
        shard_path = os.path.join(OUTPUT_DIR, f"{prefix}.json")
        try:
            with open(shard_path, 'w', encoding='utf-8') as f:
                json.dump(prefix_data, f, ensure_ascii=False)
            written_count += 1
        except Exception as e:
            print(f"❌ Error writing shard {prefix}.json: {e}")

    print(f"🎉 Success! Database split into {written_count} shard files in '{OUTPUT_DIR}'.")

if __name__ == '__main__':
    shard_db()
