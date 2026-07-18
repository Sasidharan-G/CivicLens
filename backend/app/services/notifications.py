import json, logging
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import settings
from ..models import Notification, NotificationDelivery, NotificationPreference, PushSubscription, User
from .email import send_email

logger=logging.getLogger("civiclens.notifications")

def preference(db:Session,user_id:str)->NotificationPreference:
    item=db.get(NotificationPreference,user_id)
    if not item:item=NotificationPreference(user_id=user_id);db.add(item);db.flush()
    return item

def create(db:Session,user:User,title:str,message:str,kind:str="general",complaint_id:str|None=None)->Notification:
    item=Notification(user_id=user.id,title=title,message=message,kind=kind,complaint_id=complaint_id);db.add(item);db.flush();return item

def _delivery(db:Session,item:Notification,channel:str,status:str,error:str|None=None):db.add(NotificationDelivery(notification_id=item.id,channel=channel,status=status,error=error,attempted_at=datetime.now(timezone.utc)))

def dispatch(db:Session,item:Notification,user:User):
    pref=preference(db,user.id)
    if pref.email_enabled and user.email:
        try:send_email(user.email,item.title,item.message);_delivery(db,item,"email","sent")
        except Exception as error:logger.exception("Email notification failed");_delivery(db,item,"email","failed",str(error)[:1000])
    if pref.push_enabled:
        try:
            from pywebpush import webpush
            if not settings.vapid_private_key:raise RuntimeError("VAPID keys are not configured")
            for subscription in db.scalars(select(PushSubscription).where(PushSubscription.user_id==user.id)).all():
                webpush(subscription_info={"endpoint":subscription.endpoint,"keys":{"p256dh":subscription.p256dh,"auth":subscription.auth}},data=json.dumps({"title":item.title,"body":item.message,"complaint_id":item.complaint_id}),vapid_private_key=settings.vapid_private_key,vapid_claims={"sub":settings.vapid_subject});subscription.last_used_at=datetime.now(timezone.utc)
            _delivery(db,item,"push","sent")
        except Exception as error:logger.warning("Push notification failed: %s",error);_delivery(db,item,"push","failed",str(error)[:1000])
    if pref.whatsapp_enabled and user.phone:
        try:
            if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:raise RuntimeError("WhatsApp provider is not configured")
            response=httpx.post(f"https://graph.facebook.com/{settings.whatsapp_api_version}/{settings.whatsapp_phone_number_id}/messages",headers={"Authorization":f"Bearer {settings.whatsapp_access_token}"},json={"messaging_product":"whatsapp","to":user.phone,"type":"text","text":{"body":f"{item.title}\n{item.message}"}},timeout=15);response.raise_for_status();_delivery(db,item,"whatsapp","sent")
        except Exception as error:logger.warning("WhatsApp notification failed: %s",error);_delivery(db,item,"whatsapp","failed",str(error)[:1000])
