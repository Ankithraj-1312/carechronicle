import json
import os
import re

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "patients.json")

def load_patient_registry() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return {
            'patient-001': 'Ananya Sharma',
            'patient-002': 'Ravi Mehta',
            'patient-003': 'Emily Chen',
            'patient-004': 'Priya Nair'
        }
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {p["id"]: p["name"] for p in data.get("patients", [])}
    except Exception as e:
        print(f"Error loading patient registry: {e}")
        return {}

def save_patient_registry(patients_dict: dict):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    patients_list = [{"id": pid, "name": name} for pid, name in patients_dict.items()]
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump({"patients": patients_list}, f, indent=2)
    except Exception as e:
        print(f"Error saving patient registry: {e}")

def get_next_patient_id() -> str:
    registry = load_patient_registry()
    max_num = 0
    for pid in registry.keys():
        match = re.match(r'patient-(\d+)', pid)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return f"patient-{str(max_num + 1).zfill(3)}"

def get_patient_name(patient_id: str) -> str:
    registry = load_patient_registry()
    if patient_id in registry:
        return registry[patient_id]
    return " ".join([p.capitalize() for p in patient_id.split('-')])

# Dynamic attribute lookup for backward compatibility
def __getattr__(name):
    if name == 'PATIENT_NAMES':
        return load_patient_registry()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

def build_patient_profile(records: list, patient_id: str) -> dict:
    patient_name = get_patient_name(patient_id)
    medications = {}
    tests = {}
    hospitals = set()
    doctors = set()
    conditions = set()

    sorted_records = sorted(records, key=lambda r: str(r.get("meta", {}).get("date", "")))

    for record in sorted_records:
        meta = record.get("meta", {})
        body = record.get("body", "")
        date = meta.get("date", "")
        doc_type = meta.get("type", "")

        if meta.get("hospital"):
            hospitals.add(meta.get("hospital"))
        if meta.get("doctor"):
            doctors.add(meta.get("doctor"))

        if doc_type == 'discharge-summary':
            match = re.search(r'(?:diagnosis|diagnosed with|admitted for|reason for admission)[:\s]+([^\n.]+)', body, re.IGNORECASE)
            if match:
                conditions.add(match.group(1).strip())

        lines = body.splitlines()
        for line in lines:
            clean_line = line.strip()
            if not clean_line.startswith("- "):
                continue
            fact_text = clean_line[2:]

            if fact_text.startswith("Physician:") or fact_text.startswith("Facility:"):
                continue

            is_med = any(term in fact_text.lower() for term in [
                'prescription', 'rx', 'tablet', 'capsule', 'mg', 'mcg', 'dose',
                'paracetamol', 'amoxicillin', 'metformin', 'insulin', 'atorvastatin',
                'aspirin', 'cetirizine', 'pantoprazole', 'ibuprofen', 'losartan',
                'amlodipine', 'metoprolol', 'lisinopril', 'gabapentin', 'omeprazole',
                'acetaminophen', 'albuterol', 'synthroid', 'clopidogrel', 'warfarin',
                'levothyroxine', 'ramipril', 'hydrochlorothiazide', 'furosemide'
            ])
            if is_med and doc_type == 'prescription':
                digit_split = re.split(r'\d', fact_text)
                med_name = digit_split[0].strip().lower() if digit_split else fact_text.lower()
                if len(med_name) > 2:
                    medications[med_name] = {
                        "name": med_name.title(),
                        "date": date,
                        "detail": fact_text
                    }

            is_lab = any(term in fact_text.lower() for term in [
                'hemoglobin', 'haemoglobin', 'glucose', 'cholesterol', 'platelet',
                'creatinine', 'thyroid', 'vitamin d', 'hba1c', 'blood pressure',
                'wbc', 'rbc', 'ldl', 'hdl'
            ])
            if is_lab and doc_type == 'lab-report':
                parts = re.split(r'[:–-]', fact_text, maxsplit=1)
                test_name = parts[0].strip().lower()
                test_val = parts[1].strip() if len(parts) > 1 else fact_text
                if len(test_name) > 2:
                    tests[test_name] = {
                        "name": test_name.title(),
                        "date": date,
                        "value": test_val,
                        "detail": fact_text
                    }

    active_meds = sorted(medications.values(), key=lambda x: x["date"], reverse=True)
    recent_tests = sorted(tests.values(), key=lambda x: x["date"], reverse=True)

    timeline = []
    for r in sorted(records, key=lambda x: str(x.get("meta", {}).get("date", "")), reverse=True):
        meta = r.get("meta", {})
        body = r.get("body", "")
        lines = [line.strip()[2:] for line in body.splitlines() if line.strip().startswith("- ")]
        excerpt_text = "; ".join(lines[:3]) if lines else body[:150]
        
        timeline.append({
            "id": meta.get("id"),
            "file": r.get("file"),
            "date": meta.get("date"),
            "type": meta.get("type"),
            "hospital": meta.get("hospital", ""),
            "doctor": meta.get("doctor", ""),
            "title": meta.get("type", "").replace("-", " ").title(),
            "excerpt": excerpt_text
        })

    return {
        "patientId": patient_id,
        "name": patient_name,
        "conditions": list(conditions) if conditions else ["Routine health monitoring"],
        "medications": active_meds,
        "tests": recent_tests,
        "hospitals": list(hospitals),
        "doctors": list(doctors),
        "timeline": timeline
    }
