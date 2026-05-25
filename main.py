from fastapi import FastAPI
from pydantic import BaseModel
from database import SessionLocal, LeadRecord, init_db
import dns.resolver
import httpx
from groq import Groq
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


load_dotenv()

app = FastAPI()
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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

def verify_email_domain(email: str) -> bool:
    try:
        domain = email.split("@")[1]
        dns.resolver.resolve(domain, "MX")
        return True
    except:
        return False

SLACK_WEBHOOK = "https://hooks.slack.com/services/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"

def send_slack_notification(lead: Lead, score: int, analysis: str):
    message = f"🔥 Hot Lead!\nName: {lead.name}\nEmail: {lead.email}\nCompany: {lead.company}\nScore: {score}\n\n🤖 AI Analysis:\n{analysis}"
    httpx.post(SLACK_WEBHOOK, json={"text": message})

def analyze_lead_with_ai(lead: Lead) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"Analyze this sales lead in 2 sentences. Is this a serious buyer?\nCompany: {lead.company}\nIndustry: {lead.industry}\nMessage: {lead.message}"
        }],
        max_tokens=200
    )
    return response.choices[0].message.content

@app.post("/lead")
async def receive_lead(lead: Lead):
    score = score_lead(lead)

    if not verify_email_domain(lead.email):
        score -= 20

    classification = classify_lead(score)
    analysis = analyze_lead_with_ai(lead)

    if classification == "hot":
        send_slack_notification(lead, score, analysis)

    db = SessionLocal()
    try:
        record = LeadRecord(
            name=lead.name, email=lead.email,
            company=lead.company, message=lead.message,
            company_size=lead.company_size, industry=lead.industry,
            score=score, classification=classification
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        return {"status": "duplicate", "score": score, "classification": classification, "ai_analysis": analysis}
    finally:
        db.close()

    return {"status": "saved", "score": score, "classification": classification, "ai_analysis": analysis}

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

@app.get("/")
async def dashboard():
    return FileResponse("dashboard.html")