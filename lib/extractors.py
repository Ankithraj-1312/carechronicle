import io
import os
import base64
import docx
from pypdf import PdfReader

OCR_PROMPT = (
    "Extract all readable text from this clinical document/prescription image exactly "
    "as written. Do not add any introductory text, headers, explanation, or markdown "
    "formatting. Just return the raw text."
)

# ---------------------------------------------------------------------------
# OCR backend: Ollama (local, privacy-first)
# ---------------------------------------------------------------------------
def ocr_via_ollama(buffer: bytes, ext: str) -> str:
    """Use a locally running Ollama vision model (e.g. llava) for OCR.
    
    Ollama must be running: `ollama serve`
    A vision model must be pulled: `ollama pull llava`
    
    No data leaves the machine — fully HIPAA-safe.
    """
    import requests

    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llava")
    b64_image = base64.b64encode(buffer).decode("utf-8")

    payload = {
        "model": ollama_model,
        "messages": [
            {
                "role": "user",
                "content": OCR_PROMPT,
                "images": [b64_image]
            }
        ],
        "stream": False
    }

    resp = requests.post(
        f"{ollama_host}/api/chat",
        json=payload,
        timeout=60  # vision inference can take a moment locally
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "") or ""


# ---------------------------------------------------------------------------
# OCR backend: Groq (cloud fallback)
# ---------------------------------------------------------------------------
def ocr_via_groq(buffer: bytes, ext: str) -> str:
    """Use Groq's hosted vision model as a cloud fallback for OCR."""
    groq_key = os.environ.get("Groq_API_KEY", "")
    if not groq_key:
        raise ValueError("Groq_API_KEY is not set in environment variables.")

    from groq import Groq

    client = Groq(api_key=groq_key)
    mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"
    b64_image = base64.b64encode(buffer).decode("utf-8")

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}
                    },
                    {
                        "type": "text",
                        "text": OCR_PROMPT
                    }
                ]
            }
        ]
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------
def extract_text(buffer: bytes, filename: str) -> str:
    ext = filename.lower().split(".")[-1]

    if ext == "pdf":
        reader = PdfReader(io.BytesIO(buffer))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        # Scanned PDF: if extracted text is very short/empty, try OCR fallback
        if len(text.strip()) < 100:
            try:
                from pdf2image import convert_from_bytes
                import pytesseract
                images = convert_from_bytes(buffer)
                ocr_text = ""
                for img in images:
                    ocr_text += pytesseract.image_to_string(img) or ""
                if len(ocr_text.strip()) >= 10:
                    text = ocr_text
            except Exception as e:
                print(f"[WARN] Scanned PDF detected, but OCR fallback failed: {str(e)}")

        return text

    elif ext == "docx":
        doc = docx.Document(io.BytesIO(buffer))
        return "\n".join([p.text for p in doc.paragraphs])

    elif ext in ["png", "jpg", "jpeg"]:
        # 1. Try Tesseract (fastest, fully local)
        try:
            from PIL import Image
            import pytesseract
            img = Image.open(io.BytesIO(buffer))
            result = pytesseract.image_to_string(img) or ""
            if result.strip():
                return result
            raise ValueError("Tesseract returned empty text.")
        except Exception as tess_err:
            print(f"[INFO] Tesseract unavailable or returned empty: {tess_err}")

        # 2. Try Ollama (local LLM — no data leaves the machine)
        try:
            print("[INFO] Attempting Ollama local vision OCR...")
            result = ocr_via_ollama(buffer, ext)
            if result.strip():
                print("[INFO] Ollama OCR succeeded.")
                return result
            raise ValueError("Ollama returned empty text.")
        except Exception as ollama_err:
            print(f"[WARN] Ollama OCR failed: {ollama_err}")

        # 3. Fall back to Groq (cloud)
        try:
            print("[INFO] Attempting Groq cloud vision OCR...")
            result = ocr_via_groq(buffer, ext)
            if result.strip():
                print("[INFO] Groq OCR succeeded.")
                return result
            raise ValueError("Groq returned empty text.")
        except Exception as groq_err:
            raise ValueError(
                f"All OCR backends failed for image .{ext}. "
                f"Tesseract: not installed or empty. "
                f"Ollama: {ollama_err}. "
                f"Groq: {groq_err}."
            )

    elif ext in ["txt", "md", "markdown"]:
        return buffer.decode("utf-8", errors="ignore")

    else:
        raise ValueError(f"Unsupported file type: .{ext}")
