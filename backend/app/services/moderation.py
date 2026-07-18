import re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..models import Comment, Complaint, ComplaintSupport

ABUSE={"kill yourself","rape","terrorist threat","explicit sexual","child sexual"}
PHONE=re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)")
EMAIL=re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",re.I)
AADHAAR=re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")

def mask_pii(value:str)->str:
    value=EMAIL.sub("[email hidden]",value);value=PHONE.sub("[phone hidden]",value);return AADHAAR.sub("[identity number hidden]",value)

def validate_content(value:str):
    normalized=" ".join(value.lower().split())
    if any(term in normalized for term in ABUSE):raise HTTPException(422,"Content violates CivicLens safety rules")
    if len(set(re.findall(r"\w+",normalized)))<2:raise HTTPException(422,"Please provide meaningful civic context")

def guard_complaint_spam(db:Session,user_id:str,title:str,description:str):
    since=datetime.now(timezone.utc)-timedelta(minutes=10);recent=db.scalars(select(Complaint).where(Complaint.reporter_id==user_id,Complaint.created_at>=since)).all()
    if len(recent)>=3:raise HTTPException(429,"Too many reports submitted in a short period")
    normalized=lambda value:" ".join(re.findall(r"\w+",value.lower()))
    incoming=normalized(title+" "+description)
    if any(normalized(x.title+" "+x.description)==incoming for x in recent):raise HTTPException(409,"This report appears to be a recent duplicate")

def guard_comment_spam(db:Session,user_id:str,content:str):
    since=datetime.now(timezone.utc)-timedelta(minutes=5);recent=db.scalars(select(Comment).where(Comment.user_id==user_id,Comment.created_at>=since)).all()
    if len(recent)>=5:raise HTTPException(429,"Too many comments submitted in a short period")
    if any(x.content.lower().strip()==content.lower().strip() for x in recent):raise HTTPException(409,"Duplicate comment")

def guard_support(db:Session,user_id:str,complaint:Complaint):
    since=datetime.now(timezone.utc)-timedelta(hours=1);count=db.scalar(select(func.count()).select_from(ComplaintSupport).where(ComplaintSupport.user_id==user_id,ComplaintSupport.created_at>=since)) or 0
    if count>=20:raise HTTPException(429,"Unusual support activity detected; please try again later")
