import requests
import datetime
from lib.okf_builder import build_okf_markdown

def fetch_fhir_patient(fhir_base: str, patient_id: str) -> dict:
    url = f"{fhir_base.rstrip('/')}/Patient/{patient_id}"
    r = requests.get(url, headers={"Accept": "application/fhir+json"}, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_fhir_resources(fhir_base: str, patient_id: str, resource_type: str) -> list:
    url = f"{fhir_base.rstrip('/')}/{resource_type}?patient={patient_id}"
    r = requests.get(url, headers={"Accept": "application/fhir+json"}, timeout=15)
    r.raise_for_status()
    bundle = r.json()
    resources = []
    for entry in bundle.get("entry", []):
        if "resource" in entry:
            resources.append(entry["resource"])
    return resources

def convert_fhir_medication_request(res: dict) -> str:
    med_name = "Prescription"
    if "medicationCodeableConcept" in res:
        med_name = res["medicationCodeableConcept"].get("text", "") or res["medicationCodeableConcept"].get("coding", [{}])[0].get("display", "Prescription")
    elif "medicationReference" in res:
        med_name = res["medicationReference"].get("display", "Prescription")
        
    date_str = res.get("authoredOn", "") or datetime.date.today().isoformat()
    if len(date_str) > 10:
        date_str = date_str[:10]
        
    dosage_text = "Take as directed"
    if "dosageInstruction" in res and res["dosageInstruction"]:
        dosage_text = res["dosageInstruction"][0].get("text", "") or res["dosageInstruction"][0].get("patientInstructionText", "Take as directed")
        
    doctor = "Unknown Clinician"
    if "requester" in res:
        doctor = res["requester"].get("display", "Dr. Sarah Jenkins")
        
    body = f"""# Prescription Details
- - {med_name} - {dosage_text}
- Physician: {doctor}
- Facility: Hospital Outpatient Care
"""
    doc_id = f"prescription-{date_str}-{res.get('id', 'imported')}"
    return build_okf_markdown(
        filename=f"{doc_id}.txt",
        content=body,
        patient_id="patient-temp",
        doc_type="prescription",
        doc_date=date_str,
        hospital="Hospital Outpatient Care",
        doctor=doctor
    )

def convert_fhir_observation(res: dict) -> str:
    test_name = "Lab Report"
    if "code" in res:
        test_name = res["code"].get("text", "") or res["code"].get("coding", [{}])[0].get("display", "Lab Report")
        
    date_str = res.get("effectiveDateTime", "") or datetime.date.today().isoformat()
    if len(date_str) > 10:
        date_str = date_str[:10]
        
    val_str = ""
    if "valueQuantity" in res:
        val = res["valueQuantity"].get("value", "")
        unit = res["valueQuantity"].get("unit", "")
        val_str = f"{val} {unit}".strip()
    elif "valueCodeableConcept" in res:
        val_str = res["valueCodeableConcept"].get("text", "")
    elif "component" in res:
        # e.g., Blood Pressure panel components
        comp_parts = []
        for comp in res["component"]:
            c_name = comp.get("code", {}).get("text", "") or comp.get("code", {}).get("coding", [{}])[0].get("display", "Test")
            c_val = comp.get("valueQuantity", {}).get("value", "")
            c_unit = comp.get("valueQuantity", {}).get("unit", "")
            comp_parts.append(f"{c_name}: {c_val} {c_unit}".strip())
        val_str = " | ".join(comp_parts)
        
    body = f"""# Lab Investigation Report
- - {test_name}: {val_str}
- Physician: Dr. Sunita Rao
- Facility: Clinical Pathology Labs
"""
    doc_id = f"lab-report-{date_str}-{res.get('id', 'imported')}"
    return build_okf_markdown(
        filename=f"{doc_id}.txt",
        content=body,
        patient_id="patient-temp",
        doc_type="lab-report",
        doc_date=date_str,
        hospital="Clinical Pathology Labs",
        doctor="Dr. Sunita Rao"
    )
