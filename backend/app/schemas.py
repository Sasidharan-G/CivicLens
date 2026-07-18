from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from .models import Role, Severity, Status

class UserCreate(BaseModel):
    full_name:str=Field(min_length=2,max_length=120); email:EmailStr; password:str=Field(min_length=8,max_length=72); phone:str|None=None; locality:str|None=None;accept_terms:bool=True;accept_privacy:bool=True
class Login(BaseModel): email:EmailStr; password:str
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True); id:str; full_name:str; email:EmailStr; role:Role; locality:str|None=None; is_email_verified:bool=False
class Token(BaseModel): access_token:str; refresh_token:str; token_type:str="bearer"; expires_in:int; user:UserOut
class RefreshRequest(BaseModel): refresh_token:str=Field(min_length=32)
class TokenAction(BaseModel): token:str=Field(min_length=32)
class ForgotPassword(BaseModel): email:EmailStr
class ResetPassword(BaseModel): token:str=Field(min_length=32); new_password:str=Field(min_length=8,max_length=72)
class EmailRequest(BaseModel): email:EmailStr
class MediaInput(BaseModel): url:str=Field(max_length=500); public_id:str|None=None; mime_type:str="image/jpeg"
class ComplaintCreate(BaseModel):
    title:str=Field(min_length=4,max_length=180); description:str=Field(min_length=10,max_length=5000); category:str; severity:Severity; confidence_score:float|None=Field(None,ge=0,le=1); department:str|None=None; image_url:str|None=None; image_public_id:str|None=None; image_phash:str|None=Field(None,max_length=64); media:list[MediaInput]=Field(default_factory=list,max_length=5); latitude:float=Field(ge=-90,le=90); longitude:float=Field(ge=-180,le=180); address:str|None=None; locality:str|None=None; ward:str|None=None; postal_code:str|None=None; complaint_letter:str|None=None; is_anonymous:bool=False; hide_exact_location:bool=False
class SimilarRequest(BaseModel): latitude:float; longitude:float; category:str; title:str=""; description:str=""; image_phash:str|None=Field(None,max_length=64); radius_m:float|None=None
class LetterRequest(BaseModel): citizen_name:str; category:str; description:str; address:str; severity:Severity; department:str="Greater Chennai Corporation"; reference_number:str="Draft"
class StatusUpdate(BaseModel): status:Status; note:str=Field(min_length=2,max_length=1000)
class AssignUpdate(BaseModel): assigned_to_id:str|None=None; department:str
class MergeRequest(BaseModel): duplicate_id:str; note:str="Merged as a duplicate report"
class CommentCreate(BaseModel): content:str=Field(min_length=2,max_length=1500)
class InternalNoteCreate(BaseModel): content:str=Field(min_length=2,max_length=3000)
class BulkStatusUpdate(BaseModel): complaint_ids:list[str]=Field(min_length=1,max_length=100); status:Status; note:str=Field(min_length=2,max_length=1000)
class BulkAssignUpdate(BaseModel): complaint_ids:list[str]=Field(min_length=1,max_length=100); assigned_to_id:str|None=None; department:str
class ResolutionUpdate(BaseModel): summary:str=Field(min_length=5,max_length=3000)
class ReopenRequest(BaseModel): reason:str=Field(min_length=5,max_length=1500)
class NotificationPreferenceUpdate(BaseModel):
    email_enabled:bool=True;push_enabled:bool=False;whatsapp_enabled:bool=False;status_alerts:bool=True;nearby_critical_alerts:bool=True;ward_digest:bool=False
class PushSubscriptionCreate(BaseModel): endpoint:str=Field(min_length=10,max_length=4000);p256dh:str=Field(min_length=8,max_length=1000);auth:str=Field(min_length=8,max_length=1000)
class ModerationReportCreate(BaseModel): target_type:str=Field(pattern="^(comment|complaint|user)$");target_id:str;reason:str=Field(min_length=3,max_length=60);details:str|None=Field(None,max_length=1500)
class ModerationReview(BaseModel): action:str=Field(pattern="^(dismiss|hide|suspend|restore)$");note:str=Field(min_length=2,max_length=1500)
class UserBlockCreate(BaseModel): user_id:str
class AppealCreate(BaseModel): message:str=Field(min_length=10,max_length=3000)
class AppealReview(BaseModel): approve:bool;note:str=Field(min_length=2,max_length=1500)
