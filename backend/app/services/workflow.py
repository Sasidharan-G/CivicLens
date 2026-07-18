from datetime import datetime,timedelta,timezone
from fastapi import HTTPException
from ..models import Complaint,ComplaintStatusEvent,Notification,Severity,Status,User

ALLOWED={Status.submitted:{Status.verified,Status.rejected,Status.duplicate},Status.verified:{Status.assigned,Status.rejected,Status.duplicate},Status.assigned:{Status.in_progress,Status.rejected},Status.in_progress:{Status.resolved,Status.rejected},Status.resolved:{Status.in_progress},Status.rejected:{Status.verified},Status.duplicate:{Status.verified}}
SLA_HOURS={Severity.critical:4,Severity.high:24,Severity.medium:72,Severity.low:120}
def ensure_transition(old:Status,new:Status):
    if old==new:return
    if new not in ALLOWED.get(old,set()):raise HTTPException(409,f"Cannot change status from {old.value} to {new.value}")
def sla_deadline(severity:Severity):return datetime.now(timezone.utc)+timedelta(hours=SLA_HOURS[severity])
def transition(db,complaint:Complaint,new:Status,note:str,actor:User,force=False):
    old=complaint.status
    if not force:ensure_transition(old,new)
    complaint.status=new
    if new==Status.assigned and not complaint.sla_due_at:complaint.sla_due_at=sla_deadline(complaint.severity)
    if new==Status.resolved:complaint.resolved_at=datetime.now(timezone.utc)
    elif old==Status.resolved:complaint.resolved_at=None;complaint.citizen_confirmed_at=None;complaint.reopened_count+=1
    db.add(ComplaintStatusEvent(complaint_id=complaint.id,previous_status=old,new_status=new,note=note,changed_by_id=actor.id));db.add(Notification(user_id=complaint.reporter_id,title=f"Complaint {new.value.replace('_',' ')}",message=note,kind="status_change",complaint_id=complaint.id));return old
def is_overdue(complaint:Complaint):
    if not complaint.sla_due_at or complaint.status in {Status.resolved,Status.rejected,Status.duplicate}:return False
    due=complaint.sla_due_at.replace(tzinfo=timezone.utc) if complaint.sla_due_at.tzinfo is None else complaint.sla_due_at
    return due<datetime.now(timezone.utc)
