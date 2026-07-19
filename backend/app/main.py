import csv
import io
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from .config import settings
from .database import Base, engine, get_db
from .models import AuditLog, Comment, Complaint, ComplaintMedia, ComplaintStatusEvent, ComplaintSupport, DuplicateCluster, DuplicateClusterMember, InternalNote, ModerationReport, Notification, NotificationPreference, PushSubscription, Role, Severity, Status, SuspensionAppeal, User, UserBlock
from .schemas import AppealCreate, AppealReview, AssignUpdate, BulkAssignUpdate, BulkStatusUpdate, CommentCreate, ComplaintCreate, EmailRequest, ForgotPassword, InternalNoteCreate, LetterRequest, Login, MergeRequest, ModerationReportCreate, ModerationReview, NotificationPreferenceUpdate, PushSubscriptionCreate, RefreshRequest, ReopenRequest, ResetPassword, ResolutionUpdate, SimilarRequest, StatusUpdate, Token, TokenAction, UserBlockCreate, UserCreate, UserOut
from .security import admin_user, authenticated_user, create_token, current_user, hash_password, verify_password
from .services.ai import ai
from .services.audit import record as audit
from .services.auth_tokens import consume, issue, issue_session, revoke_user_sessions
from .services.geocoding import reverse_geocode
from .services.email import send_password_reset, send_verification
from .services.notifications import dispatch as dispatch_notification, preference as notification_preference
from .services.moderation import guard_comment_spam, guard_complaint_spam, guard_support, mask_pii, validate_content
from .services.duplicates import candidates, encode_embedding, ensure_cluster, hybrid_score, perceptual_hash, refresh_cluster, text_embedding
from .services.storage import storage
from .services.categories import guidance
from .services.workflow import is_overdue, transition
from .middleware import SecurityHeadersMiddleware, SimpleRateLimitMiddleware

if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.sentry_dsn,environment=settings.environment,traces_sample_rate=.1,send_default_pii=False)
@asynccontextmanager
async def lifespan(app:FastAPI):
    # Vercel's managed database credentials are only available inside the
    # deployed runtime.  Keep startup idempotent so a fresh production
    # database is initialized on the first cold start as well as locally.
    Base.metadata.create_all(engine)
    yield
app=FastAPI(title="CivicLens API",version="1.1.0",description="AI-powered civic issue reporting API",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.add_middleware(SimpleRateLimitMiddleware);app.add_middleware(SecurityHeadersMiddleware)
Path(settings.upload_dir).mkdir(parents=True,exist_ok=True); app.mount("/uploads",StaticFiles(directory=settings.upload_dir),name="uploads")
@app.get("/", include_in_schema=False)
def root(): return {"service":"CivicLens API","status":"running","docs":"/docs","health":"/api/health"}

def user_dict(u): return {"id":u.id,"full_name":u.full_name,"email":u.email,"role":u.role.value,"locality":u.locality}
def complaint_dict(c, detail=False):
    lat=round(c.latitude,3) if c.hide_exact_location else c.latitude;lon=round(c.longitude,3) if c.hide_exact_location else c.longitude
    d={"id":c.id,"reference_number":c.reference_number,"title":c.title,"description":c.description,"category":c.category,"severity":c.severity.value,"status":c.status.value,"confidence_score":c.confidence_score,"department":c.department,"assigned_to_id":c.assigned_to_id,"image_url":c.image_url,"latitude":lat,"longitude":lon,"address":c.locality if c.hide_exact_location else c.address,"locality":c.locality,"ward":c.ward,"postal_code":c.postal_code,"complaint_letter":c.complaint_letter,"support_count":c.support_count,"reporter_id":None if c.is_anonymous else c.reporter_id,"is_anonymous":c.is_anonymous,"hide_exact_location":c.hide_exact_location,"sla_due_at":c.sla_due_at,"is_overdue":is_overdue(c),"resolution_summary":c.resolution_summary,"citizen_confirmed_at":c.citizen_confirmed_at,"reopened_count":c.reopened_count,"media":[{"id":m.id,"url":m.url,"media_type":m.media_type,"mime_type":m.mime_type,"created_at":m.created_at} for m in c.media],"created_at":c.created_at,"updated_at":c.updated_at}
    if detail:
        d["reporter"]={"full_name":"Anonymous citizen" if c.is_anonymous else c.reporter.full_name}; d["timeline"]=[{"id":e.id,"previous_status":e.previous_status.value if e.previous_status else None,"new_status":e.new_status.value,"note":e.note,"created_at":e.created_at} for e in c.events]; d["comments"]=[{"id":x.id,"content":x.content,"is_official":x.is_official,"created_at":x.created_at,"author":x.user.full_name,"user_id":x.user_id} for x in c.comments if not x.is_hidden]
    return d
def reference(db):
    year=datetime.now().year; n=db.scalar(select(func.count()).select_from(Complaint))+1
    while db.scalar(select(Complaint).where(Complaint.reference_number==f"CIV-{year}-{n:06d}")): n+=1
    return f"CIV-{year}-{n:06d}"

@app.get("/api/health")
def health(db:Session=Depends(get_db)):
    db.execute(select(1));return {"status":"healthy","service":"CivicLens API","version":"1.1.0","database":"connected","ai_mode":"live" if settings.ai_api_key else "demo","storage":"cloudinary" if storage.cloudinary_ready else "local"}
@app.get("/api/ready")
def ready(response:Response,db:Session=Depends(get_db)):
    db.execute(select(1));errors,warnings=settings.readiness();response.status_code=503 if errors else 200
    return {"status":"not_ready" if errors else "ready","environment":settings.environment,"database":"connected","checks":{"durable_storage":storage.cloudinary_ready,"email_delivery":bool(settings.smtp_host),"error_monitoring":bool(settings.sentry_dsn)},"errors":errors,"warnings":warnings}
def auth_response(db:Session,u:User):
    refresh=issue_session(db,u);db.commit();return {"access_token":create_token(u),"refresh_token":refresh,"expires_in":settings.jwt_expire_minutes*60,"user":u}
@app.post("/api/auth/register",response_model=Token,status_code=201)
def register(data:UserCreate,request:Request,tasks:BackgroundTasks,db:Session=Depends(get_db)):
    if not data.accept_terms or not data.accept_privacy:raise HTTPException(422,"Terms and privacy consent are required")
    if db.scalar(select(User).where(func.lower(User.email)==data.email.lower())): raise HTTPException(409,"An account already exists with this email")
    accepted=datetime.now(timezone.utc);u=User(full_name=data.full_name.strip(),email=data.email.lower(),password_hash=hash_password(data.password),phone=data.phone,locality=data.locality,terms_accepted_at=accepted,privacy_accepted_at=accepted); db.add(u); db.flush();verification=issue(db,u,"verify_email",timedelta(hours=24));audit(db,"auth.register",u.id,"user",u.id,ip_address=request.client.host if request.client else None);db.commit(); db.refresh(u);tasks.add_task(send_verification,u.email,verification)
    return auth_response(db,u)
@app.post("/api/auth/login",response_model=Token)
def login(data:Login,request:Request,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(func.lower(User.email)==data.email.lower()))
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,"Invalid email or password")
    if not u.is_active:raise HTTPException(403,"Account suspended. Use your existing session token to submit an appeal.")
    audit(db,"auth.login",u.id,"user",u.id,ip_address=request.client.host if request.client else None);return auth_response(db,u)
@app.post("/api/auth/refresh",response_model=Token)
def refresh(data:RefreshRequest,db:Session=Depends(get_db)):
    token=consume(db,data.refresh_token,"refresh")
    if not token:raise HTTPException(401,"Invalid or expired refresh token")
    u=db.get(User,token.user_id)
    if not u or not u.is_active:raise HTTPException(401,"Account unavailable")
    return auth_response(db,u)
@app.post("/api/auth/logout",status_code=204)
def logout(data:RefreshRequest,db:Session=Depends(get_db)):
    consume(db,data.refresh_token,"refresh");db.commit()
@app.post("/api/auth/forgot-password")
def forgot_password(data:ForgotPassword,tasks:BackgroundTasks,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(func.lower(User.email)==data.email.lower()));result={"message":"If this account exists, reset instructions have been prepared."}
    if u:
        raw=issue(db,u,"password_reset",timedelta(minutes=30));audit(db,"auth.password_reset_requested",u.id,"user",u.id);db.commit();tasks.add_task(send_password_reset,u.email,raw)
        if not settings.is_production:result["development_token"]=raw
    return result
@app.post("/api/auth/reset-password")
def reset_password(data:ResetPassword,db:Session=Depends(get_db)):
    token=consume(db,data.token,"password_reset")
    if not token:raise HTTPException(400,"Invalid or expired reset token")
    u=db.get(User,token.user_id);u.password_hash=hash_password(data.new_password);revoke_user_sessions(db,u.id);audit(db,"auth.password_reset",u.id,"user",u.id);db.commit();return {"message":"Password updated. Please log in again."}
@app.post("/api/auth/request-verification")
def request_verification(data:EmailRequest,tasks:BackgroundTasks,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(func.lower(User.email)==data.email.lower()));result={"message":"If verification is required, instructions have been prepared."}
    if u and not u.is_email_verified:
        raw=issue(db,u,"verify_email",timedelta(hours=24));db.commit();tasks.add_task(send_verification,u.email,raw)
        if not settings.is_production:result["development_token"]=raw
    return result
@app.post("/api/auth/verify-email")
def verify_email(data:TokenAction,db:Session=Depends(get_db)):
    token=consume(db,data.token,"verify_email")
    if not token:raise HTTPException(400,"Invalid or expired verification token")
    u=db.get(User,token.user_id);u.is_email_verified=True;audit(db,"auth.email_verified",u.id,"user",u.id);db.commit();return {"message":"Email verified successfully."}
@app.get("/api/auth/me",response_model=UserOut)
def me(u:User=Depends(current_user)): return u

@app.get("/api/notifications")
def notifications(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),unread_only:bool=False,db:Session=Depends(get_db),u:User=Depends(current_user)):
    filters=[Notification.user_id==u.id]
    if unread_only:filters.append(Notification.is_read.is_(False))
    total=db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0;unread=db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==u.id,Notification.is_read.is_(False))) or 0
    rows=db.scalars(select(Notification).where(*filters).order_by(Notification.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items":[{"id":x.id,"title":x.title,"message":x.message,"kind":x.kind,"is_read":x.is_read,"complaint_id":x.complaint_id,"created_at":x.created_at} for x in rows],"total":total,"unread":unread,"page":page}

@app.patch("/api/notifications/{id}/read")
def read_notification(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=db.scalar(select(Notification).where(Notification.id==id,Notification.user_id==u.id))
    if not item:raise HTTPException(404,"Notification not found")
    item.is_read=True;db.commit();return {"id":item.id,"is_read":True}

@app.post("/api/notifications/read-all")
def read_all_notifications(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rows=db.scalars(select(Notification).where(Notification.user_id==u.id,Notification.is_read.is_(False))).all()
    for item in rows:item.is_read=True
    db.commit();return {"updated":len(rows)}

def preference_dict(item:NotificationPreference):return {"email_enabled":item.email_enabled,"push_enabled":item.push_enabled,"whatsapp_enabled":item.whatsapp_enabled,"status_alerts":item.status_alerts,"nearby_critical_alerts":item.nearby_critical_alerts,"ward_digest":item.ward_digest,"vapid_public_key":settings.vapid_public_key}
@app.get("/api/notification-preferences")
def get_notification_preferences(db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=notification_preference(db,u.id);db.commit();return preference_dict(item)
@app.put("/api/notification-preferences")
def update_notification_preferences(data:NotificationPreferenceUpdate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=notification_preference(db,u.id)
    for key,value in data.model_dump().items():setattr(item,key,value)
    db.commit();return preference_dict(item)
@app.post("/api/push-subscriptions",status_code=201)
def subscribe_push(data:PushSubscriptionCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=db.scalar(select(PushSubscription).where(PushSubscription.endpoint==data.endpoint))
    if item:item.user_id=u.id;item.p256dh=data.p256dh;item.auth=data.auth
    else:item=PushSubscription(user_id=u.id,**data.model_dump());db.add(item)
    pref=notification_preference(db,u.id);pref.push_enabled=True;db.commit();return {"subscribed":True}
@app.delete("/api/push-subscriptions")
def unsubscribe_push(endpoint:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=db.scalar(select(PushSubscription).where(PushSubscription.endpoint==endpoint,PushSubscription.user_id==u.id))
    if item:db.delete(item);db.commit()
    return {"subscribed":False}

@app.post("/api/moderation/reports",status_code=201)
def report_content(data:ModerationReportCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    target={"comment":Comment,"complaint":Complaint,"user":User}[data.target_type]
    if not db.get(target,data.target_id):raise HTTPException(404,"Reported item not found")
    item=ModerationReport(reporter_id=u.id,**data.model_dump());db.add(item)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,"You have already reported this item")
    db.refresh(item);return {"id":item.id,"status":item.status}
@app.post("/api/users/block",status_code=201)
def block_user(data:UserBlockCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if data.user_id==u.id:raise HTTPException(400,"You cannot block yourself")
    if not db.get(User,data.user_id):raise HTTPException(404,"User not found")
    item=UserBlock(blocker_id=u.id,blocked_id=data.user_id);db.add(item)
    try:db.commit()
    except IntegrityError:db.rollback()
    return {"blocked":True,"user_id":data.user_id}
@app.delete("/api/users/block/{user_id}")
def unblock_user(user_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=db.scalar(select(UserBlock).where(UserBlock.blocker_id==u.id,UserBlock.blocked_id==user_id))
    if item:db.delete(item);db.commit()
    return {"blocked":False,"user_id":user_id}
@app.post("/api/moderation/appeals",status_code=201)
def appeal_suspension(data:AppealCreate,db:Session=Depends(get_db),u:User=Depends(authenticated_user)):
    if u.is_active:raise HTTPException(409,"Only suspended accounts can appeal")
    if db.scalar(select(SuspensionAppeal).where(SuspensionAppeal.user_id==u.id,SuspensionAppeal.status=="pending")):raise HTTPException(409,"A pending appeal already exists")
    item=SuspensionAppeal(user_id=u.id,message=mask_pii(data.message));db.add(item);db.commit();db.refresh(item);return {"id":item.id,"status":item.status}
@app.get("/api/admin/moderation")
def moderation_queue(status:str="pending",db:Session=Depends(get_db),u:User=Depends(admin_user)):
    reports=db.scalars(select(ModerationReport).where(ModerationReport.status==status).order_by(ModerationReport.created_at)).all();appeals=db.scalars(select(SuspensionAppeal).where(SuspensionAppeal.status==status).order_by(SuspensionAppeal.created_at)).all()
    return {"reports":[{"id":x.id,"target_type":x.target_type,"target_id":x.target_id,"reason":x.reason,"details":x.details,"status":x.status,"created_at":x.created_at} for x in reports],"appeals":[{"id":x.id,"user_id":x.user_id,"message":x.message,"status":x.status,"created_at":x.created_at} for x in appeals]}
@app.patch("/api/admin/moderation/reports/{id}")
def review_report(id:str,data:ModerationReview,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    item=db.get(ModerationReport,id)
    if not item:raise HTTPException(404,"Moderation report not found")
    if data.action=="hide":
        if item.target_type=="comment":
            target=db.get(Comment,item.target_id)
            if target:target.is_hidden=True
        elif item.target_type=="complaint":
            target=db.get(Complaint,item.target_id)
            if target:target.status=Status.rejected
    if data.action=="suspend":
        target=db.get(User,item.target_id) if item.target_type=="user" else None
        if item.target_type=="comment":
            comment_target=db.get(Comment,item.target_id);target=db.get(User,comment_target.user_id) if comment_target else None
        if target:target.is_active=False;target.suspended_at=datetime.now(timezone.utc);target.suspension_reason=data.note;revoke_user_sessions(db,target.id)
    if data.action=="restore" and item.target_type=="user":
        target=db.get(User,item.target_id)
        if target:target.is_active=True;target.suspended_at=None;target.suspension_reason=None
    item.status="dismissed" if data.action=="dismiss" else "actioned";item.reviewed_by_id=u.id;item.review_note=data.note;item.reviewed_at=datetime.now(timezone.utc);audit(db,"moderation.report_reviewed",u.id,item.target_type,item.target_id,{"action":data.action});db.commit();return {"id":item.id,"status":item.status,"action":data.action}
@app.patch("/api/admin/moderation/appeals/{id}")
def review_appeal(id:str,data:AppealReview,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    item=db.get(SuspensionAppeal,id)
    if not item:raise HTTPException(404,"Appeal not found")
    user=db.get(User,item.user_id);item.status="approved" if data.approve else "rejected";item.review_note=data.note;item.reviewed_by_id=u.id;item.reviewed_at=datetime.now(timezone.utc)
    if data.approve:user.is_active=True;user.suspended_at=None;user.suspension_reason=None
    db.commit();return {"id":item.id,"status":item.status}

@app.post("/api/complaints/analyze")
async def analyze(file:UploadFile=File(...),u:User=Depends(current_user)):
    allowed={"image/jpeg","image/png","image/webp"}
    if file.content_type not in allowed: raise HTTPException(400,"Only JPEG, PNG and WebP images are allowed")
    data=await file.read()
    if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"Image is too large")
    try:data=storage.sanitize(data,file.content_type)
    except ValueError as error:raise HTTPException(400,str(error))
    result=await ai.analyze_issue_image(data,file.filename or "issue.jpg")
    if result.get("is_safe") is False:raise HTTPException(422,"Image did not pass CivicLens safety moderation")
    safe={k:result.get(k) for k in ("category","title","description","severity","confidence_score","department","safety_warning","moderation_labels","is_demo")}; safe["severity"]=safe["severity"] if safe["severity"] in [x.value for x in Severity] else "medium"
    saved=storage.upload(data,file.content_type);safe["image_url"]=saved.url;safe["image_public_id"]=saved.public_id;safe["image_phash"]=perceptual_hash(data);safe["storage_provider"]=saved.provider; return safe
@app.post("/api/complaints/media",status_code=201)
async def upload_media(files:list[UploadFile]=File(...),u:User=Depends(current_user)):
    if not files or len(files)>5:raise HTTPException(400,"Upload between 1 and 5 images")
    out=[]
    for file in files:
        if file.content_type not in {"image/jpeg","image/png","image/webp"}:raise HTTPException(400,"Only JPEG, PNG and WebP images are allowed")
        data=await file.read()
        if len(data)>settings.max_upload_mb*1024*1024:raise HTTPException(413,f"{file.filename} is too large")
        try:data=storage.sanitize(data,file.content_type)
        except ValueError as error:raise HTTPException(400,str(error))
        saved=storage.upload(data,file.content_type);out.append({"url":saved.url,"public_id":saved.public_id,"mime_type":file.content_type,"provider":saved.provider})
    return {"items":out}
@app.get("/api/categories/{category}/guidance")
def category_guidance(category:str):return guidance(category)
@app.get("/api/location/reverse")
async def geocode(latitude:float=Query(ge=-90,le=90),longitude:float=Query(ge=-180,le=180),db:Session=Depends(get_db),u:User=Depends(current_user)):return await reverse_geocode(db,latitude,longitude)
@app.post("/api/complaints/generate-letter")
async def letter(data:LetterRequest,u:User=Depends(current_user)): return {"letter":await ai.generate_complaint_letter(data),"is_demo":not bool(settings.ai_api_key)}
@app.post("/api/complaints/similar")
def similar(data:SimilarRequest,db:Session=Depends(get_db)):
    radius=data.radius_m or settings.similarity_radius_m; rows=candidates(db,data.latitude,data.longitude,radius); out=[]
    for c in rows:
        s,dist,signals=hybrid_score(c,data.latitude,data.longitude,data.category,data.title+" "+data.description,data.image_phash,radius)
        if dist<=radius and s>=settings.similarity_threshold: out.append({**complaint_dict(c),"similarity_score":s,"distance_m":dist,"signals":signals,"recommendation":"support_existing" if s>=.62 else "review"})
    return sorted(out,key=lambda x:x["similarity_score"],reverse=True)
@app.post("/api/complaints",status_code=201)
def create_complaint(data:ComplaintCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    validate_content(data.title+" "+data.description);guard_complaint_spam(db,u.id,data.title,data.description);values=data.model_dump(exclude={"media"});media=data.media;values["title"]=mask_pii(values["title"]);values["description"]=mask_pii(values["description"]);values["address"]=mask_pii(values["address"]) if values.get("address") else None;values["text_embedding"]=encode_embedding(values["title"]+" "+values["description"]);c=Complaint(**values,reference_number=reference(db),reporter_id=u.id); db.add(c); db.flush()
    if db.bind and db.bind.dialect.name=="postgresql":
        vector="["+",".join(str(x) for x in text_embedding(c.title+" "+c.description))+"]";db.execute(text("UPDATE complaints SET geo=ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography, embedding=CAST(:embedding AS vector) WHERE id=:id"),{"lon":c.longitude,"lat":c.latitude,"embedding":vector,"id":c.id})
    for item in media:db.add(ComplaintMedia(complaint_id=c.id,url=item.url,public_id=item.public_id,mime_type=item.mime_type,media_type="issue",uploaded_by_id=u.id))
    if not media and c.image_url:db.add(ComplaintMedia(complaint_id=c.id,url=c.image_url,public_id=c.image_public_id,mime_type="image/jpeg",media_type="issue",uploaded_by_id=u.id))
    if c.severity==Severity.critical and (c.ward or c.locality):
        nearby=db.scalars(select(User).where(User.id!=u.id,User.is_active.is_(True),or_(User.ward==c.ward if c.ward else False,User.locality==c.locality if c.locality else False))).all()
        for recipient in nearby:
            pref=notification_preference(db,recipient.id)
            if pref.nearby_critical_alerts:
                item=Notification(user_id=recipient.id,title="Critical issue reported nearby",message=f"{c.title} was reported in {c.ward or c.locality}.",kind="nearby_critical",complaint_id=c.id);db.add(item);db.flush();dispatch_notification(db,item,recipient)
    db.add(ComplaintStatusEvent(complaint_id=c.id,previous_status=None,new_status=Status.submitted,note="Complaint submitted by citizen",changed_by_id=u.id));audit(db,"complaint.created",u.id,"complaint",c.id,{"reference":c.reference_number,"anonymous":c.is_anonymous});db.commit();return complaint_dict(get_one(c.id,db))
@app.get("/api/complaints")
def list_complaints(page:int=Query(1,ge=1),page_size:int=Query(12,ge=1,le=100),search:str|None=None,status:str|None=None,category:str|None=None,severity:str|None=None,mine:bool=False,db:Session=Depends(get_db),u:User|None=Depends(current_user)):
    q=select(Complaint); filters=[]
    if search: filters.append(or_(Complaint.title.ilike(f"%{search}%"),Complaint.reference_number.ilike(f"%{search}%")))
    if status: filters.append(Complaint.status==status)
    if category: filters.append(Complaint.category==category)
    if severity: filters.append(Complaint.severity==severity)
    if mine: filters.append(Complaint.reporter_id==u.id)
    q=q.where(*filters); total=db.scalar(select(func.count()).select_from(q.subquery())); rows=db.scalars(q.order_by(Complaint.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all(); return {"items":[complaint_dict(x) for x in rows],"total":total,"page":page,"page_size":page_size}
def get_one(id,db):
    c=db.scalar(select(Complaint).options(selectinload(Complaint.reporter),selectinload(Complaint.events),selectinload(Complaint.media),selectinload(Complaint.comments).selectinload(Comment.user)).where(Complaint.id==id))
    if not c: raise HTTPException(404,"Complaint not found")
    return c
@app.get("/api/complaints/reference/{ref}")
def by_ref(ref:str,db:Session=Depends(get_db)):
    c=db.scalar(select(Complaint).where(Complaint.reference_number==ref));
    if not c: raise HTTPException(404,"Complaint not found")
    return complaint_dict(c)
@app.get("/api/complaints/{id}")
def detail(id:str,db:Session=Depends(get_db)): return complaint_dict(get_one(id,db),True)
@app.patch("/api/complaints/{id}")
def edit(id:str,data:ComplaintCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    c=get_one(id,db)
    if c.reporter_id!=u.id or c.status not in [Status.submitted,Status.verified]: raise HTTPException(403,"This complaint can no longer be edited")
    for k,v in data.model_dump(exclude={"media"}).items(): setattr(c,k,v)
    db.commit(); return complaint_dict(c)
@app.delete("/api/complaints/{id}",status_code=204)
def delete(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    c=get_one(id,db)
    if c.reporter_id!=u.id or c.status!=Status.submitted: raise HTTPException(403,"Only newly submitted complaints can be deleted")
    db.delete(c); db.commit()
@app.post("/api/complaints/{id}/support")
def support(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    c=get_one(id,db)
    if db.scalar(select(UserBlock.id).where(UserBlock.blocker_id==c.reporter_id,UserBlock.blocked_id==u.id)):raise HTTPException(403,"You cannot interact with this report")
    guard_support(db,u.id,c);db.add(ComplaintSupport(complaint_id=id,user_id=u.id))
    try: c.support_count+=1; db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,"You already support this complaint")
    return {"support_count":c.support_count,"supported":True}
@app.delete("/api/complaints/{id}/support")
def unsupport(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    x=db.scalar(select(ComplaintSupport).where(ComplaintSupport.complaint_id==id,ComplaintSupport.user_id==u.id)); c=get_one(id,db)
    if x: db.delete(x); c.support_count=max(0,c.support_count-1); db.commit()
    return {"support_count":c.support_count,"supported":False}
@app.get("/api/complaints/{id}/comments")
def comments(id:str,db:Session=Depends(get_db)): get_one(id,db); return [{"id":x.id,"content":x.content,"author":x.user.full_name,"is_official":x.is_official,"created_at":x.created_at} for x in db.scalars(select(Comment).options(selectinload(Comment.user)).where(Comment.complaint_id==id)).all()]
@app.post("/api/complaints/{id}/comments",status_code=201)
def comment(id:str,data:CommentCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    c=get_one(id,db)
    if db.scalar(select(UserBlock.id).where(UserBlock.blocker_id==c.reporter_id,UserBlock.blocked_id==u.id)):raise HTTPException(403,"You cannot interact with this report")
    validate_content(data.content);guard_comment_spam(db,u.id,data.content);content=mask_pii(data.content.strip());x=Comment(complaint_id=id,user_id=u.id,content=content,is_official=u.role==Role.admin); db.add(x); db.commit(); db.refresh(x); return {"id":x.id,"content":x.content,"author":u.full_name,"is_official":x.is_official,"created_at":x.created_at}
@app.post("/api/complaints/{id}/confirm-resolution")
def confirm_resolution(id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    c=get_one(id,db)
    if c.reporter_id!=u.id:raise HTTPException(403,"Only the reporter can confirm resolution")
    if c.status!=Status.resolved:raise HTTPException(409,"Complaint is not resolved yet")
    c.citizen_confirmed_at=datetime.now(timezone.utc);audit(db,"complaint.resolution_confirmed",u.id,"complaint",id);db.commit();return {"confirmed":True,"confirmed_at":c.citizen_confirmed_at}
@app.post("/api/complaints/{id}/reopen")
def reopen_complaint(id:str,data:ReopenRequest,db:Session=Depends(get_db),u:User=Depends(current_user)):
    c=get_one(id,db)
    if c.reporter_id!=u.id:raise HTTPException(403,"Only the reporter can reopen this complaint")
    if c.status!=Status.resolved:raise HTTPException(409,"Only resolved complaints can be reopened")
    transition(db,c,Status.in_progress,f"Reopened by citizen: {data.reason}",u);audit(db,"complaint.reopened",u.id,"complaint",id,{"reason":data.reason});db.commit();return complaint_dict(c)

@app.patch("/api/admin/complaints/{id}/status")
def change_status(id:str,data:StatusUpdate,tasks:BackgroundTasks,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    c=get_one(id,db)
    if data.status==Status.resolved and (not c.resolution_summary or not any(m.media_type=="resolution" for m in c.media)):raise HTTPException(409,"Add a resolution summary and evidence photo before resolving")
    old=transition(db,c,data.status,data.note,u);db.flush();item=db.scalar(select(Notification).where(Notification.user_id==c.reporter_id,Notification.complaint_id==c.id).order_by(Notification.created_at.desc()));pref=notification_preference(db,c.reporter_id)
    if pref.status_alerts and item:dispatch_notification(db,item,c.reporter)
    audit(db,"complaint.status_changed",u.id,"complaint",id,{"from":old.value,"to":data.status.value});db.commit();return complaint_dict(c)
@app.post("/api/admin/complaints/{id}/resolution-evidence",status_code=201)
async def resolution_evidence(id:str,file:UploadFile=File(...),db:Session=Depends(get_db),u:User=Depends(admin_user)):
    c=get_one(id,db)
    if file.content_type not in {"image/jpeg","image/png","image/webp"}:raise HTTPException(400,"Resolution evidence must be an image")
    data=await file.read()
    if len(data)>settings.max_upload_mb*1024*1024:raise HTTPException(413,"Image is too large")
    try:data=storage.sanitize(data,file.content_type)
    except ValueError as error:raise HTTPException(400,str(error))
    saved=storage.upload(data,file.content_type);m=ComplaintMedia(complaint_id=id,url=saved.url,public_id=saved.public_id,mime_type=file.content_type,media_type="resolution",uploaded_by_id=u.id);db.add(m);audit(db,"complaint.resolution_evidence_added",u.id,"complaint",id);db.commit();db.refresh(m);return {"id":m.id,"url":m.url,"media_type":m.media_type}
@app.patch("/api/admin/complaints/{id}/resolution")
def resolution_summary(id:str,data:ResolutionUpdate,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    c=get_one(id,db);c.resolution_summary=data.summary;audit(db,"complaint.resolution_summary_updated",u.id,"complaint",id);db.commit();return complaint_dict(c)
@app.get("/api/admin/audit-logs")
def audit_logs(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),u:User=Depends(admin_user)):
    rows=db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all();return [{"id":x.id,"action":x.action,"actor_id":x.actor_id,"entity_type":x.entity_type,"entity_id":x.entity_id,"metadata":x.metadata_json,"ip_address":x.ip_address,"created_at":x.created_at} for x in rows]
@app.patch("/api/admin/complaints/{id}/assign")
def assign(id:str,data:AssignUpdate,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    c=get_one(id,db);c.assigned_to_id=data.assigned_to_id;c.department=data.department;transition(db,c,Status.assigned,f"Assigned to {data.department}",u);audit(db,"complaint.assigned",u.id,"complaint",id,{"department":data.department,"officer":data.assigned_to_id});db.commit();return complaint_dict(c)
@app.get("/api/admin/officers")
def officers(db:Session=Depends(get_db),u:User=Depends(admin_user)):return [{"id":x.id,"full_name":x.full_name,"email":x.email,"department":x.department,"ward_scope":x.ward_scope} for x in db.scalars(select(User).where(User.role==Role.admin,User.is_active.is_(True)).order_by(User.full_name)).all()]
@app.get("/api/admin/queue")
def authority_queue(overdue:bool=False,assigned_to_me:bool=False,department:str|None=None,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    q=select(Complaint).options(selectinload(Complaint.media)).order_by(Complaint.created_at.desc());filters=[]
    if assigned_to_me:filters.append(Complaint.assigned_to_id==u.id)
    if department:filters.append(Complaint.department==department)
    rows=db.scalars(q.where(*filters)).all()
    if overdue:rows=[x for x in rows if is_overdue(x)]
    return [complaint_dict(x) for x in rows]
@app.post("/api/admin/complaints/bulk/status")
def bulk_status(data:BulkStatusUpdate,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    rows=db.scalars(select(Complaint).options(selectinload(Complaint.media)).where(Complaint.id.in_(data.complaint_ids))).all();updated=[]
    for c in rows:
        if data.status==Status.resolved and (not c.resolution_summary or not any(m.media_type=="resolution" for m in c.media)):continue
        old=transition(db,c,data.status,data.note,u);audit(db,"complaint.bulk_status_changed",u.id,"complaint",c.id,{"from":old.value,"to":data.status.value});updated.append(c.id)
    db.commit();return {"updated":updated,"skipped":list(set(data.complaint_ids)-set(updated))}
@app.post("/api/admin/complaints/bulk/assign")
def bulk_assign(data:BulkAssignUpdate,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    rows=db.scalars(select(Complaint).where(Complaint.id.in_(data.complaint_ids))).all()
    for c in rows:c.assigned_to_id=data.assigned_to_id;c.department=data.department;transition(db,c,Status.assigned,f"Assigned to {data.department}",u)
    db.commit();return {"updated":[x.id for x in rows]}
@app.get("/api/admin/complaints/{id}/internal-notes")
def internal_notes(id:str,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    get_one(id,db);rows=db.scalars(select(InternalNote).options(selectinload(InternalNote.author)).where(InternalNote.complaint_id==id).order_by(InternalNote.created_at.desc())).all();return [{"id":x.id,"content":x.content,"author":x.author.full_name,"created_at":x.created_at} for x in rows]
@app.post("/api/admin/complaints/{id}/internal-notes",status_code=201)
def add_internal_note(id:str,data:InternalNoteCreate,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    get_one(id,db);note=InternalNote(complaint_id=id,author_id=u.id,content=data.content.strip());db.add(note);audit(db,"complaint.internal_note_added",u.id,"complaint",id);db.commit();db.refresh(note);return {"id":note.id,"content":note.content,"author":u.full_name,"created_at":note.created_at}
@app.post("/api/admin/complaints/{id}/merge")
def merge(id:str,data:MergeRequest,db:Session=Depends(get_db),u:User=Depends(admin_user)):
    if id==data.duplicate_id:raise HTTPException(400,"Primary and duplicate must be different complaints")
    primary=get_one(id,db); dup=get_one(data.duplicate_id,db)
    if dup.duplicate_of_id:raise HTTPException(409,"Complaint is already merged")
    existing=set(db.scalars(select(ComplaintSupport.user_id).where(ComplaintSupport.complaint_id==id)).all())
    for support in list(db.scalars(select(ComplaintSupport).where(ComplaintSupport.complaint_id==dup.id)).all()):
        if support.user_id in existing:db.delete(support)
        else:support.complaint_id=id;existing.add(support.user_id)
    for comment in db.scalars(select(Comment).where(Comment.complaint_id==dup.id)).all():comment.complaint_id=id
    old=dup.status;dup.status=Status.duplicate;dup.duplicate_of_id=id;primary.support_count=len(existing)
    cluster=ensure_cluster(db,primary);member=db.scalar(select(DuplicateClusterMember).where(DuplicateClusterMember.complaint_id==dup.id))
    if not member:
        score_value,dist,_=hybrid_score(primary,dup.latitude,dup.longitude,dup.category,dup.title+" "+dup.description,dup.image_phash,settings.similarity_radius_m);db.add(DuplicateClusterMember(cluster_id=cluster.id,complaint_id=dup.id,similarity_score=score_value,distance_m=dist));db.flush()
    refresh_cluster(db,cluster);db.add(ComplaintStatusEvent(complaint_id=dup.id,previous_status=old,new_status=Status.duplicate,note=data.note,changed_by_id=u.id));audit(db,"complaint.duplicate_merged",u.id,"complaint",dup.id,{"primary":id,"supporters":primary.support_count});db.commit();return {"primary":complaint_dict(primary),"duplicate":complaint_dict(dup),"cluster_id":cluster.id}

@app.get("/api/admin/duplicate-clusters")
def duplicate_clusters(db:Session=Depends(get_db),u:User=Depends(admin_user)):
    clusters=db.scalars(select(DuplicateCluster).order_by(DuplicateCluster.member_count.desc(),DuplicateCluster.updated_at.desc())).all();out=[]
    for cluster in clusters:
        primary=db.get(Complaint,cluster.primary_complaint_id);members=db.execute(select(DuplicateClusterMember,Complaint).join(Complaint,Complaint.id==DuplicateClusterMember.complaint_id).where(DuplicateClusterMember.cluster_id==cluster.id).order_by(DuplicateClusterMember.similarity_score.desc())).all()
        out.append({"id":cluster.id,"category":cluster.category,"latitude":cluster.latitude,"longitude":cluster.longitude,"member_count":cluster.member_count,"total_support_count":cluster.total_support_count,"primary":complaint_dict(primary),"members":[{"complaint":complaint_dict(c),"similarity_score":m.similarity_score,"distance_m":m.distance_m} for m,c in members]})
    return out

def _aware(value):
    if not value:return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
def _analytics_rows(db,start_date=None,end_date=None,locality=None):
    filters=[]
    if start_date:filters.append(Complaint.created_at>=datetime.combine(start_date,datetime.min.time(),tzinfo=timezone.utc))
    if end_date:filters.append(Complaint.created_at<datetime.combine(end_date+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc))
    if locality:filters.append(func.lower(Complaint.locality)==locality.strip().lower())
    return list(db.scalars(select(Complaint).where(*filters).order_by(Complaint.created_at)).all())
def analytics_data(db,start_date=None,end_date=None,locality=None,private=False):
    rows=_analytics_rows(db,start_date,end_date,locality);total=len(rows);resolved=[c for c in rows if c.status==Status.resolved]
    def counts(field):
        out={}
        for c in rows:
            value=getattr(c,field) or "Unknown";value=value.value if hasattr(value,"value") else value;out[value]=out.get(value,0)+1
        return out
    resolution_hours=[(_aware(c.resolved_at)-_aware(c.created_at)).total_seconds()/3600 for c in rows if c.resolved_at]
    ids=[c.id for c in rows];first_response=[]
    if ids:
        events=db.scalars(select(ComplaintStatusEvent).where(ComplaintStatusEvent.complaint_id.in_(ids),ComplaintStatusEvent.new_status!=Status.submitted).order_by(ComplaintStatusEvent.created_at)).all();seen=set()
        created={c.id:_aware(c.created_at) for c in rows}
        for event in events:
            if event.complaint_id not in seen:first_response.append((_aware(event.created_at)-created[event.complaint_id]).total_seconds()/3600);seen.add(event.complaint_id)
    sla_eligible=[c for c in rows if c.sla_due_at];sla_met=[c for c in sla_eligible if c.resolved_at and _aware(c.resolved_at)<=_aware(c.sla_due_at)]
    confirmed=sum(1 for c in resolved if c.citizen_confirmed_at);reopened=sum(1 for c in rows if c.reopened_count>0)
    monthly={}
    for c in rows:
        key=c.created_at.strftime("%Y-%m");item=monthly.setdefault(key,{"month":key,"reported":0,"resolved":0});item["reported"]+=1;item["resolved"]+=int(c.status==Status.resolved)
    wards=[]
    for name,count in sorted(counts("ward").items(),key=lambda x:x[1],reverse=True):
        ward_rows=[c for c in rows if (c.ward or "Unknown")==name];ward_resolved=sum(c.status==Status.resolved for c in ward_rows);overdue=sum(is_overdue(c) for c in ward_rows);score=round(max(0,min(100,100-(count-ward_resolved)*5-overdue*8)),1);wards.append({"ward":name,"reports":count,"open":count-ward_resolved,"health_score":score})
    hotspots=[{"locality":name,"reports":count,"latitude":round(sum(c.latitude for c in rows if (c.locality or "Unknown")==name)/count,5),"longitude":round(sum(c.longitude for c in rows if (c.locality or "Unknown")==name)/count,5)} for name,count in sorted(counts("locality").items(),key=lambda x:x[1],reverse=True) if name!="Unknown"]
    category_counts=counts("category");months=max(1,len(monthly));forecast=[{"category":name,"forecast":round(count/months,1),"method":"monthly run-rate"} for name,count in sorted(category_counts.items(),key=lambda x:x[1],reverse=True)]
    rate=len(resolved)/max(1,total)*100;sla_rate=len(sla_met)/max(1,len(sla_eligible))*100
    result={"total":total,"resolved":len(resolved),"open":total-len(resolved),"resolution_rate":round(rate,1),"civic_health_score":round(max(0,min(100,45+rate*.35+sla_rate*.2-reopened/max(1,total)*20)),1),"avg_first_response_hours":round(sum(first_response)/len(first_response),1) if first_response else None,"avg_resolution_hours":round(sum(resolution_hours)/len(resolution_hours),1) if resolution_hours else None,"sla_compliance_rate":round(sla_rate,1),"reopened_rate":round(reopened/max(1,len(resolved)+reopened)*100,1),"citizen_satisfaction_score":round(confirmed/max(1,len(resolved))*100,1),"satisfaction_method":"confirmed resolutions / resolved complaints","by_category":category_counts,"by_status":counts("status"),"by_severity":counts("severity"),"by_locality":counts("locality"),"ward_health":wards,"hotspots":hotspots,"monthly_trends":list(monthly.values()),"category_forecast":forecast,"filters":{"start_date":str(start_date) if start_date else None,"end_date":str(end_date) if end_date else None,"locality":locality},"demo_data":True}
    if private:
        departments=[]
        for name,count in sorted(counts("department").items(),key=lambda x:x[1],reverse=True):
            group=[c for c in rows if (c.department or "Unknown")==name];done=sum(c.status==Status.resolved for c in group);departments.append({"department":name,"total":count,"resolved":done,"resolution_rate":round(done/count*100,1),"overdue":sum(is_overdue(c) for c in group)})
        result["department_performance"]=departments
    return result
@app.get("/api/admin/analytics")
def admin_analytics(start_date:date|None=Query(None),end_date:date|None=Query(None),locality:str|None=Query(None,max_length=100),db:Session=Depends(get_db),u:User=Depends(admin_user)): return analytics_data(db,start_date,end_date,locality,True)
@app.get("/api/public/analytics")
def public_analytics(start_date:date|None=Query(None),end_date:date|None=Query(None),locality:str|None=Query(None,max_length=100),db:Session=Depends(get_db)): return analytics_data(db,start_date,end_date,locality)
def _analytics_csv(data):
    output=io.StringIO();writer=csv.writer(output);writer.writerow(["Metric","Value"])
    for key in ["total","resolved","open","resolution_rate","civic_health_score","avg_first_response_hours","avg_resolution_hours","sla_compliance_rate","reopened_rate","citizen_satisfaction_score"]:writer.writerow([key,data.get(key)])
    writer.writerow([]);writer.writerow(["Category","Reports"])
    for key,value in data["by_category"].items():writer.writerow([key,value])
    writer.writerow([]);writer.writerow(["Month","Reported","Resolved"])
    for item in data["monthly_trends"]:writer.writerow([item["month"],item["reported"],item["resolved"]])
    return output.getvalue()
@app.get("/api/admin/analytics/export")
def export_analytics(format:str=Query("csv",pattern="^(csv|pdf)$"),start_date:date|None=Query(None),end_date:date|None=Query(None),locality:str|None=Query(None,max_length=100),db:Session=Depends(get_db),u:User=Depends(admin_user)):
    data=analytics_data(db,start_date,end_date,locality,True);csv_text=_analytics_csv(data)
    if format=="csv":return Response(csv_text,media_type="text/csv",headers={"Content-Disposition":"attachment; filename=civiclens-analytics.csv"})
    lines=["CivicLens Analytics Report",f"Generated: {datetime.now(timezone.utc).date()}"]+[line.replace(","," | ") for line in csv_text.splitlines() if line][:38];safe_lines=[line.replace("\\","").replace("(","[").replace(")","]") for line in lines];content="BT /F1 10 Tf 45 790 Td 14 TL "+" ".join(f"({line}) Tj T*" for line in safe_lines)+" ET";raw=content.encode("latin-1","replace");pdf=(f"%PDF-1.4\n1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj\n2 0 obj <</Type/Pages/Kids[3 0 R]/Count 1>> endobj\n3 0 obj <</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>> endobj\n4 0 obj <</Type/Font/Subtype/Type1/BaseFont/Helvetica>> endobj\n5 0 obj <</Length {len(raw)}>> stream\n").encode()+raw+b"\nendstream endobj\ntrailer <</Root 1 0 R>>\n%%EOF";return Response(pdf,media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=civiclens-analytics.pdf"})
@app.get("/api/public/map")
def public_map(db:Session=Depends(get_db)): return [complaint_dict(x) for x in db.scalars(select(Complaint).order_by(Complaint.created_at.desc())).all()]
@app.get("/api/public/recent")
def recent(db:Session=Depends(get_db)): return [complaint_dict(x) for x in db.scalars(select(Complaint).order_by(Complaint.created_at.desc()).limit(6)).all()]

def authorize_job(secret:str|None):
    if not settings.internal_jobs_secret or secret!=settings.internal_jobs_secret:raise HTTPException(403,"Invalid jobs secret")
@app.post("/api/internal/jobs/sla-alerts")
def run_sla_alerts(x_jobs_secret:str|None=Header(None),db:Session=Depends(get_db)):
    authorize_job(x_jobs_secret);now=datetime.now(timezone.utc);cutoff=now+timedelta(hours=24);created=0
    complaints=db.scalars(select(Complaint).options(selectinload(Complaint.reporter)).where(Complaint.sla_due_at.is_not(None),Complaint.sla_due_at<=cutoff,Complaint.status.notin_([Status.resolved,Status.rejected,Status.duplicate]))).all()
    admins=list(db.scalars(select(User).where(User.role==Role.admin,User.is_active.is_(True))).all())
    for c in complaints:
        overdue=is_overdue(c);kind="sla_escalation" if overdue else "sla_reminder";since=now-timedelta(hours=20)
        if db.scalar(select(Notification.id).where(Notification.complaint_id==c.id,Notification.kind==kind,Notification.created_at>=since)):continue
        recipients=admins if overdue else [c.reporter]
        for recipient in recipients:
            item=Notification(user_id=recipient.id,title=f"SLA {'overdue' if overdue else 'due soon'}: {c.reference_number}",message=f"{c.title} {'has crossed its SLA' if overdue else 'is due within 24 hours'}.",kind=kind,complaint_id=c.id);db.add(item);db.flush();dispatch_notification(db,item,recipient);created+=1
    db.commit();return {"processed":len(complaints),"notifications_created":created}
@app.post("/api/internal/jobs/ward-digest")
def run_ward_digest(x_jobs_secret:str|None=Header(None),db:Session=Depends(get_db)):
    authorize_job(x_jobs_secret);since=datetime.now(timezone.utc)-timedelta(days=1);created=0
    users=db.scalars(select(User).where(User.role==Role.admin,User.is_active.is_(True))).all()
    for user in users:
        pref=notification_preference(db,user.id)
        if not pref.ward_digest:continue
        filters=[Complaint.created_at>=since]
        if user.ward_scope:filters.append(Complaint.ward.in_([x.strip() for x in user.ward_scope.split(',') if x.strip()]))
        count=db.scalar(select(func.count()).select_from(Complaint).where(*filters)) or 0
        if not count:continue
        item=Notification(user_id=user.id,title="Ward daily civic digest",message=f"{count} new complaints were reported in your ward scope during the last 24 hours.",kind="ward_digest");db.add(item);db.flush();dispatch_notification(db,item,user);created+=1
    db.commit();return {"digests_created":created}
@app.post("/api/internal/jobs/data-retention")
def run_data_retention(dry_run:bool=True,x_jobs_secret:str|None=Header(None),db:Session=Depends(get_db)):
    authorize_job(x_jobs_secret);cutoff=datetime.now(timezone.utc)-timedelta(days=settings.closed_media_retention_days)
    rows=db.scalars(select(ComplaintMedia).join(Complaint,Complaint.id==ComplaintMedia.complaint_id).where(Complaint.status.in_([Status.resolved,Status.rejected,Status.duplicate]),Complaint.updated_at<cutoff)).all()
    if not dry_run:
        for media in rows:storage.delete(media.public_id);db.delete(media)
        db.commit()
    return {"eligible_media":len(rows),"deleted":0 if dry_run else len(rows),"dry_run":dry_run,"retention_days":settings.closed_media_retention_days}
