from fastapi import FastAPI
from pydantic import BaseModel
from database import SessionLocal, LeadRecord, init_db

app = FastAPI()
init_db()

class Lead(BaseModel):
    name: str
    email: str
    company: str
    message: str
    company_size: int = 0
    industry: str = ""

def score_lead(lead: Lead) -> int:
    score = 0
    target_industries = ["tech", "software", "saas", "ai"]
    if lead.company_size > 50:   score += 30
    if "@gmail" not in lead.email and "@yahoo" not in lead.email: score += 20
    if lead.industry.lower() in target_industries: score += 25
    if len(lead.message) > 100:  score += 15
    if lead.company:             score += 10
    return score

def classify_lead(score: int) -> str:
    if score >= 70:   return "hot"
    elif score >= 40: return "warm"
    else:             return "cold"

@app.post("/lead")
async def receive_lead(lead: Lead):
    score = score_lead(lead)
    classification = classify_lead(score)
    db = SessionLocal()
    record = LeadRecord(
        name=lead.name, email=lead.email,
        company=lead.company, message=lead.message,
        company_size=lead.company_size, industry=lead.industry,
        score=score, classification=classification
    )
    db.add(record)
    db.commit()
    db.close()
    return {"status": "saved", "score": score, "classification": classification}

@app.get("/leads")
async def get_leads():
    db = SessionLocal()
    leads = db.query(LeadRecord).all()
    db.close()
    return {"total": len(leads), "leads": leads}

@app.get("/leads/hot")
async def get_hot_leads():
    db = SessionLocal()
    leads = db.query(LeadRecord)\
              .filter(LeadRecord.classification != "cold")\
              .order_by(LeadRecord.score.desc())\
              .all()
    db.close()
    return {"total": len(leads), "leads": leads}