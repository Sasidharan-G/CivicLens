import hashlib,secrets
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..models import AuthToken,User

def _hash(token:str)->str:return hashlib.sha256(token.encode()).hexdigest()
def issue(db:Session,user:User,purpose:str,ttl:timedelta)->str:
    raw=secrets.token_urlsafe(48); db.add(AuthToken(user_id=user.id,token_hash=_hash(raw),purpose=purpose,expires_at=datetime.now(timezone.utc)+ttl));db.flush();return raw
def consume(db:Session,raw:str,purpose:str,mark_used=True)->AuthToken|None:
    record=db.scalar(select(AuthToken).where(AuthToken.token_hash==_hash(raw),AuthToken.purpose==purpose,AuthToken.used_at.is_(None),AuthToken.revoked_at.is_(None)))
    if not record:return None
    expiry=record.expires_at.replace(tzinfo=timezone.utc) if record.expires_at.tzinfo is None else record.expires_at
    if expiry<=datetime.now(timezone.utc):return None
    if mark_used:record.used_at=datetime.now(timezone.utc)
    return record
def issue_session(db:Session,user:User)->str:return issue(db,user,"refresh",timedelta(days=settings.refresh_token_expire_days))
def revoke_user_sessions(db:Session,user_id:str):
    now=datetime.now(timezone.utc)
    for token in db.scalars(select(AuthToken).where(AuthToken.user_id==user_id,AuthToken.purpose=="refresh",AuthToken.revoked_at.is_(None))).all():token.revoked_at=now

