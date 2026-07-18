import json
from sqlalchemy.orm import Session
from ..models import AuditLog
def record(db:Session,action:str,actor_id:str|None=None,entity_type:str|None=None,entity_id:str|None=None,metadata:dict|None=None,ip_address:str|None=None):
    db.add(AuditLog(actor_id=actor_id,action=action,entity_type=entity_type,entity_id=entity_id,metadata_json=json.dumps(metadata or {},default=str),ip_address=ip_address))

