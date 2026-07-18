import os
import re
import base64
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from lib.extractors import extract_text
from lib.okf_builder import build_okf_markdown, parse_frontmatter, slug
from lib.llm import safety_check, plan_query, generate_answer, run_qa_pipeline
from lib.wiki import build_patient_profile, get_patient_name, PATIENT_NAMES

app = FastAPI()

ROOT = os.getcwd()
PATIENTS_DIR = os.path.join(ROOT, "data", "okf", "patients")

class ConvertPayload(BaseModel):
    filename: str = 'uploaded-document.txt'
    content: str
    patientId: str = 'patient-001'

class UploadPayload(BaseModel):
    filename: str
    content: str
    patientId: str = 'patient-001'

class QueryPayload(BaseModel):
    query: str
    patientId: str = 'patient-001'

def seed_demo_data():
    os.makedirs(PATIENTS_DIR, exist_ok=True)
    
    sample1 = [
        {"filename": "cbc-report-2026-07-16.txt", "content": "Complete Blood Count (CBC)\nDate: 2026-07-16\nHemoglobin: 10.2 g/dL\nPlatelet count: 245,000 /uL\nSource: City Care Diagnostics\nPhysician: Dr. Sharma"},
        {"filename": "prescription-2026-07-10.txt", "content": "Prescription\nDate: 2026-07-10\nParacetamol 500 mg - take 1 tablet three times daily as needed for pain.\nFollow-up visit in 7 days\nCity Care Hospital\nPhysician: Dr. Sharma"},
        {"filename": "discharge-summary-2026-06-02.txt", "content": "Discharge Summary\nDate: 2026-06-02\nAdmission for observation after mild chest tightness.\nECG normal. Released with prescription.\nCity Care Hospital\nPhysician: Dr. Sharma"}
    ]

    sample2 = [
        {"filename": "diabetic-check-2026-07-01.txt", "content": "Diabetic Assessment Report\nDate: 2026-07-01\nHbA1c: 7.4 %\nGlucose (Fasting): 140 mg/dL\nSource: Apex Diagnostics\nPhysician: Dr. Patel"},
        {"filename": "prescription-2026-07-02.txt", "content": "Prescription\nDate: 2026-07-02\nMetformin 500 mg - take 1 tablet twice daily with meals.\nAtorvastatin 10 mg - take 1 tablet daily at bedtime.\nAspirin 81 mg - take 1 tablet daily.\nApex Diagnostics\nPhysician: Dr. Patel"}
    ]

    p1_dir = os.path.join(PATIENTS_DIR, "patient-001")
    os.makedirs(p1_dir, exist_ok=True)
    if not any(f.endswith('.md') for f in os.listdir(p1_dir)):
        for s in sample1:
            markdown = build_okf_markdown(s["filename"], s["content"], "patient-001")
            parsed = parse_frontmatter(markdown)
            doc_id = parsed["meta"].get("id")
            with open(os.path.join(p1_dir, f"{doc_id}.md"), "w", encoding="utf-8") as f:
                f.write(markdown)

    p2_dir = os.path.join(PATIENTS_DIR, "patient-002")
    os.makedirs(p2_dir, exist_ok=True)
    if not any(f.endswith('.md') for f in os.listdir(p2_dir)):
        for s in sample2:
            markdown = build_okf_markdown(s["filename"], s["content"], "patient-002")
            parsed = parse_frontmatter(markdown)
            doc_id = parsed["meta"].get("id")
            with open(os.path.join(p2_dir, f"{doc_id}.md"), "w", encoding="utf-8") as f:
                f.write(markdown)

seed_demo_data()

def list_records(patient_id: str) -> list:
    p_dir = os.path.join(PATIENTS_DIR, patient_id)
    os.makedirs(p_dir, exist_ok=True)
    records = []
    for name in os.listdir(p_dir):
        if name.endswith('.md'):
            filepath = os.path.join(p_dir, name)
            with open(filepath, "r", encoding="utf-8") as f:
                markdown = f.read()
            parsed = parse_frontmatter(markdown)
            # Guard: skip any record whose patient_id doesn't match the requested one
            record_patient_id = parsed["meta"].get("patient_id", patient_id)
            if record_patient_id != patient_id:
                print(f"[WARN] Skipping cross-patient record: {name} (belongs to {record_patient_id}, not {patient_id})", flush=True)
                continue
            records.append({
                "file": name,
                "meta": parsed["meta"],
                "body": parsed["body"]
            })
    records.sort(key=lambda r: str(r.get("meta", {}).get("date", "")), reverse=True)
    return records

def rank_records_smarter(query: str, keywords: list, types: list, records: list) -> list:
    scored_records = []
    for r in records:
        score = 0
        meta = r.get("meta", {})
        body = r.get("body", "")
        haystack = f"{meta.get('type', '')} {meta.get('date', '')} {body}".lower()
        
        for kw in keywords:
            if kw.lower() in haystack:
                score += 5
                
        if "any" in types or meta.get("type") in types:
            score += 10
            
        simple_tokens = re.findall(r'[a-z0-9]+', query.lower())
        for token in simple_tokens:
            if token in haystack:
                score += 1
                
        if score > 0:
            r_copy = r.copy()
            r_copy["score"] = score
            scored_records.append(r_copy)
            
    scored_records.sort(key=lambda x: (-x["score"], x.get("meta", {}).get("date", "")))
    return scored_records[:4]

# API Endpoints
@app.get("/api/patients")
def get_patients():
    for p_id in PATIENT_NAMES.keys():
        os.makedirs(os.path.join(PATIENTS_DIR, p_id), exist_ok=True)
        
    dirs = [name for name in os.listdir(PATIENTS_DIR) if os.path.isdir(os.path.join(PATIENTS_DIR, name))]
    patients = [{"id": d, "name": get_patient_name(d)} for d in dirs]
    return {"patients": patients}

@app.get("/api/profile")
def get_profile(patientId: str = 'patient-001'):
    records = list_records(patientId)
    profile = build_patient_profile(records, patientId)
    return profile

@app.get("/api/records")
def get_records(patientId: str = 'patient-001'):
    records = list_records(patientId)
    return {"records": records}

@app.post("/api/convert")
def convert_document(payload: ConvertPayload):
    if not payload.content.strip():
        return JSONResponse(status_code=400, content={"error": "Add readable document text before conversion."})
        
    p_dir = os.path.join(PATIENTS_DIR, payload.patientId)
    os.makedirs(p_dir, exist_ok=True)
    
    markdown = build_okf_markdown(payload.filename, payload.content, payload.patientId)
    parsed = parse_frontmatter(markdown)
    doc_id = parsed["meta"].get("id")
    
    with open(os.path.join(p_dir, f"{doc_id}.md"), "w", encoding="utf-8") as f:
        f.write(markdown)
        
    return JSONResponse(status_code=201, content={
        "message": "Document converted to an OKF Markdown record.",
        "id": doc_id,
        "markdown": markdown
    })

@app.post("/api/upload")
def upload_file(payload: UploadPayload):
    if not payload.filename or not payload.content:
        return JSONResponse(status_code=400, content={"error": "Missing filename or content payload"})
        
    try:
        buffer = base64.b64decode(payload.content)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid base64 payload"})
        
    try:
        extracted_text = extract_text(buffer, payload.filename)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Failed to parse file: {str(e)}"})
        
    if not extracted_text.strip():
        return JSONResponse(status_code=400, content={"error": "Document does not contain any readable text."})
        
    p_dir = os.path.join(PATIENTS_DIR, payload.patientId)
    os.makedirs(p_dir, exist_ok=True)
    
    markdown = build_okf_markdown(payload.filename, extracted_text, payload.patientId)
    parsed = parse_frontmatter(markdown)
    doc_id = parsed["meta"].get("id")
    
    with open(os.path.join(p_dir, f"{doc_id}.md"), "w", encoding="utf-8") as f:
        f.write(markdown)
        
    return JSONResponse(status_code=201, content={
        "message": "File uploaded, parsed, and converted to OKF Markdown.",
        "id": doc_id,
        "type": parsed["meta"].get("type"),
        "date": parsed["meta"].get("date")
    })

@app.post("/api/query")
async def query_pipeline(payload: QueryPayload):
    query = payload.query.strip()
    if not query:
        return JSONResponse(status_code=400, content={"error": "Enter a question."})
        
    all_records = list_records(payload.patientId)
    result = await run_qa_pipeline(query, payload.patientId, all_records, rank_records_smarter)
    return result

# Serving SPA Static Assets
@app.get("/")
def read_root():
    return FileResponse("public/index.html")

@app.get("/requirements.txt")
def get_requirements():
    return FileResponse("requirements.txt")

app.mount("/", StaticFiles(directory="public"), name="public")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
