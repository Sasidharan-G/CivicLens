import json
from datetime import datetime,timedelta,timezone
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..models import GeocodeCache

def cache_key(lat:float,lon:float)->str:return f"{round(lat,5)}:{round(lon,5)}"
async def reverse_geocode(db:Session,lat:float,lon:float)->dict:
    key=cache_key(lat,lon); cached=db.scalar(select(GeocodeCache).where(GeocodeCache.cache_key==key))
    if cached:
        created=cached.created_at.replace(tzinfo=timezone.utc) if cached.created_at.tzinfo is None else cached.created_at
        if created>datetime.now(timezone.utc)-timedelta(days=settings.geocoding_cache_days):return {**json.loads(cached.response_json),"cached":True}
    fallback={"address":f"{lat:.5f}, {lon:.5f}","locality":None,"ward":None,"postal_code":None,"source":"coordinates","cached":False}
    if not settings.geocoding_enabled:return fallback
    try:
        async with httpx.AsyncClient(timeout=8,headers={"User-Agent":settings.geocoding_user_agent}) as client:
            response=await client.get("https://nominatim.openstreetmap.org/reverse",params={"lat":lat,"lon":lon,"format":"jsonv2","addressdetails":1});response.raise_for_status();raw=response.json();a=raw.get("address",{})
        result={"address":raw.get("display_name") or fallback["address"],"locality":a.get("suburb") or a.get("city_district") or a.get("city"),"ward":a.get("borough") or a.get("quarter"),"postal_code":a.get("postcode"),"source":"openstreetmap","cached":False}
        if cached:cached.response_json=json.dumps(result);cached.created_at=datetime.now(timezone.utc)
        else:db.add(GeocodeCache(cache_key=key,latitude=lat,longitude=lon,response_json=json.dumps(result)))
        db.commit();return result
    except (httpx.HTTPError,ValueError):return fallback

