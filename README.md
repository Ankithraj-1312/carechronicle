# 🏥 CareChronicle — Patient Record Intelligence

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/LLM-Groq--LLaMA_3.3-orange.svg)](https://groq.com/)
[![MCP](https://img.shields.io/badge/Protocol-MCP-blue.svg)](https://modelcontextprotocol.io/)

**CareChronicle** is an AI-powered clinical intelligence platform and document workspace designed to transform unstructured clinical files (PDFs, DOCX, TXT, MD) into structured, queryable knowledge graphs. Built with a Model Context Protocol (MCP) native design, it indexes historical health data into the **Open Knowledge Format (OKF)** and provides source-cited, doctor-grounded Q&A with ultra-low LLM cost profiles.

---

## 📸 Interface Preview
* **Dynamic Sidebar**: Highlights active conditions, active medications, and diagnostic tests extracted in real-time from the patient's records.
* **Visual Timeline**: Reconstructs patient history chronologically with inline preview modals for raw OKF markdown sources.
* **Grounded Chat**: Double-classification pipeline providing cited answers back to exact Record IDs with built-in clinical safety checks.
* **Glassmorphism Theme**: Sleek, responsive dark mode optimized for Windows/Chrome/Edge with smooth typewriter animations.

---

## ⚡ Architecture Flow

```mermaid
graph TD
    User([User Document / Query]) -->|Upload PDF/DOCX/TXT| Parser[extractors.py & okf_builder.py]
    Parser -->|Parse Frontmatter & Facts| OKF[(OKF Markdown Directory)]
    OKF -->|Build Patient Profile| Wiki[wiki.py Profiler]
    Wiki -->|Render Dashboard Stats & Timeline| UI[Front-End Web UI]

    User -->|Ask Question| QueryPipeline[llm.py: run_qa_pipeline]
    QueryPipeline -->|Classify Query| Classifier{Is Document Query?}
    
    Classifier -->|No: General Health Q| GenAns[1x Groq/Gemini Call]
    Classifier -->|Yes: Patient Chart Q| Plan[Local Query Planner: 0 LLM Calls]
    
    Plan -->|Rank & Retrieve| Retrieval[rank_records_smarter]
    Retrieval -->|Cited Answer Generation| DocAns[1x Groq/Gemini Call]
    
    GenAns --> UI
    DocAns --> UI
```

---

## 🌟 Hackathon Winning Features

### 1. 📂 Open Knowledge Format (OKF) Structured Markdown
Instead of a database, CareChronicle maps records to highly structured markdown documents featuring standard frontmatter. This flat-file storage design keeps patient details completely human-readable, easily auditable, and version-controlled.
```yaml
---
id: lab-report-2026-07-01-diabetic-check-2026-07-01
type: lab-report
patient_id: patient-002
date: 2026-07-01
hospital: "Apex Diagnostics"
doctor: "Dr. Patel"
source_file: "diabetic-check-2026-07-01.txt"
links:
  - patient-002
  - glucose-fasting
  - hba1c
---
# Lab Report
## Extracted factual details
- Glucose (Fasting): 140 mg/dL
- HbA1c: 7.4 %
```

### 2. 🔌 Native Model Context Protocol (MCP) Server
CareChronicle is agent-ready out-of-the-box. It runs a parallel FastMCP server exposing 6 powerful tools for AI agents (like Claude Desktop, Gemini, etc.):
- `convert_text_to_okf` — Convert raw text data to OKF.
- `ingest_document_file` — Ingest local files automatically.
- `get_patient_wiki_profile` — Compile patient summaries.
- `list_patient_records` — List structured files in directory.
- `search_okf_records` — Query planner search.
- `query_patient_records` — Complete safety-first answering tool.

### 3. 📉 Cost-Optimization: Double Classification Pipeline
Traditional RAG pipelines make expensive LLM calls for safety checking, query planning, and answering. CareChronicle uses:
- **Local Keywords Classifier** (`is_document_query`) to route general vs. chart queries.
- **General Queries**: Direct prompt bypass. Uses **exactly 1 LLM call** to answer.
- **Document Queries**: Local parser maps keywords and record types (**0 LLM calls**). Finds records, then triggers **exactly 1 LLM call** to synthesize the answer.
- **Result**: Zero safety-checking API waste, ultra-low token consumption, and sub-second answer speeds on Groq.

### 🛡️ 3-Tier Robust Fallback System
The QA retriever relies on safety failovers:
- **Tier 1 (Primary)**: High-speed Groq LLaMA 3.3 70B REST API.
- **Tier 2 (Fallback)**: Google Gemini Pro API.
- **Tier 3 (Offline)**: Deterministic, local regex rule-based parser compiling highlights from documents (works with 0 internet connection or invalid API keys).

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.10+
- Groq API Key and/or Google Gemini API Key

### Step 1: Clone and Install Dependencies
```bash
git clone https://github.com/your-username/carechronicle.git
cd carechronicle
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Create a `.env` file in the root directory:
```env
PORT=3005
Groq_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
```

### Step 3: Run the Platform
Start the FastAPI server:
```bash
python main.py
```
Open your browser and navigate to **`http://localhost:3005`**.

---

## 📂 Project Directory Structure

```
├── data/
│   └── okf/
│       └── patients/        # Flat-file structured OKF patient directory
├── lib/
│   ├── extractors.py        # PDF/DOCX/TXT text parsing extraction
│   ├── llm.py               # Double-classification QA pipeline & fallbacks
│   ├── okf_builder.py       # Raw files → structured OKF markdown conversion
│   └── wiki.py              # Sidebar clinical statistics compiler
├── public/
│   ├── app.js               # Typewriter response engine & websocket mock upload
│   ├── index.html           # Main dashboard interface layout
│   └── styles.css           # Custom glassmorphic styling
├── main.py                  # FastAPI Application router & endpoints
├── mcp_server.py            # FastMCP server integration
├── requirements.txt         # Project requirements
└── README.md                # System documentation
```

---

## 🧪 Quick Test Scenarios
To showcase the clinical intelligence during a live demo:
1. **General Query Routing**: Ask *"What is type-2 diabetes?"* — Notice it answers instantly with clinical details and normal thresholds without checking patient records.
2. **Medication Grounding**: Select **Ravi Mehta** and ask *"What is my Metformin dose?"* — The response extracts `Metformin 500 mg` twice daily directly from the prescription record and cites Dr. Patel.
3. **Lab Result Progression**: Select **Ananya Sharma** and ask *"What was my latest hemoglobin?"* — System extracts `10.2 g/dL` from `cbc-report-2026-07-16` and maps the timeline.
4. **Offline Mode Validation**: Delete API keys from `.env` and restart. Ask a question — notice the system still produces structured, cited answers using the Tier 3 offline parser!

---

## 📝 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
