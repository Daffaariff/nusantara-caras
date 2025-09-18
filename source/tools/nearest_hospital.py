from __future__ import annotations
import argparse
import json
import os
import sys
import asyncio
from typing import Dict, List, Tuple, Optional

import aiohttp


class NearestFacilityFinder:
    """Find nearby facilities (hospital/apotek) using OSM (Nominatim + Overpass)."""

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(
        self,
        *,
        contact_email: str | None = None,
        lang: str = "id",
        request_timeout: int = 20,
        overpass_timeout: int = 60,
        polite_sleep: float = 1.0,
        nominatim_url: str | None = None,
        overpass_url: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.contact_email = contact_email or os.getenv("OSM_CONTACT", "contact@example.com")
        self.lang = lang
        self.request_timeout = request_timeout
        self.overpass_timeout = overpass_timeout
        self.polite_sleep = polite_sleep
        self.nominatim_url = nominatim_url or self.NOMINATIM_URL
        self.overpass_url = overpass_url or self.OVERPASS_URL
        self._session: aiohttp.ClientSession | None = session

    # ---- utilities -----------------------------------------------------------
    def _user_agent(self) -> str:
        return f"NearestFacilityScript/3.0 ({self.contact_email})"

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import radians, sin, cos, asin, sqrt
        R = 6371.0088
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return 2 * R * asin(sqrt(a))

    @staticmethod
    def _addr_label(
        *, address: Optional[str], street: Optional[str], city: Optional[str],
        state: Optional[str], country: Optional[str], postalcode: Optional[str]
    ) -> str:
        if address:
            return address
        parts = [p for p in [street, city, state, postalcode, country] if p]
        return ", ".join(parts) if parts else "(unspecified)"

    # ---- providers -----------------------------------------------------------
    async def geocode(
        self,
        *,
        address: Optional[str] = None,
        street: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        postalcode: Optional[str] = None,
    ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        params = {
            "format": "jsonv2",
            "limit": 1,
            "accept-language": self.lang,
            "addressdetails": 0,
        }
        if any([street, city, state, country, postalcode]):
            if street: params["street"] = street
            if city: params["city"] = city
            if state: params["state"] = state
            if country: params["country"] = country
            if postalcode: params["postalcode"] = postalcode
        elif address and address.strip():
            params["q"] = address.strip()
        else:
            return None, None, None  # no input → no result

        async with self._get_session().get(self.nominatim_url, params=params, timeout=self.request_timeout) as r:
            data = await r.json()

        if not data:
            return None, None, None

        lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
        display = data[0].get(
            "display_name",
            self._addr_label(
                address=address, street=street, city=city,
                state=state, country=country, postalcode=postalcode
            )
        )
        return lat, lon, display

    @staticmethod
    def _normalize_type(facility_type: str) -> str:
        ft = facility_type.strip().lower()
        if ft in {"hospital", "apotek"}:
            return ft
        if ft == "pharmacy":
            return "apotek"
        raise ValueError("facility_type must be 'hospital' or 'apotek'")

    def build_overpass_query(self, lat: float, lon: float, radius_m: int, facility_type: str) -> str:
        ft = self._normalize_type(facility_type)
        if ft == "hospital":
            body = """
              node["amenity"="hospital"](around:{r},{lat},{lon});
              way["amenity"="hospital"](around:{r},{lat},{lon});
              relation["amenity"="hospital"](around:{r},{lat},{lon});
              node["healthcare"="hospital"](around:{r},{lat},{lon});
              way["healthcare"="hospital"](around:{r},{lat},{lon});
              relation["healthcare"="hospital"](around:{r},{lat},{lon});
            """.format(r=radius_m, lat=lat, lon=lon)
        else:  # apotek / pharmacy
            body = """
              node["amenity"="pharmacy"](around:{r},{lat},{lon});
              way["amenity"="pharmacy"](around:{r},{lat},{lon});
              relation["amenity"="pharmacy"](around:{r},{lat},{lon});
              node["healthcare"="pharmacy"](around:{r},{lat},{lon});
              way["healthcare"="pharmacy"](around:{r},{lat},{lon});
              relation["healthcare"="pharmacy"](around:{r},{lat},{lon});
              node["shop"="chemist"](around:{r},{lat},{lon});
              way["shop"="chemist"](around:{r},{lat},{lon});
              relation["shop"="chemist"](around:{r},{lat},{lon});
            """.format(r=radius_m, lat=lat, lon=lon)
        return f"[out:json][timeout:25];({body});out center tags;"

    async def query_places(self, lat: float, lon: float, radius_m: int, facility_type: str) -> List[Dict]:
        q = self.build_overpass_query(lat, lon, radius_m, facility_type)
        async with self._get_session().post(self.overpass_url, data=q.encode("utf-8"), timeout=self.overpass_timeout) as r:
            data = await r.json()
        elements = data.get("elements", [])
        results: List[Dict] = []
        for el in elements:
            tags = el.get("tags", {}) or {}
            if "lat" in el and "lon" in el:
                plat, plon = float(el["lat"]), float(el["lon"])
            elif "center" in el and isinstance(el["center"], dict):
                plat, plon = float(el["center"]["lat"]), float(el["center"]["lon"])
            else:
                continue
            name = tags.get("name") or tags.get("official_name") or tags.get("operator") or "Unnamed"
            addr = ", ".join(v for k, v in tags.items() if k.startswith("addr:") and isinstance(v, str))
            results.append({
                "id": f"{el.get('type')}/{el.get('id')}",
                "name": name,
                "lat": plat,
                "lon": plon,
                "address": addr,
                "tags": tags,
            })
        uniq, seen = [], set()
        for r_ in results:
            if r_["id"] not in seen:
                seen.add(r_["id"])
                uniq.append(r_)
        return uniq

    @staticmethod
    def map_result(bundle: dict) -> list[str]:
        if not bundle or "results" not in bundle:
            return []

        mapped = []
        print(bundle["results"])
        for r in bundle["results"]:
            tags = r.get("tags", {}) or {}
            name = (
                tags.get("name")
                or tags.get("name:en")
                or tags.get("operator")
                or "Tidak bernama"
            )
            kind = r.get("kind", "fasilitas")
            if "hospital" in kind:
                kind = ""  # drop redundant word
            distance = r.get("distance_km")

            if distance is not None:
                mapped.append(f"{kind} {name} jarak {distance} km")
            else:
                mapped.append(f"{kind} {name}")
        return mapped


    # ---- public API ----------------------------------------------------------
    async def search(
        self,
        *,
        facility_type: str,
        radius_m: int = 5000,
        limit: int = 5,
        address: Optional[str] = None,
        street: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        postalcode: Optional[str] = None,
    ) -> List[str]:
        lat, lon, display = await self.geocode(
            address=address, street=street, city=city, state=state,
            country=country, postalcode=postalcode
        )

        # 🚨 If geocode failed → return empty
        if not lat or not lon:
            return []

        if self.polite_sleep > 0:
            await asyncio.sleep(self.polite_sleep)

        places = await self.query_places(lat, lon, radius_m, facility_type)
        for p in places:
            p["distance_km"] = round(self.haversine_km(lat, lon, p["lat"], p["lon"]), 3)
            p["kind"] = self._normalize_type(facility_type)

        places.sort(key=lambda x: x["distance_km"])
        final_result = {
            "query_address": self._addr_label(
                address=address, street=street, city=city,
                state=state, country=country, postalcode=postalcode
            ),
            "resolved_address": display,
            "origin": {"lat": lat, "lon": lon},
            "facility_type": self._normalize_type(facility_type),
            "radius_m": radius_m,
            "results": places[: max(0, limit)],
        }

        return self.map_result(final_result)



    @staticmethod
    def to_json(bundle: Dict) -> str:
        return json.dumps(bundle, indent=2, ensure_ascii=False)

    def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self._user_agent()}
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ---- CLI ---------------------------------------------------------------------
def _build_cli() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Find nearest hospitals or apotek using OpenStreetMap.")
    ap.add_argument("--type", choices=["hospital", "apotek"], default="hospital")
    ap.add_argument("--radius", type=int, default=5000)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--lang", default="id")
    ap.add_argument("--contact", default=os.getenv("OSM_CONTACT", "contact@example.com"))
    ap.add_argument("--address")
    ap.add_argument("--street")
    ap.add_argument("--city")
    ap.add_argument("--state")
    ap.add_argument("--country")
    ap.add_argument("--postal", dest="postalcode")

    args = ap.parse_args()
    if not args.address and not any([args.street, args.city, args.state, args.country, args.postalcode]):
        ap.error("Provide --address or one of --street/--city/--state/--country/--postal.")
    return args


async def main_async():
    args = _build_cli()
    finder = NearestFacilityFinder(contact_email=args.contact, lang=args.lang)
    try:
        bundle = await finder.search(
            facility_type=args.type,
            radius_m=args.radius,
            limit=args.limit,
            address=args.address,
            street=args.street,
            city=args.city,
            state=args.state,
            country=args.country,
            postalcode=args.postalcode,
        )
        print(bundle)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await finder.close()


if __name__ == "__main__":
    asyncio.run(main_async())
