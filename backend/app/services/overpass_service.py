import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OVERPASS_URL = os.getenv(
    "OVERPASS_API_URL",
    "https://overpass-api.de/api/interpreter"
)

# OSM tag filters per layer
LAYER_QUERIES: dict[str, str] = {
    "cameras":  'node["man_made"="surveillance"]',
    "atm":      'node["amenity"="atm"]',
    "bank":     'node["amenity"="bank"]',
    "police":   'node["amenity"="police"]',
    "military": 'node["military"]',
    "power":    'node["power"="substation"]',
    "water":    'node["man_made"="water_tower"]',
    "alpr":     'node["man_made"="surveillance"]["surveillance:type"="ALPR"]',
}


def _parse_layer_tag(query_filter: str) -> tuple[str, Optional[str]]:
    """Extract (key, value) from an Overpass tag filter string."""
    # Strip 'node[' prefix and trailing ']'
    inner = query_filter[len("node["):].rstrip("]")
    # Handle multi-tag filters like "key"="val"]["key2"="val2" — only use first tag
    first_tag = inner.split(']["')[0]
    first_tag = first_tag.strip('"')
    if '="' in first_tag:
        key, _, val = first_tag.partition('="')
        return key, val.rstrip('"')
    return first_tag, None


async def fetch_osint_layers(
    lat: float,
    lng: float,
    radius: int = 1000,
    layers: list[str] | None = None,
) -> dict:
    """Query Overpass API for OSINT points of interest around given coordinates.

    Returns a dict keyed by layer name with lists of GeoJSON-like items.
    """
    active = [l for l in (layers or list(LAYER_QUERIES.keys())) if l in LAYER_QUERIES]

    node_blocks = "\n  ".join(
        f'{LAYER_QUERIES[layer]}(around:{radius},{lat},{lng});'
        for layer in active
    )
    query = f"""[out:json][timeout:25];
(
  {node_blocks}
);
out body;"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
        raw_elements = resp.json().get("elements", [])
    except Exception as e:
        logger.error(f"Overpass request failed: {e}")
        return {layer: [] for layer in active}

    result: dict[str, list] = {layer: [] for layer in active}

    for el in raw_elements:
        tags = el.get("tags", {})
        item = {
            "id":       el["id"],
            "lat":      el.get("lat"),
            "lng":      el.get("lon"),
            "name":     tags.get("name", ""),
            "operator": tags.get("operator", ""),
            "tags":     tags,
        }
        # Assign element to the first matching layer
        for layer in active:
            key, val = _parse_layer_tag(LAYER_QUERIES[layer])
            if val:
                if tags.get(key) == val:
                    result[layer].append(item)
                    break
            else:
                if key in tags:
                    result[layer].append(item)
                    break

    for layer in active:
        logger.debug(f"Overpass layer '{layer}': {len(result[layer])} elements")

    return result
