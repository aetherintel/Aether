from fastapi import APIRouter, Query
from services.overpass_service import fetch_osint_layers, LAYER_QUERIES

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/osint-layers")
async def get_osint_layers(
    lat: float = Query(..., description="Latitude of the center point"),
    lng: float = Query(..., description="Longitude of the center point"),
    radius: int = Query(500, ge=100, le=5000, description="Search radius in meters"),
    layers: str = Query(
        "cameras,atm,police,military",
        description=f"Comma-separated layer names. Available: {', '.join(LAYER_QUERIES.keys())}"
    ),
):
    """Fetch OSINT points of interest around a coordinate via Overpass API.

    Returns a dict keyed by layer name with lists of elements.
    """
    layer_list = [l.strip() for l in layers.split(",") if l.strip()]
    return await fetch_osint_layers(lat, lng, radius, layer_list)


@router.get("/osint-layers/available")
async def get_available_layers():
    """List all available OSINT layer names."""
    return {"layers": list(LAYER_QUERIES.keys())}
