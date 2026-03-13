import os
import httpx
import logging

logger = logging.getLogger(__name__)

# Primary + fallback Overpass endpoints
OVERPASS_URLS = [
    os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter"),
    "https://overpass.kumi.systems/api/interpreter",
]

# OSM tag filters per layer — used to build Overpass QL queries
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

# Direct tag matchers per layer — (key, value_or_None) tuples.
# None means "key must exist with any value".
# alpr uses two conditions — handled specially.
LAYER_MATCHERS: dict[str, list[tuple[str, str | None]]] = {
    "alpr":     [("man_made", "surveillance"), ("surveillance:type", "ALPR")],
    "cameras":  [("man_made", "surveillance")],
    "atm":      [("amenity", "atm")],
    "bank":     [("amenity", "bank")],
    "police":   [("amenity", "police")],
    "military": [("military", None)],
    "power":    [("power", "substation")],
    "water":    [("man_made", "water_tower")],
}


def _matches_layer(tags: dict, layer: str) -> bool:
    """Return True if the element tags satisfy all conditions for the layer."""
    conditions = LAYER_MATCHERS.get(layer, [])
    return all(
        (tags.get(k) == v if v is not None else k in tags)
        for k, v in conditions
    )


async def fetch_osint_layers(
    lat: float,
    lng: float,
    radius: int = 500,
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

    raw_elements = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in OVERPASS_URLS:
            try:
                resp = await client.post(url, data={"data": query})
                resp.raise_for_status()
                raw_elements = resp.json().get("elements", [])
                logger.info(f"Overpass OK via {url} ({len(raw_elements)} elements)")
                break
            except Exception as e:
                logger.warning(f"Overpass {url} failed: {e}, trying next...")

    if raw_elements is None:
        logger.error("All Overpass endpoints failed")
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
        # alpr is most specific — check it first, then the others
        for layer in active:
            if _matches_layer(tags, layer):
                result[layer].append(item)
                break

    for layer in active:
        logger.info(f"Overpass layer '{layer}': {len(result[layer])} elements")

    return result
