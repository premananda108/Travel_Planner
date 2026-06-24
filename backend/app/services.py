import time
import logging
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)

class ArtworkCache:
    """In-memory TTL cache for artwork validation responses."""
    def __init__(self, ttl: int):
        self.ttl = ttl
        self.store: Dict[str, Dict[str, Any]] = {}

    def get(self, artwork_id: str) -> Optional[Dict[str, Any]]:
        if artwork_id in self.store:
            entry = self.store[artwork_id]
            if entry["expires_at"] > time.time():
                logger.info(f"Cache hit for artwork {artwork_id}")
                return entry["data"]
            else:
                logger.info(f"Cache expired for artwork {artwork_id}")
                del self.store[artwork_id]
        return None

    def set(self, artwork_id: str, data: Dict[str, Any]) -> None:
        self.store[artwork_id] = {
            "data": data,
            "expires_at": time.time() + self.ttl
        }
        logger.info(f"Cached artwork {artwork_id} with TTL {self.ttl}s")

# Global cache instance
artwork_cache = ArtworkCache(ttl=settings.CACHE_TTL_SECONDS)

async def fetch_artwork_from_api(artwork_id: str) -> Dict[str, Any]:
    """
    Fetches details of an artwork from the Art Institute of Chicago API.
    Raises HTTPException if the artwork doesn't exist or if there is an API error.
    """
    # 1. Check cache first
    cached_data = artwork_cache.get(artwork_id)
    if cached_data:
        return cached_data

    # 2. Query external API
    url = f"{settings.ART_API_BASE_URL}/artworks/{artwork_id}"
    params = {"fields": "id,title,image_id"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Artwork with ID '{artwork_id}' not found in the Art Institute of Chicago API."
                )
            elif response.status_code != 200:
                logger.error(f"External API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Error communicating with the Art Institute of Chicago API."
                )

            data = response.json()
            artwork_data = data.get("data")
            if not artwork_data:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"External API returned empty data for artwork ID '{artwork_id}'."
                )

            # Extract fields we care about
            result = {
                "external_id": str(artwork_data.get("id")),
                "title": artwork_data.get("title") or "Unknown Title",
                "image_id": artwork_data.get("image_id"),
            }

            # 3. Store in cache
            artwork_cache.set(artwork_id, result)
            return result

        except httpx.RequestError as exc:
            logger.error(f"Network error accessing Art Institute API: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Art Institute of Chicago API. Please try again later."
            )
