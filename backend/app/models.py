import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now(): return datetime.now(timezone.utc)
class Role(str, enum.Enum): citizen="citizen"; admin="admin"
class Severity(str, enum.Enum): low="low"; medium="medium"; high="high"; critical="critical"
class Status(str, enum.Enum): submitted="submitted"; verified="verified"; assigned="assigned"; in_progress="in_progress"; resolved="resolved"; rejected="rejected"; duplicate="duplicate"

class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    full_name: Mapped[str]=mapped_column(String(120)); email: Mapped[str]=mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255)); role: Mapped[Role]=mapped_column(Enum(Role), default=Role.citizen)
    phone: Mapped[str|None]=mapped_column(String(30)); locality: Mapped[str|None]=mapped_column(String(100)); ward: Mapped[str|None]=mapped_column(String(50)); department: Mapped[str|None]=mapped_column(String(120)); ward_scope: Mapped[str|None]=mapped_column(String(200))
    is_active: Mapped[bool]=mapped_column(Boolean, default=True); is_email_verified: Mapped[bool]=mapped_column(Boolean, default=False); suspended_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); suspension_reason: Mapped[str|None]=mapped_column(Text); terms_accepted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); privacy_accepted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class Complaint(Base):
    __tablename__="complaints"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    reference_number: Mapped[str]=mapped_column(String(30), unique=True, index=True)
    reporter_id: Mapped[str]=mapped_column(ForeignKey("users.id"), index=True); title: Mapped[str]=mapped_column(String(180)); description: Mapped[str]=mapped_column(Text)
    category: Mapped[str]=mapped_column(String(60), index=True); severity: Mapped[Severity]=mapped_column(Enum(Severity), index=True); status: Mapped[Status]=mapped_column(Enum(Status), default=Status.submitted, index=True)
    confidence_score: Mapped[float|None]=mapped_column(Float); department: Mapped[str|None]=mapped_column(String(120)); image_url: Mapped[str|None]=mapped_column(String(500)); image_public_id: Mapped[str|None]=mapped_column(String(200))
    image_phash: Mapped[str|None]=mapped_column(String(64),index=True); text_embedding: Mapped[str|None]=mapped_column(Text)
    latitude: Mapped[float]=mapped_column(Float, index=True); longitude: Mapped[float]=mapped_column(Float, index=True); address: Mapped[str|None]=mapped_column(String(300)); locality: Mapped[str|None]=mapped_column(String(100)); ward: Mapped[str|None]=mapped_column(String(50)); postal_code: Mapped[str|None]=mapped_column(String(20))
    complaint_letter: Mapped[str|None]=mapped_column(Text); support_count: Mapped[int]=mapped_column(Integer, default=0)
    is_anonymous: Mapped[bool]=mapped_column(Boolean,default=False); hide_exact_location: Mapped[bool]=mapped_column(Boolean,default=False)
    sla_due_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),index=True); resolution_summary: Mapped[str|None]=mapped_column(Text); citizen_confirmed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); reopened_count: Mapped[int]=mapped_column(Integer,default=0)
    duplicate_of_id: Mapped[str|None]=mapped_column(ForeignKey("complaints.id")); assigned_to_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now, index=True); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now, onupdate=now); resolved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    reporter: Mapped[User]=relationship(foreign_keys=[reporter_id]); events: Mapped[list["ComplaintStatusEvent"]]=relationship(cascade="all, delete-orphan", order_by="ComplaintStatusEvent.created_at"); comments: Mapped[list["Comment"]]=relationship(cascade="all, delete-orphan", order_by="Comment.created_at"); media: Mapped[list["ComplaintMedia"]]=relationship(cascade="all, delete-orphan",order_by="ComplaintMedia.created_at")
    __table_args__=(Index("ix_complaint_geo", "latitude", "longitude"),)

class ComplaintStatusEvent(Base):
    __tablename__="complaint_status_events"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4())); complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id"), index=True)
    previous_status: Mapped[Status|None]=mapped_column(Enum(Status)); new_status: Mapped[Status]=mapped_column(Enum(Status)); note: Mapped[str|None]=mapped_column(Text); changed_by_id: Mapped[str]=mapped_column(ForeignKey("users.id")); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class ComplaintMedia(Base):
    __tablename__="complaint_media"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id",ondelete="CASCADE"),index=True)
    url: Mapped[str]=mapped_column(String(500));public_id: Mapped[str|None]=mapped_column(String(200));media_type: Mapped[str]=mapped_column(String(30),default="issue");mime_type: Mapped[str]=mapped_column(String(80),default="image/jpeg")
    uploaded_by_id: Mapped[str]=mapped_column(ForeignKey("users.id"));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class InternalNote(Base):
    __tablename__="internal_notes"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id",ondelete="CASCADE"),index=True);author_id: Mapped[str]=mapped_column(ForeignKey("users.id"));content: Mapped[str]=mapped_column(Text);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True);author: Mapped[User]=relationship()

class ComplaintSupport(Base):
    __tablename__="complaint_supports"; __table_args__=(UniqueConstraint("complaint_id","user_id",name="uq_complaint_support"),)
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4())); complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id", ondelete="CASCADE")); user_id: Mapped[str]=mapped_column(ForeignKey("users.id")); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class Comment(Base):
    __tablename__="comments"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4())); complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True); user_id: Mapped[str]=mapped_column(ForeignKey("users.id")); content: Mapped[str]=mapped_column(Text); is_official: Mapped[bool]=mapped_column(Boolean, default=False); is_hidden: Mapped[bool]=mapped_column(Boolean,default=False,index=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now, onupdate=now); user: Mapped[User]=relationship()

class Notification(Base):
    __tablename__="notifications"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4())); user_id: Mapped[str]=mapped_column(ForeignKey("users.id"), index=True); title: Mapped[str]=mapped_column(String(160)); message: Mapped[str]=mapped_column(Text); kind: Mapped[str]=mapped_column(String(40),default="general",index=True); is_read: Mapped[bool]=mapped_column(Boolean, default=False); complaint_id: Mapped[str|None]=mapped_column(ForeignKey("complaints.id")); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class NotificationPreference(Base):
    __tablename__="notification_preferences"
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),primary_key=True)
    email_enabled: Mapped[bool]=mapped_column(Boolean,default=True);push_enabled: Mapped[bool]=mapped_column(Boolean,default=False);whatsapp_enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    status_alerts: Mapped[bool]=mapped_column(Boolean,default=True);nearby_critical_alerts: Mapped[bool]=mapped_column(Boolean,default=True);ward_digest: Mapped[bool]=mapped_column(Boolean,default=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)

class PushSubscription(Base):
    __tablename__="push_subscriptions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));user_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    endpoint: Mapped[str]=mapped_column(Text,unique=True);p256dh: Mapped[str]=mapped_column(Text);auth: Mapped[str]=mapped_column(Text);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);last_used_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class NotificationDelivery(Base):
    __tablename__="notification_deliveries"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));notification_id: Mapped[str]=mapped_column(ForeignKey("notifications.id",ondelete="CASCADE"),index=True)
    channel: Mapped[str]=mapped_column(String(20),index=True);status: Mapped[str]=mapped_column(String(20),default="pending",index=True);error: Mapped[str|None]=mapped_column(Text);attempted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True));created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ModerationReport(Base):
    __tablename__="moderation_reports"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));reporter_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    target_type: Mapped[str]=mapped_column(String(30),index=True);target_id: Mapped[str]=mapped_column(String(36),index=True);reason: Mapped[str]=mapped_column(String(60),index=True);details: Mapped[str|None]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(30),default="pending",index=True);reviewed_by_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"));review_note: Mapped[str|None]=mapped_column(Text);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True);reviewed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint("reporter_id","target_type","target_id",name="uq_moderation_reporter_target"),)

class UserBlock(Base):
    __tablename__="user_blocks";__table_args__=(UniqueConstraint("blocker_id","blocked_id",name="uq_user_block"),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));blocker_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);blocked_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SuspensionAppeal(Base):
    __tablename__="suspension_appeals"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()));user_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);message: Mapped[str]=mapped_column(Text);status: Mapped[str]=mapped_column(String(30),default="pending",index=True);reviewed_by_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"));review_note: Mapped[str|None]=mapped_column(Text);created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);reviewed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class AuthToken(Base):
    __tablename__="auth_tokens"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    token_hash: Mapped[str]=mapped_column(String(64),unique=True,index=True)
    purpose: Mapped[str]=mapped_column(String(30),index=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    used_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); revoked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    actor_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),index=True); action: Mapped[str]=mapped_column(String(100),index=True)
    entity_type: Mapped[str|None]=mapped_column(String(60)); entity_id: Mapped[str|None]=mapped_column(String(60),index=True)
    metadata_json: Mapped[str|None]=mapped_column(Text); ip_address: Mapped[str|None]=mapped_column(String(64)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)

class GeocodeCache(Base):
    __tablename__="geocode_cache"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    cache_key: Mapped[str]=mapped_column(String(80),unique=True,index=True); latitude: Mapped[float]=mapped_column(Float); longitude: Mapped[float]=mapped_column(Float)
    response_json: Mapped[str]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)

class DuplicateCluster(Base):
    __tablename__="duplicate_clusters"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    primary_complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id",ondelete="CASCADE"),unique=True,index=True)
    category: Mapped[str]=mapped_column(String(60),index=True); latitude: Mapped[float]=mapped_column(Float); longitude: Mapped[float]=mapped_column(Float)
    member_count: Mapped[int]=mapped_column(Integer,default=1); total_support_count: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)

class DuplicateClusterMember(Base):
    __tablename__="duplicate_cluster_members"; __table_args__=(UniqueConstraint("cluster_id","complaint_id",name="uq_cluster_complaint"),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    cluster_id: Mapped[str]=mapped_column(ForeignKey("duplicate_clusters.id",ondelete="CASCADE"),index=True)
    complaint_id: Mapped[str]=mapped_column(ForeignKey("complaints.id",ondelete="CASCADE"),unique=True,index=True)
    similarity_score: Mapped[float]=mapped_column(Float,default=1); distance_m: Mapped[float]=mapped_column(Float,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
