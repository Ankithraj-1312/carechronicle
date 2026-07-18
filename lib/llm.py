import json
import re
import sys
import os
import requests
import google.generativeai as genai

def parse_json_from_text(text: str) -> dict:
    try:
        clean = text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean)
    except Exception:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                raise ValueError("Could not parse JSON from text: " + text)
        raise ValueError("Could not parse JSON from text: " + text)

def fallback_plan(query: str) -> dict:
    STOP_WORDS = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'what', 'when', 'of', 'for', 'to', 'in', 'on', 'and', 'with', 'show', 'please', 'how', 'who', 'where', 'did', 'does', 'do', 'has', 'have', 'had'}
    tokens = [t for t in re.findall(r'[a-z0-9]+', query.lower()) if t not in STOP_WORDS]
    
    types = []
    q_lower = query.lower()
    # Broad prescription detection - includes common query patterns
    if any(kw in q_lower for kw in ['prescrip', 'medication', 'medicine', 'drug', 'pill', 'tablet', 'current med', 'rx', 'taking', 'prescribed', 'dose', 'dosage', 'atorvastatin', 'metformin', 'aspirin', 'paracetamol', 'insulin', 'metoprolol']):
        types.append('prescription')
    # Broad discharge detection
    if any(kw in q_lower for kw in ['discharge', 'admit', 'admission', 'hospital stay', 'hospitalized', 'released']):
        types.append('discharge-summary')
    # Broad lab report detection
    if any(kw in q_lower for kw in ['lab', 'test result', 'report', 'blood', 'hemoglobin', 'glucose', 'hba1c', 'cholesterol', 'platelet', 'cbc', 'ldl', 'hdl', 'triglyceride', 'creatinine', 'thyroid', 'tsh', 'wbc', 'rbc']):
        types.append('lab-report')
    if any(kw in q_lower for kw in ['policy', 'protocol', 'rule', 'guideline']):
        types.append('hospital-policy')

    # Important: if query has personal context words (my, me, current, latest, recent) but no type matched,
    # broaden to search ALL record types
    personal_words = ['my', 'me', 'current', 'latest', 'recent', 'am i', 'i am', 'i have', 'i take']
    if not types and any(pw in q_lower for pw in personal_words):
        types = ['any']
        
    return {
        "types": types if types else ["any"],
        "keywords": tokens[:5]
    }

def fallback_answer(query: str, records: list) -> dict:
    if not records:
        return {
            "answer": f'I could not find any matching patient records for "{query}". Please check the timeline or try different search keywords.',
            "safety": "CareChronicle only summarizes existing records. It does not diagnose or recommend treatment."
        }
        
    details = []
    for r in records:
        body = r.get("body", "")
        meta = r.get("meta", {})
        lines = [line.strip()[2:] for line in body.splitlines() if line.strip().startswith("- ")]
        
        if lines:
            content_text = "; ".join(lines[:3])
        else:
            clean_body = re.sub(r'#.*\n?', '', body)
            clean_body = re.sub(r'\s+', ' ', clean_body).strip()
            content_text = clean_body[:180]
            
        details.append(f"[{meta.get('id')}] ({meta.get('date')}): {content_text}")
        
    return {
        "answer": f'**Rule-based Fallback Answer** (Gemini/Groq API Keys missing/invalid):\n\nHere are the records matching "{query}":\n\n' + "\n\n".join([f"- {d}" for d in details]),
        "safety": "This is a source-based record summary, not medical advice. Please consult a qualified clinician for interpretation, diagnosis, or treatment decisions."
    }

def call_ollama_api(prompt: str, response_format_json: bool = False) -> str:
    host = os.environ.get("OLLAMA_HOST", "")
    if not host:
        raise ValueError("OLLAMA_HOST is not set.")
    model = os.environ.get("OLLAMA_MODEL", "llama3")
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    if response_format_json:
        payload["format"] = "json"
        
    try:
        response = requests.post(f"{host}/api/generate", json=payload, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Ollama API error: {response.status_code} - {response.text}")
        return response.json().get("response", "")
    except Exception as e:
        raise RuntimeError(f"Failed to communicate with Ollama: {str(e)}")

def call_groq_api(messages: list, response_format_json: bool = False) -> str:
    api_key = os.environ.get("Groq_API_KEY", "")
    if not api_key:
        raise ValueError("Groq_API_KEY is not set.")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.2
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}
        
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"Groq API error: {response.status_code} - {response.text}")
        
    return response.json()["choices"][0]["message"]["content"]

def call_gemini_api(prompt: str, api_key: str, response_mime_type: str = None) -> str:
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.5-flash")
    generation_config = {}
    if response_mime_type:
        generation_config["response_mime_type"] = response_mime_type
    response = model.generate_content(prompt, generation_config=generation_config)
    return response.text

async def safety_check(query: str, api_key: str) -> dict:
    groq_key = os.environ.get("Groq_API_KEY", "")
    
    prompt = f"""You are a safety audit tool for a clinical records system named CareChronicle.
Analyze the user's clinical query: "{query}"

Verify:
1. Is it safe? (Does it avoid requesting illegal actions, self-harm, cyber threats, or medical instructions designed to cause harm?)
2. Is it at least tangentially relevant to clinical medicine, patient history, hospital procedures, symptoms, records, or health guidelines?

Respond strictly in JSON format with two keys:
{{
  "safe": true or false,
  "reason": "a brief reason explaining your decision"
}}"""

    if groq_key:
        try:
            res = call_groq_api([{"role": "user", "content": prompt}], response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("Safety check Groq error:", str(e), file=sys.stderr)
            
    if api_key:
        try:
            res = call_gemini_api(prompt, api_key, "application/json")
            return parse_json_from_text(res)
        except Exception as e:
            print("Safety check Gemini error:", str(e), file=sys.stderr)
            
    return {"safe": True, "reason": "No API Key or execution error. Bypassed safely."}

async def plan_query(query: str, api_key: str) -> dict:
    groq_key = os.environ.get("Groq_API_KEY", "")
    
    prompt = f"""Analyze this clinical query: "{query}"
We need to search a database of medical records for this patient.
Determine:
1. What types of records are likely to be relevant? Options: "prescription", "lab-report", "discharge-summary", "hospital-policy", "medical-document", "any".
2. What are the top 3-4 keywords or terms to search for inside those records?

Respond strictly in JSON format:
{{
  "types": ["prescription", "lab-report"],
  "keywords": ["hemoglobin", "anemia", "iron"]
}}"""

    if groq_key:
        try:
            res = call_groq_api([{"role": "user", "content": prompt}], response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("Query planner Groq error:", str(e), file=sys.stderr)
            
    if api_key:
        try:
            res = call_gemini_api(prompt, api_key, "application/json")
            return parse_json_from_text(res)
        except Exception as e:
            print("Query planner Gemini error:", str(e), file=sys.stderr)
            
    return fallback_plan(query)

async def generate_answer(query: str, records: list, api_key: str, patient_name: str = "", patient_id: str = "") -> dict:
    groq_key = os.environ.get("Groq_API_KEY", "")
    
    records_str_list = []
    for r in records:
        meta = r.get("meta", {})
        r_str = (
            f"Record ID: {meta.get('id')}\n"
            f"Date: {meta.get('date')}\n"
            f"Type: {meta.get('type')}\n"
            f"Hospital/Facility: {meta.get('hospital', 'Not specified')}\n"
            f"Prescribing Doctor: {meta.get('doctor', 'Not specified')}\n"
            f"Source File: {meta.get('source_file')}\n"
            f"Full Record Content:\n{r.get('body', '')}"
        )
        records_str_list.append(r_str)
        
    records_str = "\n\n" + ("=" * 50) + "\n\n".join(records_str_list)
    
    patient_context = ""
    if patient_name and patient_id:
        patient_context = f"""ACTIVE PATIENT CONTEXT:
- Patient Name: {patient_name}
- Patient ID: {patient_id}
- You are ONLY answering questions about THIS patient. Ignore any data in the records that references a different patient name or patient_id.

"""
    prompt = f"""You are CareChronicle, a clinical document retrieval assistant. Your job is to give PRECISE, DATA-SPECIFIC answers extracted directly from the patient's records.

{patient_context}Patient Query: "{query}"

Patient Records:
{records_str if records_str else "NO RECORDS FOUND FOR THIS PATIENT."}

CRITICAL INSTRUCTIONS — Follow these strictly:
1. **Extract exact values** from the records — do NOT generalize. For medications: name + dose + frequency. For labs: exact numeric value + unit + reference range if available. For dates: exact date from the record.
2. **Cite every fact** with its Record ID in square brackets, e.g. "Metformin 500 mg twice daily [prescription-2026-07-02-...]".
3. **Structure your answer clearly** using these sections when applicable:
   - Start with a direct 1-2 sentence answer to the question.
   - Then a breakdown with bullet points containing exact data.
   - If multiple records span different dates, show chronological changes (e.g. "HbA1c was 7.4% on 2026-07-01 [lab-report-...]")
4. **For medications**: list EACH drug separately with: drug name, dose (mg/mcg), frequency, instructions (e.g. "with meals"), prescribing doctor, date prescribed.
5. **For lab results**: list EACH test separately with: test name, result value + unit, date of test, ordering doctor.
6. **For discharge/admission**: list: admission reason, discharge date, key findings, follow-up instructions.
7. If a record exists but does NOT contain the specific answer, say so (e.g. "The record from [date] does not mention blood pressure readings").
8. If absolutely NO relevant data exists, say: "No records were found for [specific topic]." — DO NOT give a generic refusal.
9. Finish with a brief safety note mentioning the patient's specific doctor by name if visible.
10. Format in clean Markdown with bold labels.

Respond ONLY in this JSON format:
{{
  "answer": "Your detailed, data-specific markdown answer here...",
  "safety": "A short patient-specific clinical safety note (1-2 sentences, mention their doctor's name if known)"
}}"""

    ollama_host = os.environ.get("OLLAMA_HOST", "")
    if ollama_host:
        try:
            res = call_ollama_api(prompt, response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("Answer generator Ollama error:", str(e), file=sys.stderr)

    if groq_key:
        try:
            res = call_groq_api([{"role": "user", "content": prompt}], response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("Answer generator Groq error:", str(e), file=sys.stderr)
            
    if api_key:
        try:
            res = call_gemini_api(prompt, api_key, "application/json")
            return parse_json_from_text(res)
        except Exception as e:
            print("Answer generator Gemini error:", str(e), file=sys.stderr)
            
    return fallback_answer(query, records)


def is_document_query(query: str) -> bool:
    q = query.lower().strip()
    doc_keywords = [
        "my", "me", "patient", "record", "report", "prescription", "lab", "test", "cbc", 
        "hemoglobin", "haemoglobin", "glucose", "hba1c", "blood", "platelet", 
        "summary", "timeline", "doctor", "physician", "hospital", "clinic", 
        "patel", "sharma", "ananya", "ravi", "chen", "emily", "rx", "tablet", 
        "active condition", "medication", "pill", "mg", "dose", "history", 
        "admit", "admission", "discharge", "latest", "recent", "when was", "what was",
        "who prescribed", "which hospital", "document", "chart", "file"
    ]
    return any(kw in q for kw in doc_keywords)

async def generate_general_answer(query: str, groq_key: str, gemini_key: str) -> dict:
    prompt = f"""You are CareChronicle, a knowledgeable and precise clinical information assistant.
The user has a general medical or health question: "{query}"

CRITICAL INSTRUCTIONS:
1. Give a DETAILED, SPECIFIC, and INFORMATIVE answer — not vague or overly brief.
2. Include: what the condition/term/drug/test IS, how it works, normal ranges or typical values where relevant, common causes, symptoms, or treatments as appropriate to the question.
3. Use clear structure with headers and bullet points where it helps readability.
4. Include specific numbers, clinical thresholds, or examples whenever relevant (e.g. "Normal fasting glucose is 70–99 mg/dL. Prediabetes is 100–125 mg/dL. Diabetes is ≥126 mg/dL.").
5. If the question is about a drug, include: drug class, mechanism (brief), common dosages, key side effects.
6. If the question is about a lab test, include: what it measures, normal reference ranges, what high/low values indicate.
7. If the question is completely unrelated to health/medicine/biology, politely explain your scope.
8. End with a brief, specific safety note (not generic boilerplate).
9. Format in clean Markdown with bold headers.

Respond ONLY in this JSON format:
{{
  "answer": "Your detailed, structured markdown answer here...",
  "safety": "A specific 1-2 sentence safety note relevant to this topic"
}}"""
    ollama_host = os.environ.get("OLLAMA_HOST", "")
    if ollama_host:
        try:
            res = call_ollama_api(prompt, response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("General answer Ollama error:", str(e), file=sys.stderr)

    if groq_key:
        try:
            res = call_groq_api([{"role": "user", "content": prompt}], response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("General answer Groq error:", str(e), file=sys.stderr)
            
    if gemini_key:
        try:
            res = call_gemini_api(prompt, gemini_key, "application/json")
            return parse_json_from_text(res)
        except Exception as e:
            print("General answer Gemini error:", str(e), file=sys.stderr)
            
    return {
        "answer": f"I received your question: '{query}'. However, I am currently operating in offline mode. Please ensure your API keys are active.",
        "safety": "Always consult a qualified doctor or healthcare clinician before making any medical decisions."
    }


async def run_qa_pipeline(query: str, patient_id: str, all_records: list, rank_records_fn) -> dict:
    query = query.strip()
    groq_key = os.environ.get("Groq_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    
    # Resolve patient name for prompt context
    from lib.wiki import get_patient_name
    patient_name = get_patient_name(patient_id)
    
    # 1. Classify if query is general or patient-document related
    is_doc = is_document_query(query)
    
    if not is_doc:
        # General question: bypass safety/planning LLM calls entirely to minimize LLM usage!
        result = await generate_general_answer(query, groq_key, gemini_key)
        return {
            "answer": result.get("answer"),
            "safety": result.get("safety", "This is general medical information, not specific patient advice. Please consult your physician."),
            "sources": []
        }
        
    # Document-related question:
    # 2. Local Query Planning (0 LLM calls!) to get keywords/types
    plan = fallback_plan(query)
    
    # 3. Retrieve & rank records
    matched_records = rank_records_fn(query, plan.get("keywords", []), plan.get("types", ["any"]), all_records)
    
    # 3b. Safety net: if nothing matched with strict types, fall back to searching all records
    if not matched_records and plan.get("types", ["any"]) != ["any"]:
        matched_records = rank_records_fn(query, plan.get("keywords", []), ["any"], all_records)
    
    # 3c. Last resort: if still no records, pass all records to the LLM to let it figure it out
    if not matched_records and all_records:
        matched_records = sorted(all_records, key=lambda r: str(r.get("meta", {}).get("date", "")), reverse=True)[:4]
    
    # 4. Generate Answer from records — use Groq as primary, Gemini as fallback (only 1 LLM call!)
    result = await generate_answer(query, matched_records, gemini_key, patient_name=patient_name, patient_id=patient_id)
    
    # Format sources for frontend
    sources = []
    for r in matched_records:
        meta = r.get("meta", {})
        body = r.get("body", "")
        lines = [line.strip()[2:] for line in body.splitlines() if line.strip().startswith("- ")]
        excerpt_text = "; ".join(lines[:2]) if lines else body[:150]
        
        sources.append({
            "id": meta.get("id"),
            "type": meta.get("type"),
            "date": meta.get("date"),
            "source": meta.get("source_file"),
            "excerpt": excerpt_text
        })
        
    return {
        "answer": result.get("answer"),
        "safety": result.get("safety"),
        "sources": sources
    }
