# workers/geolocation_worker/worker.py
import logging
import asyncio
import os
import pickle
from typing import List, Dict, Optional, Tuple
from gliner import GLiNER  # Replaces spaCy
from rq import get_current_job
from neo4j import AsyncGraphDatabase
import requests
import httpx
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from aether_lib.utils.event_publisher import publish_event as _publish_event
except Exception:
    def _publish_event(event_type, payload): pass

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

GEONAMES_DATA_DIR = os.getenv("GEONAMES_DATA_DIR", "/app/models/geolocation/geonames")
GLINER_MODEL_PATH = os.getenv("GLINER_MODEL_PATH", "/app/models/geolocation/gliner_model")

# ArcGIS / ESRI
ESRI_API_KEY = os.getenv("ESRI_API_KEY")
ARCGIS_GEOCODE_URL = (
    "https://geocode-api.arcgis.com/arcgis/rest/services"
    "/World/GeocodeServer/findAddressCandidates"
)

driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Global state
_gliner_model = None
_geonames_loaded = False
GEONAMES_INDEX = {}
ALTERNATE_NAMES = {}


def get_gliner_model():
    """Lazy load GLiNER model"""
    global _gliner_model
    if _gliner_model is None:
        try:
            logger.info(f"🚀 Loading GLiNER model from {GLINER_MODEL_PATH}...")
            # Load from local path, ensure map_location is set for CPU if needed
            _gliner_model = GLiNER.from_pretrained(GLINER_MODEL_PATH, local_files_only=True)
            logger.info("✅ GLiNER model loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load GLiNER model: {e}")
            _gliner_model = False  # Mark as failed
    return _gliner_model if _gliner_model else None


# workers/geolocation_worker/worker.py

def load_geonames_index():
    """Load pre-built pickle index (instant loading)"""
    global _geonames_loaded, GEONAMES_INDEX, ALTERNATE_NAMES
    
    if _geonames_loaded:
        return
    
    pickle_file = f"{GEONAMES_DATA_DIR}/index.pkl"
    
    if not os.path.exists(pickle_file):
        logger.error(f"❌ GeoNames index not found: {pickle_file}")
        logger.error("Run: ./scripts/setup_geolocation_complete.sh")
        _geonames_loaded = True
        return
    
    try:
        logger.info("📍 Loading GeoNames index...")
        
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        GEONAMES_INDEX = data['index']
        ALTERNATE_NAMES = data['alternates']
        metadata = data.get('metadata', {})
        
        logger.info(f"   {len(GEONAMES_INDEX):,} locations")
        logger.info(f"   {len(ALTERNATE_NAMES):,} alternate names")
        
        _geonames_loaded = True
        
    except Exception as e:
        logger.error(f"❌ Failed to load GeoNames pickle: {e}")
        _geonames_loaded = True


# ============================================================================
# NER - Extract Location Entities
# ============================================================================

# Common false positives in German text that GLiNER might pick up as locations
BLOCKLIST = {
    "land", "stadt", "staat", "ort", "region", "platz", "straße", "weg", 
    "hier", "da", "dort", "heimat", "bund", "insel", "berg", "fluss",
    "osten", "westen", "norden", "süden",
    "polizei", "regierung", "amt", "behörde" 
}

def extract_location_entities(text: str) -> List[Tuple[str, int, int]]:
    """Use GLiNER to extract location entities with filtering"""
    model = get_gliner_model()
    if not model:
        return []
    
    # Focused labels for GLiNER
    labels = ["city", "country", "location", "landmark"]
    
    try:
        # GLiNER predict_entities
        # Increased threshold to 0.60 to reduce noise like "Land"
        entities = model.predict_entities(text, labels, threshold=0.60)
        
        locations = []
        for ent in entities:
            raw_text = ent['text']
            clean_text = raw_text.lower().strip()
            
            # Filter 1: Length
            if len(clean_text) < 3:
                continue
                
            # Filter 2: Blocklist
            if clean_text in BLOCKLIST:
                continue
            
            # Filter 3: Blocklist substring (cautious)
            # e.g. "mein Land" -> "land" is in blocklist, but "Deutschland" is not.
            # checks if the exact extracted entity is in blocklist.
            
            locations.append((raw_text, ent['start'], ent['end']))
            
        return locations
    except Exception as e:
        logger.error(f"GLiNER prediction failed: {e}")
        return []


# ============================================================================
# Toponym Resolution
# ============================================================================

@lru_cache(maxsize=1000)
def resolve_toponym(location_name: str, context: str = "") -> Optional[Dict]:
    """Resolve location name with caching"""
    load_geonames_index()  # Lazy load
    
    if not GEONAMES_INDEX:
        return None
    
    name_lower = location_name.lower().strip()
    
    # Check alternate names
    if name_lower in ALTERNATE_NAMES:
        canonical = ALTERNATE_NAMES[name_lower]
        if canonical in GEONAMES_INDEX:
            return GEONAMES_INDEX[canonical]
    
    # Direct lookup
    if name_lower in GEONAMES_INDEX:
        return GEONAMES_INDEX[name_lower]
    
    # Partial matching
    candidates = [
        data for key, data in GEONAMES_INDEX.items()
        if name_lower in key or key in name_lower
    ]
    
    if not candidates:
        return None
    
    # Context-based disambiguation
    if context:
        context_lower = context.lower()
        for candidate in candidates:
            if candidate['name'].lower() in context_lower:
                return candidate
    
    # Return most populous
    return max(candidates, key=lambda x: x['population'])


# ============================================================================
# Geocoding (GeoNames Only)
# ============================================================================

async def geocode_location(location_name: str, geonames_data: Optional[Dict]) -> Optional[Dict]:
    """Geocode using GeoNames data"""
    
    if geonames_data:
        return {
            'lat': geonames_data['lat'],
            'lng': geonames_data['lng'],
            'display_name': geonames_data['name'],
            'geonameid': geonames_data['geonameid'],
            'source': 'geonames',
            'country': geonames_data['country'],
            'admin1': geonames_data.get('admin1'),
            'admin2': geonames_data.get('admin2'),
            'population': geonames_data.get('population', 0)
        }
    
    return None


# ============================================================================
# ArcGIS Entity Geocoding (replaces GeoNames per-entity lookup)
# ============================================================================

async def geocode_entity_with_arcgis(entity_name: str) -> Optional[Dict]:
    """Geocode a single location name (extracted by GLiNER) via ArcGIS.

    ArcGIS is excellent at resolving clean location names like "Lyon", "Berlin",
    "Alexanderplatz" — much better than sending a full paragraph.
    Score threshold: 75. Returns None if no confident match.
    """
    if not ESRI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(ARCGIS_GEOCODE_URL, params={
                "singleLine": entity_name,
                "f": "pjson",
                "token": ESRI_API_KEY,
                "outFields": "Match_addr,LongLabel,City,Region,Country,Type",
                "maxLocations": 1,
            })
            resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"ArcGIS geocode request failed for '{entity_name}': {e}")
        return None

    candidates = data.get("candidates", [])
    if not candidates:
        return None

    best = candidates[0]
    score = best.get("score", 0)
    if score < 75:
        print(f"DEBUG: ArcGIS score {score} < 75 for '{entity_name}', discarding", flush=True)
        return None

    loc = best.get("location", {})
    lat = loc.get("y")
    lng = loc.get("x")
    if lat is None or lng is None:
        return None

    attrs = best.get("attributes", {})
    display_name = attrs.get("LongLabel") or best.get("address", entity_name)
    print(f"DEBUG: ArcGIS geocoded '{entity_name}' → {display_name} ({lat}, {lng}) score={score}", flush=True)
    return {
        "lat": lat,
        "lng": lng,
        "display_name": display_name,
        "country": attrs.get("Country", ""),
        "city": attrs.get("City", ""),
        "source": "arcgis",
    }


# ============================================================================
# Main Worker
# ============================================================================

def extract_and_update_location(message_id: str, text: str, owner_id: str, case_id: int):
    """RQ worker entry point"""
    print(f"DEBUG: Starting geolocation extraction... ESRI_API_KEY set={bool(ESRI_API_KEY)}", flush=True)
    job = get_current_job()
    job_id = job.id if job else 'unknown'

    return asyncio.run(_extract_and_update_location_async(
        message_id, text, owner_id, case_id, job_id
    ))


async def _extract_and_update_location_async(
    message_id: str, text: str, owner_id: str, case_id: int, job_id: str
):
    """Main extraction logic"""
    try:
        
        logger.info(f"Processing: {text[:100]}...")

        locations = []

        # Step 1: always extract entities with GLiNER
        entities = extract_location_entities(text)

        if not entities:
            print(f"DEBUG: GLiNER found no entities in {message_id}", flush=True)
            await update_message_geolocation_status(message_id, 'no_location', owner_id)
            return {"status": "no_location", "message_id": message_id}

        print(f"DEBUG: GLiNER found entities: {[e[0] for e in entities]}", flush=True)

        # Step 2: geocode each entity — ArcGIS primary, GeoNames fallback
        for entity_text, start, end in entities:
            coords = None

            if ESRI_API_KEY:
                # Primary: ArcGIS (precise, global coverage)
                arcgis_result = await geocode_entity_with_arcgis(entity_text)
                if arcgis_result:
                    coords = arcgis_result
                    locations.append({
                        'raw': entity_text,
                        'canonical_name': arcgis_result['display_name'],
                        'latitude': arcgis_result['lat'],
                        'longitude': arcgis_result['lng'],
                        'display_name': arcgis_result['display_name'],
                        'source': 'arcgis',
                        'country': arcgis_result.get('country', ''),
                        'city': arcgis_result.get('city', ''),
                        'confidence': 'high',
                    })
                    continue

            # Fallback: GeoNames local index
            context = text[max(0, start-50):min(len(text), end+50)]
            geonames_data = resolve_toponym(entity_text, context)
            coords = await geocode_location(entity_text, geonames_data)

            if coords:
                locations.append({
                    'raw': entity_text,
                    'canonical_name': geonames_data['name'] if geonames_data else entity_text,
                    'latitude': coords['lat'],
                    'longitude': coords['lng'],
                    'display_name': coords['display_name'],
                    'geonameid': coords.get('geonameid'),
                    'source': coords['source'],
                    'country': coords.get('country', ''),
                    'city': coords.get('city', ''),
                    'confidence': 'high' if geonames_data else 'medium',
                })
            else:
                print(f"DEBUG: Could not geocode '{entity_text}' via ArcGIS or GeoNames", flush=True)
        
        if locations:
            await store_locations_neo4j(message_id, locations, owner_id)
            await update_message_geolocation_status(message_id, 'completed', owner_id)
            return {
                "status": "success",
                "message_id": message_id,
                "locations_found": len(locations)
            }
        else:
            await update_message_geolocation_status(message_id, 'no_coordinates', owner_id)
            return {"status": "no_coordinates", "message_id": message_id}
            
    except Exception as e:
        logger.error(f"Failed for {message_id}: {e}", exc_info=True)
        await update_message_geolocation_status(message_id, 'failed', owner_id)
        raise


async def store_locations_neo4j(message_id: str, locations: list, owner_id: str):
    """Store in Neo4j"""
    async with driver.session() as session:
        for loc in locations:
            try:
                await session.run(
                    """
                    MATCH (m:Message {mid: $mid, owner_id: $owner})
                    MERGE (l:Location {canonical_name: $name, owner_id: $owner})
                    ON CREATE SET
                        l.latitude = $lat, l.longitude = $lng,
                        l.location = point({latitude: $lat, longitude: $lng}),
                        l.geonameid = $gid, l.source = $src,
                        l.country = $country, l.created_at = datetime()
                    ON MATCH SET l.mention_count = coalesce(l.mention_count, 0) + 1
                    MERGE (m)-[:MENTIONS_LOCATION]->(l)
                    """,
                    mid=message_id, owner=owner_id, name=loc['canonical_name'],
                    lat=loc['latitude'], lng=loc['longitude'],
                    gid=loc.get('geonameid'), src=loc['source'],
                    country=loc['country']
                )
            except Exception as e:
                logger.error(f"Store error: {e}")


async def update_message_geolocation_status(mid: str, status: str, owner: str):
    async with driver.session() as s:
        await s.run(
            "MATCH (m:Message {mid: $mid, owner_id: $owner}) "
            "SET m.geolocation_status = $status, m.geolocation_processed_at = datetime()",
            mid=mid, owner=owner, status=status
        )
    # Publish for all terminal statuses so the frontend clears the pending state
    if status in ("completed", "no_location", "no_coordinates", "failed"):
        _publish_event("message_status_changed", {
            "message_id": mid,
            "owner_id": owner,
            "updates": {"geolocation_status": status},
        })