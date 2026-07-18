import json
from datetime import date
import httpx
from ..config import settings

DEPARTMENTS={"Pothole":"Roads Department","Garbage accumulation":"Solid Waste Management","Water leakage":"Chennai Metro Water","Sewage overflow":"Chennai Metro Water","Broken streetlight":"Electrical Department","Fallen tree":"Parks Department"}
class AIProvider:
    async def analyze_issue_image(self, data:bytes, filename:str):
        if not settings.ai_api_key:
            name=filename.lower(); category=next((k for k in DEPARTMENTS if k.lower().split()[0] in name),"Pothole")
            return {"category":category,"title":f"{category} requires attention","description":f"A {category.lower()} was observed at this location and requires inspection by the responsible civic team.","severity":"high" if "major" in name else "medium","confidence_score":.86,"department":DEPARTMENTS.get(category,"Greater Chennai Corporation"),"safety_warning":"Please keep a safe distance from the affected area.","is_safe":True,"moderation_labels":[],"is_demo":True}
        prompt="Analyze this civic issue image and moderate it. Return JSON keys category,title,description,severity,confidence_score,department,safety_warning,is_safe,moderation_labels only. Set is_safe false for explicit sexual content, graphic violence unrelated to civic evidence, hate symbols, or exposed personal documents."
        import base64
        payload={"model":settings.ai_vision_model,"messages":[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(data).decode()}}]}],"response_format":{"type":"json_object"}}
        async with httpx.AsyncClient(timeout=45) as c:
            r=await c.post(settings.ai_base_url.rstrip("/")+"/chat/completions",headers={"Authorization":f"Bearer {settings.ai_api_key}"},json=payload); r.raise_for_status()
            out=json.loads(r.json()["choices"][0]["message"]["content"]); out["is_demo"]=False; return out
    async def generate_complaint_letter(self, d):
        return f"To\nThe Officer-in-Charge,\n{d.department}\n\nSubject: Request for action regarding {d.category}\n\nRespected Sir/Madam,\n\nI, {d.citizen_name}, wish to report a {d.severity.value}-severity civic issue at {d.address}. {d.description}\n\nI request your department to inspect the location and take timely corrective action. Kindly use reference {d.reference_number} for further correspondence.\n\nDate: {date.today():%d %B %Y}\n\nYours faithfully,\n{d.citizen_name}"
ai=AIProvider()
