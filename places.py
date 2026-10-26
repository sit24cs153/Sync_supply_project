import hashlib
import json
import math
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import User, PlacesCache
from app.rate_limit import limiter
from app.schemas import NearbyRequest, NearbyResponse, PlaceOut

router = APIRouter(prefix="/api/places", tags=["places"])
settings = get_settings()

KIND_QUERY = {
    "ayurvedic": "ayurvedic hospital OR ayurvedic shop OR ayurveda clinic",
    "hospital": "hospital emergency room",
    "homeopathy": "homeopathy clinic",
}

# Hospital/emergency searches use a tighter radius (closer = faster to reach)
# than a routine Ayurvedic-shop search, per the handoff guide's emergency flow.
KIND_RADIUS_METERS = {
    "ayurvedic": 15000,
    "hospital": 8000,
    "homeopathy": 15000,
}


def _haversine_meters(lat1, lng1, lat2, lng2) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(min(1, math.sqrt(a)))


def _cache_key(req: NearbyRequest) -> str:
    lat = round(req.latitude, 2) if req.latitude is not None else None
    lng = round(req.longitude, 2) if req.longitude is not None else None
    raw = json.dumps({"lat": lat, "lng": lng, "text": req.place_text, "kind": req.kind}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _fetch_phone(place_id: str) -> str | None:
    """One Place Details call per result, only for the first page of results,
    to keep this inside a free-tier Maps quota."""
    try:
        resp = httpx.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "formatted_phone_number", "key": settings.GOOGLE_MAPS_API_KEY},
            timeout=6,
        )
        data = resp.json()
        return data.get("result", {}).get("formatted_phone_number")
    except httpx.HTTPError:
        return None


@router.post("/nearby", response_model=NearbyResponse)
@limiter.limit(settings.RATE_LIMIT_PLACES)
def nearby(request: Request, payload: NearbyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.latitude is None and not payload.place_text:
        raise HTTPException(status_code=400, detail={"error": {"code": "location_required", "message": "Provide a location or a town/pin code."}})

    key = _cache_key(payload)
    cached = db.query(PlacesCache).filter(PlacesCache.cache_key == key).first()
    if cached and cached.created_at > datetime.utcnow() - timedelta(seconds=settings.PLACES_CACHE_SECONDS):
        return NearbyResponse(**cached.payload)

    if not settings.GOOGLE_MAPS_API_KEY:
        return NearbyResponse(places=[], message="Nearby care is not configured yet. Please try again later.")

    radius = KIND_RADIUS_METERS.get(payload.kind, 15000)
    query = KIND_QUERY.get(payload.kind, KIND_QUERY["ayurvedic"])
    params = {"query": query, "key": settings.GOOGLE_MAPS_API_KEY}
    if payload.latitude is not None and payload.longitude is not None:
        params["location"] = f"{payload.latitude},{payload.longitude}"
        params["radius"] = radius
    else:
        params["query"] = f"{query} near {payload.place_text}"

    try:
        resp = httpx.get("https://maps.googleapis.com/maps/api/place/textsearch/json", params=params, timeout=10)
        data = resp.json()
    except httpx.HTTPError:
        return NearbyResponse(places=[], message="Could not reach the maps service. Showing no results.")

    raw_results = data.get("results", [])[:10]

    # Hospital/emergency search: sort by distance when we have the user's
    # coordinates, so the closest option is first — matters most in a
    # genuine emergency flow.
    if payload.latitude is not None and payload.longitude is not None:
        def _dist(item):
            loc = item.get("geometry", {}).get("location", {})
            if "lat" not in loc:
                return float("inf")
            return _haversine_meters(payload.latitude, payload.longitude, loc["lat"], loc["lng"])
        raw_results.sort(key=_dist)

    places = []
    for idx, item in enumerate(raw_results):
        name = item.get("name", "")
        loc = item.get("geometry", {}).get("location", {})
        lat, lng = loc.get("lat"), loc.get("lng")
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}" if lat and lng else "https://www.google.com/maps"

        distance_m = None
        if payload.latitude is not None and lat is not None:
            distance_m = round(_haversine_meters(payload.latitude, payload.longitude, lat, lng), 1)

        phone = None
        place_id = item.get("place_id")
        if place_id and idx < 5:  # only fetch phone for the top 5 to respect quota
            phone = _fetch_phone(place_id)

        places.append(PlaceOut(
            name=name,
            address=item.get("formatted_address"),
            distance_meters=distance_m,
            open_now=item.get("opening_hours", {}).get("open_now"),
            maps_url=maps_url,
            phone=phone,
        ))

    message = None if places else "No nearby results found. In rural areas, try a nearby town or pin code instead."

    response = NearbyResponse(places=places, message=message)

    if cached:
        cached.payload = response.model_dump()
        cached.created_at = datetime.utcnow()
    else:
        db.add(PlacesCache(cache_key=key, payload=response.model_dump(), created_at=datetime.utcnow()))
    db.commit()

    return response
