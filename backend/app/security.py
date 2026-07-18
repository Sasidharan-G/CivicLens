from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import hashlib, hmac, secrets
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Role, User

oauth2=OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def hash_password(v:str)->str:
    salt=secrets.token_bytes(16); rounds=310000; digest=hashlib.pbkdf2_hmac("sha256",v.encode(),salt,rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"
def verify_password(v:str,h:str)->bool:
    try:
        scheme,rounds,salt,digest=h.split("$")
        if scheme!="pbkdf2_sha256": return False
        check=hashlib.pbkdf2_hmac("sha256",v.encode(),bytes.fromhex(salt),int(rounds)).hex()
        return hmac.compare_digest(check,digest)
    except (ValueError,TypeError): return False
def create_token(user:User)->str:
    exp=datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub":user.id,"role":user.role.value,"type":"access","iat":datetime.now(timezone.utc),"exp":exp},settings.jwt_secret_key,algorithm="HS256")
def authenticated_user(token:str=Depends(oauth2), db:Session=Depends(get_db))->User:
    err=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Authentication required",headers={"WWW-Authenticate":"Bearer"})
    try:
        payload=jwt.decode(token,settings.jwt_secret_key,algorithms=["HS256"]);uid=payload.get("sub")
        if payload.get("type")!="access":raise err
    except JWTError: raise err
    user=db.get(User,uid) if uid else None
    if not user: raise err
    return user
def current_user(user:User=Depends(authenticated_user))->User:
    if not user.is_active:raise HTTPException(403,"Account suspended. You may submit an appeal to the grievance team.")
    return user
def admin_user(user:User=Depends(current_user))->User:
    if user.role != Role.admin: raise HTTPException(403,"Admin access required")
    return user
