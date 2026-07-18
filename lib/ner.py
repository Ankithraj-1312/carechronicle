import os
import sys
import json

NER_PROMPT = """You are a clinical entity extractor.
From the medical document below, extract:
- medications: list of {{ name, dose, frequency }}
- lab_results: list of {{ test_name, value, unit, flag }}
- conditions: list of diagnosis strings

Respond ONLY in this JSON format:
{{
  "medications": [
    {{ "name": "Metformin", "dose": "500 mg", "frequency": "twice daily with meals" }}
  ],
  "lab_results": [
    {{ "test_name": "Haemoglobin", "value": "10.8", "unit": "g/dL", "flag": "LOW" }}
  ],
  "conditions": ["Iron Deficiency Anaemia", "Hypertension"]
}}

If any section has no data, leave it as an empty list. Do not include any explanation, notes, or wrapper other than the raw JSON.

Document:
{text}
"""

def extract_clinical_entities(text: str) -> dict:
    prompt = NER_PROMPT.format(text=text)
    
    ollama_host = os.environ.get("OLLAMA_HOST", "")
    groq_key = os.environ.get("Groq_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    
    # 1. Try Ollama (Local)
    if ollama_host:
        try:
            from lib.llm import call_ollama_api, parse_json_from_text
            res = call_ollama_api(prompt, response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("Clinical NER Ollama error:", str(e), file=sys.stderr)
            
    # 2. Try Groq (Cloud)
    if groq_key:
        try:
            from lib.llm import call_groq_api, parse_json_from_text
            res = call_groq_api([{"role": "user", "content": prompt}], response_format_json=True)
            return parse_json_from_text(res)
        except Exception as e:
            print("Clinical NER Groq error:", str(e), file=sys.stderr)
            
    # 3. Try Gemini (Cloud)
    if gemini_key:
        try:
            from lib.llm import call_gemini_api, parse_json_from_text
            res = call_gemini_api(prompt, gemini_key, "application/json")
            return parse_json_from_text(res)
        except Exception as e:
            print("Clinical NER Gemini error:", str(e), file=sys.stderr)
            
    # 4. Offline / Rule-Based Fallback (if no API keys or local host works)
    # Return empty format
    return {"medications": [], "lab_results": [], "conditions": []}
