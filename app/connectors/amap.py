import logging
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.config import AMAP_API_KEY, AMAP_ENABLED

logger = logging.getLogger(__name__)

AMAP_TEXT_SEARCH_URL = "https://restapi.amap.com/v3/place/text"


class AmapPlaceSearch:
    """Search POI via Amap (Gaode) API."""

    @property
    def available(self) -> bool:
        return AMAP_ENABLED

    def search_restaurant(self, name: str, city: str) -> Optional[dict]:
        """Search a restaurant by name and city.
        Returns dict with name, phone, rating, avg_price, address, amap_url.
        """
        if not self.available:
            return None
        params = (
            f"key={AMAP_API_KEY}"
            f"&keywords={quote(name)}"
            f"&city={quote(city)}"
            f"&types={quote('餐饮服务')}"
            f"&offset=3"
        )
        url = f"{AMAP_TEXT_SEARCH_URL}?{params}"
        try:
            import json

            req = Request(url, headers={"User-Agent": "travel-guide-mvp/0.1"})
            with urlopen(req, timeout=8) as resp:
                import json as _json

                data = _json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.error("Amap search failed for %s in %s: %s", name, city, exc)
            return None

        if data.get("status") != "1" or not data.get("pois"):
            logger.info("Amap no results for %s in %s: %s", name, city, data.get("info", ""))
            return None

        # Pick the best match (first result)
        poi = data["pois"][0]
        biz_ext = poi.get("biz_ext", {}) or {}
        location = poi.get("location", "")
        lon, lat = "", ""
        if location and "," in location:
            lon, lat = location.split(",", 1)

        result = {
            "name": poi.get("name", name),
            "phone": self._clean_phone(poi.get("tel") or ""),
            "rating": self._clean_rating(biz_ext.get("rating")),
            "avg_price": self._clean_cost(biz_ext.get("cost")),
            "address": poi.get("address") or "",
            "lon": lon,
            "lat": lat,
            "amap_url": (
                f"https://uri.amap.com/marker?position={location}&name={quote(poi.get('name', name))}"
                if location
                else None
            ),
            "meituan_url": f"https://i.meituan.com/search/poi?q={quote(name)}",
            "dianping_url": f"https://m.dianping.com/search/keyword?keyword={quote(name)}",
        }
        return result

    @staticmethod
    def _clean_phone(raw: str) -> Optional[str]:
        if not raw or len(raw) < 6:
            return None
        # Remove invalid markers
        cleaned = raw.replace("电话错误", "").strip()
        if cleaned and len(cleaned) >= 8:
            return cleaned
        return None

    @staticmethod
    def _clean_rating(raw) -> Optional[str]:
        if not raw:
            return None
        raw = str(raw).strip()
        if raw and raw != "0.0" and raw != "0":
            return raw
        return None

    @staticmethod
    def _clean_cost(raw) -> Optional[str]:
        if not raw:
            return None
        raw = str(raw).strip()
        if raw and raw != "0.00" and raw != "0":
            return f"¥{int(float(raw))}"
        return None


amap_place_search = AmapPlaceSearch()