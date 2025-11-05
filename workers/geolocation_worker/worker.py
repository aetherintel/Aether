# workers/geolocation_worker/worker.py
import logging
import asyncio
import os
import pickle
from typing import List, Dict, Optional, Tuple
import spacy
from rq import get_current_job
from neo4j import AsyncGraphDatabase
import requests
from functools import lru_cache

logger = logging.getLogger(__name__)

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
PHOTON_URL = os.getenv("PHOTON_URL", "http://photon:2322")
GEONAMES_DATA_DIR = os.getenv("GEONAMES_DATA_DIR", "/app/models/geolocation/geonames")

driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Global state
_nlp = None
_geonames_loaded = False
GEONAMES_INDEX = {}
ALTERNATE_NAMES = {}


def get_nlp():
    """Lazy load spaCy model"""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("de_core_news_sm")
            logger.info("✅ spaCy German model loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load spaCy model: {e}")
            _nlp = False  # Mark as failed
    return _nlp if _nlp else None


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


def resolve_toponym(location_name: str, context: str = "") -> Optional[Dict]:
    """Resolve location name to coordinates"""
    load_geonames_index()  # Lazy load on first use
    
    if not GEONAMES_INDEX:
        return None
    
    name_lower = location_name.lower().strip()
    
    # Check alternate names (handles "Alex" -> "Alexanderplatz")
    if name_lower in ALTERNATE_NAMES:
        canonical = ALTERNATE_NAMES[name_lower]
        if canonical in GEONAMES_INDEX:
            return GEONAMES_INDEX[canonical]
    
    # Direct lookup
    if name_lower in GEONAMES_INDEX:
        return GEONAMES_INDEX[name_lower]
    
    # Fuzzy matching
    candidates = [
        data for key, data in GEONAMES_INDEX.items()
        if name_lower in key or key in name_lower
    ]
    
    if not candidates:
        return None
    
    # Disambiguation via context
    if context:
        context_lower = context.lower()
        for candidate in candidates:
            if candidate['name'].lower() in context_lower:
                return candidate
    
    # Return most populous
    return max(candidates, key=lambda x: x['population'])

# ============================================================================
# NER - Extract Location Entities
# ============================================================================

def extract_location_entities(text: str) -> List[Tuple[str, int, int]]:
    """Use spaCy NER to extract location entities"""
    nlp = get_nlp()
    if not nlp:
        return []
    
    doc = nlp(text)
    locations = []
    
    for ent in doc.ents:
        if ent.label_ in ['LOC', 'GPE']:
            locations.append((ent.text, ent.start_char, ent.end_char))
    
    return locations


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
# Geocoding with Fallback
# ============================================================================

async def geocode_with_fallback(location_name: str, geonames_data: Optional[Dict]) -> Optional[Dict]:
    """Geocode with GeoNames first, Photon as fallback"""
    
    # Strategy 1: GeoNames (offline, fast)
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
    
    # Strategy 2: Photon fallback (with retry and timeout)
    try:
        response = requests.get(
            f"{PHOTON_URL}/api",
            params={'q': location_name, 'limit': 1, 'lang': 'de'},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                feature = data['features'][0]
                geometry = feature.get('geometry', {})
                properties = feature.get('properties', {})
                
                if geometry.get('coordinates'):
                    lng, lat = geometry['coordinates']
                    return {
                        'lat': lat,
                        'lng': lng,
                        'display_name': properties.get('name', location_name),
                        'osm_id': properties.get('osm_id'),
                        'source': 'photon',
                        'city': properties.get('city'),
                        'country': properties.get('country', 'Deutschland')
                    }
    except requests.exceptions.ConnectionError:
        logger.warning(f"Photon unavailable for '{location_name}'")
    except requests.exceptions.Timeout:
        logger.warning(f"Photon timeout for '{location_name}'")
    except Exception as e:
        logger.warning(f"Photon error for '{location_name}': {e}")
    
    return None


# ============================================================================
# Main Worker
# ============================================================================

def extract_and_update_location(message_id: str, text: str, owner_id: str, case_id: int):
    """RQ worker entry point"""
    print("DEBUG: Starting geolocation extraction...")
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
        
        # Extract entities
        entities = extract_location_entities(text)
        
        if not entities:
            logger.info(f"No entities in {message_id}")
            await update_message_geolocation_status(message_id, 'no_location', owner_id)
            return {"status": "no_location", "message_id": message_id}
        
        logger.info(f"Found entities: {[e[0] for e in entities]}")
        
        # Resolve and geocode
        locations = []
        for entity_text, start, end in entities:
            context = text[max(0, start-50):min(len(text), end+50)]
            
            geonames_data = resolve_toponym(entity_text, context)
            coords = await geocode_with_fallback(entity_text, geonames_data)
            
            if coords:
                locations.append({
                    'raw': entity_text,
                    'canonical_name': geonames_data['name'] if geonames_data else entity_text,
                    'latitude': coords['lat'],
                    'longitude': coords['lng'],
                    'display_name': coords['display_name'],
                    'geonameid': coords.get('geonameid'),
                    'source': coords['source'],
                    'country': coords.get('country', 'Deutschland'),
                    'city': coords.get('city'),
                    'confidence': 'high' if geonames_data else 'medium'
                })
                logger.info(f"✅ {entity_text} -> ({coords['lat']}, {coords['lng']})")
            else:
                logger.warning(f"❌ Could not geocode: {entity_text}")
        
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