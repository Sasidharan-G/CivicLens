import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .database import Base, SessionLocal, engine
from .models import Comment, Complaint, ComplaintStatusEvent, Role, Severity, Status, User
from .security import hash_password

categories=[("Pothole","Roads Department"),("Garbage accumulation","Solid Waste Management"),("Water leakage","Chennai Metro Water"),("Sewage overflow","Chennai Metro Water"),("Broken streetlight","Electrical Department"),("Open drain","Storm Water Drains"),("Fallen tree","Parks Department")]
places=[("T. Nagar",13.0418,80.2341),("Adyar",13.0067,80.2570),("Anna Nagar",13.0850,80.2101),("Mylapore",13.0339,80.2697),("Velachery",12.9815,80.2180),("Perambur",13.1210,80.2326),("Besant Nagar",13.0003,80.2667)]
def seed():
    Base.metadata.create_all(engine); db=SessionLocal()
    try:
        users=[]
        for name,email,password,role in [("CivicLens Admin","admin@civiclens.demo","Admin@123",Role.admin),("Arun Kumar","citizen@civiclens.demo","Citizen@123",Role.citizen),("Meena Ravi","meena@civiclens.demo","Citizen@123",Role.citizen)]:
            u=db.scalar(select(User).where(User.email==email))
            if not u: u=User(full_name=name,email=email,password_hash=hash_password(password),role=role,locality="Chennai");db.add(u);db.flush()
            users.append(u)
        if db.scalar(select(Complaint).limit(1)): db.commit(); return
        random.seed(42)
        titles={"Pothole":"Deep pothole causing traffic hazard","Garbage accumulation":"Uncollected waste near residential street","Water leakage":"Continuous water leak on main road","Sewage overflow":"Sewage overflowing onto pedestrian path","Broken streetlight":"Streetlight not working after dark","Open drain":"Open drain poses public safety risk","Fallen tree":"Fallen tree blocking part of road"}
        for i in range(20):
            cat,dept=categories[i%len(categories)]; loc,lat,lon=places[i%len(places)]; sev=list(Severity)[i%4]; st=[Status.submitted,Status.verified,Status.assigned,Status.in_progress,Status.resolved][i%5]; created=datetime.now(timezone.utc)-timedelta(days=i*3)
            c=Complaint(reference_number=f"CIV-2026-{i+1:06d}",reporter_id=users[1+i%2].id,title=titles[cat],description=f"Residents in {loc} have observed this {cat.lower()} for several days. It requires an on-site inspection.",category=cat,severity=sev,status=st,confidence_score=.78+(i%10)/100,department=dept,latitude=lat+(i%3)*.00035,longitude=lon+(i%4)*.0003,address=f"Demo location near {loc}, Chennai",locality=loc,ward=f"Ward {100+i%12}",postal_code="6000"+str(10+i%80),complaint_letter=f"To\nThe Officer-in-Charge, {dept}\n\nSubject: Civic issue at {loc}\n\nThis demo complaint requests inspection and corrective action regarding {cat.lower()}.\n\nReference: CIV-2026-{i+1:06d}",support_count=i%8,created_at=created,resolved_at=created+timedelta(days=5) if st==Status.resolved else None);db.add(c);db.flush();db.add(ComplaintStatusEvent(complaint_id=c.id,previous_status=None,new_status=Status.submitted,note="Demo complaint submitted",changed_by_id=users[1].id,created_at=created))
            if st!=Status.submitted: db.add(ComplaintStatusEvent(complaint_id=c.id,previous_status=Status.submitted,new_status=st,note=f"Demo authority update: {st.value.replace('_',' ')}",changed_by_id=users[0].id,created_at=created+timedelta(days=1)))
            if i<8: db.add(Comment(complaint_id=c.id,user_id=users[2].id,content="I have also noticed this issue. Please prioritise an inspection.",is_official=False))
        db.commit(); print("CivicLens demo data seeded")
    finally: db.close()
if __name__=="__main__": seed()

