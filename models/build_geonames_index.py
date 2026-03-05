import os
import pickle
import sys

# Paths
DATA_DIR = "models/geolocation/geonames"
OUTPUT_FILE = os.path.join(DATA_DIR, "index.pkl")

def build_index():
    print(f"🔨 Building GeoNames index in {DATA_DIR}...")
    
    # Check files
    de_file = os.path.join(DATA_DIR, "DE.txt")
    alt_file = os.path.join(DATA_DIR, "alternateNamesV2.txt")
    
    if not os.path.exists(de_file):
        print(f"❌ Missing {de_file}")
        sys.exit(1)
        
    if not os.path.exists(alt_file):
        print(f"❌ Missing {alt_file}")
        sys.exit(1)
        
    geo_index = {}
    
    # 1. Parse DE.txt
    print("   Parsing DE.txt...")
    count = 0
    with open(de_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            # geonameid, name, asciiname, alternatenames, lat, lng, ..., population (14)
            if len(parts) < 15:
                continue
                
            geonameid = parts[0]
            name = parts[1]
            lat = float(parts[4])
            lng = float(parts[5])
            country = parts[8]
            admin1 = parts[10]
            admin2 = parts[11]
            population = int(parts[14]) if parts[14].isdigit() else 0
            
            # Simple filtering (e.g. only > 0 population or specific feature classes?)
            # For now, keep all, or maybe filter P (cities/villages)
            feature_class = parts[6]
            feature_code = parts[7]
            
            # Key by lowercase name
            key = name.lower()
            
            # Store data
            entry = {
                'geonameid': geonameid,
                'name': name,
                'lat': lat,
                'lng': lng,
                'country': country,
                'admin1': admin1,
                'admin2': admin2,
                'population': population
            }
            
            # Collision handling: keep largest population
            if key in geo_index:
                if population > geo_index[key]['population']:
                    geo_index[key] = entry
            else:
                geo_index[key] = entry
            
            count += 1
            
    print(f"   Loaded {len(geo_index)} primary locations from {count} rows.")
    
    # 2. Parse Alternate Names (Optional but good for completeness)
    print("   Parsing alternateNamesV2.txt (filtering for DE)...")
    alt_map = {}
    valid_ids = set(e['geonameid'] for e in geo_index.values())
    
    with open(alt_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 4:
                continue
                
            geonameid = parts[1]
            alt_name = parts[3].lower()
            
            if geonameid in valid_ids:
                # Map alt_name -> canonical name
                # We need to find the canonical entry.
                # Since we don't have a reverse map from ID to Name yet, let's create one or just store ID
                # Actually, worker expects `ALTERNATE_NAMES[lower] -> canonical_key`
                
                # Reverse lookup optimization
                # Optimization: we can't easily find the canonical key from ID efficiently without a map
                pass

    # Re-loop to build ID map
    id_to_key = {v['geonameid']: k for k, v in geo_index.items()}
    
    print("   Building alternate names map...")
    with open(alt_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 4:
                continue
                
            geonameid = parts[1]
            alt_name = parts[3].lower()
            
            # Only if target exists in our index
            if geonameid in id_to_key:
                canonical_key = id_to_key[geonameid]
                if alt_name != canonical_key: # distinct
                    alt_map[alt_name] = canonical_key

    print(f"   Loaded {len(alt_map)} alternate names.")

    # 3. Save
    print(f"💾 Saving to {OUTPUT_FILE}...")
    data = {
        'index': geo_index,
        'alternates': alt_map,
        'metadata': {'source': 'geonames.org'}
    }
    
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(data, f)
        
    print("✅ Done.")

if __name__ == "__main__":
    build_index()
