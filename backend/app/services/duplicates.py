import hashlib, io, json, math, re
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..models import Complaint, DuplicateCluster, DuplicateClusterMember, Status
from .similarity import distance_m, score as legacy_score

EMBEDDING_SIZE=64

def perceptual_hash(data:bytes)->str:
    image=Image.open(io.BytesIO(data)).convert("L").resize((16,16))
    pixels=list(image.getdata());avg=sum(pixels)/len(pixels)
    return f"{int(''.join('1' if p>=avg else '0' for p in pixels),2):064x}"

def hamming_similarity(a:str|None,b:str|None)->float:
    if not a or not b:return 0.0
    try:return 1-(int(a,16)^int(b,16)).bit_count()/256
    except ValueError:return 0.0

def text_embedding(value:str)->list[float]:
    vector=[0.0]*EMBEDDING_SIZE
    for word in re.findall(r"[\w]+",value.lower(),flags=re.UNICODE):
        digest=hashlib.sha256(word.encode()).digest();index=int.from_bytes(digest[:2],"big")%EMBEDDING_SIZE;vector[index]+=1 if digest[2]%2 else -1
    norm=math.sqrt(sum(x*x for x in vector)) or 1
    return [round(x/norm,6) for x in vector]

def cosine(a:list[float],b:list[float])->float:
    return max(0.0,sum(x*y for x,y in zip(a,b)))

def encode_embedding(value:str)->str:return json.dumps(text_embedding(value),separators=(",",":"))
def decode_embedding(value:str|None)->list[float]:
    try:return json.loads(value) if value else []
    except (ValueError,TypeError):return []

def candidates(db:Session,lat:float,lon:float,radius:float)->list[Complaint]:
    if db.bind and db.bind.dialect.name=="postgresql":
        ids=db.execute(text("SELECT id FROM complaints WHERE status NOT IN ('resolved','rejected','duplicate') AND ST_DWithin(geo,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:radius)"),{"lat":lat,"lon":lon,"radius":radius}).scalars().all()
        return list(db.scalars(select(Complaint).where(Complaint.id.in_(ids))).all()) if ids else []
    lat_delta=radius/111320;lon_delta=radius/max(1,111320*math.cos(math.radians(lat)))
    return list(db.scalars(select(Complaint).where(Complaint.status.notin_([Status.resolved,Status.rejected,Status.duplicate]),Complaint.latitude.between(lat-lat_delta,lat+lat_delta),Complaint.longitude.between(lon-lon_delta,lon+lon_delta))).all())

def hybrid_score(candidate:Complaint,lat:float,lon:float,category:str,value:str,image_phash:str|None,radius:float)->tuple[float,float,dict]:
    base,dist=legacy_score(candidate,lat,lon,category,value,radius)
    query_embedding=text_embedding(value);stored=decode_embedding(candidate.text_embedding) or text_embedding(candidate.title+" "+candidate.description)
    semantic=cosine(query_embedding,stored);image=hamming_similarity(image_phash,candidate.image_phash)
    final=min(1,base*.65+semantic*.25+image*.10)
    return round(final,3),dist,{"location_category_text":base,"semantic":round(semantic,3),"image":round(image,3)}

def ensure_cluster(db:Session,primary:Complaint)->DuplicateCluster:
    cluster=db.scalar(select(DuplicateCluster).where(DuplicateCluster.primary_complaint_id==primary.id))
    if not cluster:
        cluster=DuplicateCluster(primary_complaint_id=primary.id,category=primary.category,latitude=primary.latitude,longitude=primary.longitude,total_support_count=primary.support_count);db.add(cluster);db.flush();db.add(DuplicateClusterMember(cluster_id=cluster.id,complaint_id=primary.id,similarity_score=1,distance_m=0))
    return cluster

def refresh_cluster(db:Session,cluster:DuplicateCluster):
    members=list(db.scalars(select(DuplicateClusterMember).where(DuplicateClusterMember.cluster_id==cluster.id)).all());cluster.member_count=len(members)
    complaints=list(db.scalars(select(Complaint).where(Complaint.id.in_([m.complaint_id for m in members]))).all())
    cluster.total_support_count=sum(c.support_count for c in complaints)
