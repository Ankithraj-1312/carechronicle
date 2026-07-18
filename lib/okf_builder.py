import re
import os
from datetime import datetime

MEDICATION_TERMS = [
  'paracetamol', 'amoxicillin', 'metformin', 'insulin', 'atorvastatin', 'aspirin', 
  'cetirizine', 'pantoprazole', 'ibuprofen', 'losartan', 'lisinopril', 'gabapentin', 
  'amlodipine', 'albuterol', 'omeprazole', 'synthroid', 'acetaminophen'
]

LAB_TERMS = [
  'hemoglobin', 'haemoglobin', 'glucose', 'cholesterol', 'platelet', 'creatinine', 
  'thyroid', 'vitamin d', 'hba1c', 'blood pressure', 'wbc', 'rbc', 'ldl', 'hdl', 
  'potassium', 'sodium', 'tsh', 'urea', 'bilirubin'
]

def slug(value: str) -> str:
    cleaned = re.sub(r'[^a-z0-9]+', '-', value.lower())
    cleaned = re.sub(r'(^-|-$)', '', cleaned)
    return cleaned if cleaned else 'record'

def iso_date(text: str) -> str:
    match1 = re.search(r'\b(20\d{2})[-/]([01]?\d)[-/]([0-3]?\d)\b', text)
    if match1:
        return f"{match1.group(1)}-{match1.group(2).zfill(2)}-{match1.group(3).zfill(2)}"
        
    match2 = re.search(r'\b([0-3]?\d)[/-]([01]?\d)[/-](20\d{2})\b', text)
    if match2:
        return f"{match2.group(3)}-{match2.group(2).zfill(2)}-{match2.group(1).zfill(2)}"
        
    return datetime.now().strftime('%Y-%m-%d')

def classify_document(filename: str, content: str) -> str:
    haystack = f"{filename} {content}".lower()
    if re.search(r'discharge|admission|hospital stay|discharged', haystack):
        return 'discharge-summary'
    if re.search(r'prescription|rx\b|tablet|capsule|dosage|sig:|take \d', haystack):
        return 'prescription'
    if re.search(r'lab|test result|hemoglobin|haemoglobin|cbc|glucose|platelet|creatinine|report', haystack):
        return 'lab-report'
    if re.search(r'policy|procedure|protocol|staff|clinical guideline', haystack):
        return 'hospital-policy'
    return 'medical-document'

def excerpt(content: str, max_len: int = 560) -> str:
    cleaned = re.sub(r'\s+', ' ', content).strip()
    truncated = cleaned[:max_len]
    return re.sub(r'[\s,;:.]+$', '', truncated)

def extract_facts(content: str) -> list:
    facts = []
    lines = content.splitlines()
    
    for term in LAB_TERMS:
        for line in lines:
            if term in line.lower():
                facts.append(line.strip())
                break
                
    for term in MEDICATION_TERMS:
        for line in lines:
            if term in line.lower():
                facts.append(line.strip())
                break
                
    hospital_match = re.search(r'\b[A-Za-z0-9\s]+ (Hospital|Clinic|Lab|Diagnostics|Center|Medical Group)\b', content, re.IGNORECASE)
    if hospital_match:
        facts.append(f"Facility: {hospital_match.group(0).strip()}")
        
    doctor_match = re.search(r'\bDr\.\s+[A-Z][a-zA-Z]+', content)
    if doctor_match:
        facts.append(f"Physician: {doctor_match.group(0).strip()}")
        
    seen = set()
    unique_facts = [x for x in facts if not (x in seen or seen.add(x))]
    return unique_facts[:8]

def build_okf_markdown(filename: str, content: str, patient_id: str = 'patient-001') -> str:
    doc_type = classify_document(filename, content)
    date_str = iso_date(content)
    base_name = os.path.splitext(os.path.basename(filename))[0]
    doc_id = f"{doc_type}-{date_str}-{slug(base_name)}"
    facts = extract_facts(content)
    
    hospital_fact = next((f for f in facts if f.startswith('Facility:')), None)
    hospital_name = hospital_fact.replace('Facility:', '').strip() if hospital_fact else ""

    doctor_fact = next((f for f in facts if f.startswith('Physician:')), None)
    doctor_name = doctor_fact.replace('Physician:', '').strip() if doctor_fact else ""

    links = [patient_id, f"timeline-{date_str}"]
    if hospital_name:
        links.append(slug(hospital_name))
    if doctor_name:
        links.append(slug(doctor_name))
        
    for fact in facts:
        if not fact.startswith('Facility:') and not fact.startswith('Physician:'):
            split_parts = re.split(r'[:–-]', fact)
            if split_parts:
                links.append(slug(split_parts[0]))
                
    seen_links = set()
    unique_links = [x for x in links if not (x in seen_links or seen_links.add(x))][:6]
    
    frontmatter = "---\n"
    frontmatter += f"id: {doc_id}\n"
    frontmatter += f"type: {doc_type}\n"
    frontmatter += f"patient_id: {patient_id}\n"
    frontmatter += f"date: {date_str}\n"
    if hospital_name:
        frontmatter += f'hospital: "{hospital_name}"\n'
    if doctor_name:
        frontmatter += f'doctor: "{doctor_name}"\n'
    frontmatter += f'source_file: "{filename}"\n'
    frontmatter += f"source_page: 1\n"
    frontmatter += "links:\n"
    for l in unique_links:
        frontmatter += f"  - {l}\n"
    frontmatter += "---\n"
    
    title = doc_type.replace('-', ' ').title()
    facts_str = "\n".join([f"- {f}" for f in facts]) if facts else "- No structured values detected; see source excerpt below."
    content_excerpt = excerpt(content) or "No readable text was supplied."
    
    markdown = f"""{frontmatter}
# {title}

## Extracted factual details
{facts_str}

## Source excerpt

{content_excerpt}

## Source

Original file: `{filename}`, page 1.
"""
    return markdown

def parse_frontmatter(markdown: str) -> dict:
    match = re.match(r'^---\n([\s\S]*?)\n---\n([\s\S]*)$', markdown)
    if not match:
        return {"meta": {}, "body": markdown}
        
    front_text = match.group(1)
    body_text = match.group(2).strip()
    
    meta = {}
    current_list_key = None
    
    for line in front_text.splitlines():
        list_match = re.match(r'^\s*-\s+(.+)$', line)
        if list_match and current_list_key:
            if current_list_key not in meta or not isinstance(meta[current_list_key], list):
                meta[current_list_key] = []
            val = list_match.group(1).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            meta[current_list_key].append(val)
            continue
            
        pair_match = re.match(r'^([a-z_]+):\s*(.*)$', line, re.IGNORECASE)
        if pair_match:
            current_list_key = pair_match.group(1)
            val = pair_match.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                meta[current_list_key] = val[1:-1]
            elif val == "":
                meta[current_list_key] = []
            else:
                meta[current_list_key] = val
                
    return {"meta": meta, "body": body_text}

