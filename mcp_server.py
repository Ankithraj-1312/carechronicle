import os
import sys
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("CareChronicle")

from lib.extractors import extract_text
from lib.okf_builder import build_okf_markdown, parse_frontmatter, slug
from lib.llm import safety_check, plan_query, generate_answer, run_qa_pipeline
from lib.wiki import build_patient_profile

# Define the base directory for patient data
ROOT = os.getcwd()
PATIENTS_DIR = os.path.join(ROOT, "data", "okf", "patients")

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
            records.append({
                "file": name,
                "meta": parsed["meta"],
                "body": parsed["body"]
            })
    records.sort(key=lambda r: str(r.get("meta", {}).get("date", "")), reverse=True)
    return records

def rank_records_smarter(query: str, keywords: list, types: list, records: list) -> list:
    import re
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

@mcp.tool()
def convert_text_to_okf(filename: str, content: str, patient_id: str = "patient-001") -> str:
    """Converts raw medical text to an OKF Markdown string.
    
    Args:
        filename: The name of the file (e.g. prescription.txt).
        content: The raw text content.
        patient_id: The ID of the patient.
    """
    return build_okf_markdown(filename, content, patient_id)

@mcp.tool()
def ingest_document_file(filepath: str, patient_id: str = "patient-001") -> dict:
    """Reads a local file (PDF/DOCX/TXT/MD), converts it to OKF, and saves it in the patient's record folder.
    
    Args:
        filepath: Absolute path to the file.
        patient_id: The ID of the patient.
    """
    if not os.path.exists(filepath):
        return {"error": f"File not found: {filepath}"}
    
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            buffer = f.read()
        extracted_text = extract_text(buffer, filename)
    except Exception as e:
        return {"error": f"Failed to read/parse file: {str(e)}"}
        
    if not extracted_text.strip():
        return {"error": "Document does not contain any readable text."}
        
    p_dir = os.path.join(PATIENTS_DIR, patient_id)
    os.makedirs(p_dir, exist_ok=True)
    
    markdown = build_okf_markdown(filename, extracted_text, patient_id)
    parsed = parse_frontmatter(markdown)
    doc_id = parsed["meta"].get("id")
    
    dest_path = os.path.join(p_dir, f"{doc_id}.md")
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(markdown)
        
    return {
        "success": True,
        "message": f"Successfully ingested and converted to OKF.",
        "id": doc_id,
        "path": dest_path,
        "type": parsed["meta"].get("type"),
        "date": parsed["meta"].get("date")
    }

@mcp.tool()
def get_patient_wiki_profile(patient_id: str = "patient-001") -> dict:
    """Reads all OKF records for a patient and compiles the dynamic profile.
    
    Args:
        patient_id: The ID of the patient.
    """
    records = list_records(patient_id)
    return build_patient_profile(records, patient_id)

@mcp.tool()
def list_patient_records(patient_id: str = "patient-001") -> list:
    """Lists all structured records (metadata and excerpt) stored in the patient's directory.
    
    Args:
        patient_id: The ID of the patient.
    """
    records = list_records(patient_id)
    # Simplify output format to make it token-friendly for MCP client
    simplified = []
    for r in records:
        meta = r.get("meta", {})
        body = r.get("body", "")
        # Get excerpt
        import re
        lines = [line.strip()[2:] for line in body.splitlines() if line.strip().startswith("- ")]
        excerpt_text = "; ".join(lines[:2]) if lines else body[:150]
        simplified.append({
            "id": meta.get("id"),
            "type": meta.get("type"),
            "date": meta.get("date"),
            "hospital": meta.get("hospital"),
            "doctor": meta.get("doctor"),
            "source_file": meta.get("source_file"),
            "excerpt": excerpt_text
        })
    return simplified

@mcp.tool()
async def search_okf_records(query: str, patient_id: str = "patient-001") -> list:
    """Performs search/retrieval part by running query planning and ranking, returning matched relevant OKF records.
    
    Args:
        query: The clinical search query.
        patient_id: The ID of the patient.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    plan = await plan_query(query, api_key)
    all_records = list_records(patient_id)
    matched = rank_records_smarter(query, plan.get("keywords", []), plan.get("types", ["any"]), all_records)
    
    # Simplify matched records for prompt usage
    simplified = []
    for r in matched:
        meta = r.get("meta", {})
        simplified.append({
            "id": meta.get("id"),
            "type": meta.get("type"),
            "date": meta.get("date"),
            "hospital": meta.get("hospital"),
            "doctor": meta.get("doctor"),
            "source_file": meta.get("source_file"),
            "body": r.get("body", "")
        })
    return simplified

@mcp.tool()
async def query_patient_records(query: str, patient_id: str = "patient-001") -> dict:
    """Executes the complete clinical Q&A pipeline (Safety, Planning, Retrieval, and GenAI Answer).
    
    Args:
        query: The question about the patient's record.
        patient_id: The ID of the patient.
    """
    all_records = list_records(patient_id)
    result = await run_qa_pipeline(query, patient_id, all_records, rank_records_smarter)
    return result

if __name__ == "__main__":
    mcp.run()
