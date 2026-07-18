import math, re
from datetime import datetime, timezone

def distance_m(a,b,c,d):
    r=6371000; p1=math.radians(a); p2=math.radians(c); dp=math.radians(c-a); dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return r*2*math.atan2(math.sqrt(x),math.sqrt(1-x))
def words(s): return set(re.findall(r"[a-z0-9]+",s.lower()))
def score(candidate, lat, lon, category, text, radius=300):
    dist=distance_m(lat,lon,candidate.latitude,candidate.longitude)
    geo=max(0,1-dist/radius); cat=1 if candidate.category.lower()==category.lower() else 0
    a,b=words(text),words(candidate.title+" "+candidate.description); txt=len(a&b)/max(1,len(a|b))
    created=candidate.created_at.replace(tzinfo=timezone.utc) if candidate.created_at.tzinfo is None else candidate.created_at
    days=max(0,(datetime.now(timezone.utc)-created).days); recency=max(0,1-days/90)
    return round(.4*geo+.35*cat+.15*txt+.1*recency,3),round(dist,1)

