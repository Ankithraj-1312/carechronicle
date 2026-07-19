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
# OCR backend: Gemini (cloud fallback — uses existing GEMINI_API_KEY)
# ---------------------------------------------------------------------------
def ocr_via_gemini(buffer: bytes, ext: str) -> str:
    """Use Google Gemini vision model for OCR.
    Requires GEMINI_API_KEY to be set in environment variables.
    Uses gemini-3.5-flash by default; override with GEMINI_VISION_MODEL.
    """
    import google.generativeai as genai

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is not set in environment variables.")

    genai.configure(api_key=gemini_key)

    model_name = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.5-flash")
    model = genai.GenerativeModel(model_name)

    mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"
    image_part = {"mime_type": mime_type, "data": buffer}

    response = model.generate_content([OCR_PROMPT, image_part])
    return response.text or ""


# ---------------------------------------------------------------------------
# OCR backend: Groq (cloud fallback)
# ---------------------------------------------------------------------------

# Vision-capable models on Groq, in priority order.
# Override with env var GROQ_VISION_MODEL if needed.
_GROQ_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llava-v1.5-7b-4096-preview",
]

def ocr_via_groq(buffer: bytes, ext: str) -> str:
    """Use Groq's hosted vision model as a cloud fallback for OCR.
    Tries each model in _GROQ_VISION_MODELS until one succeeds.
    """
    groq_key = os.environ.get("Groq_API_KEY", "")
    if not groq_key:
        raise ValueError("Groq_API_KEY is not set in environment variables.")

    from groq import Groq

    client = Groq(api_key=groq_key)
    mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"
    b64_image = base64.b64encode(buffer).decode("utf-8")

    # Allow override via env var
    env_model = os.environ.get("GROQ_VISION_MODEL", "")
    models_to_try = [env_model] + _GROQ_VISION_MODELS if env_model else _GROQ_VISION_MODELS

    # Get list of available model IDs to skip unavailable ones fast
    try:
        available_ids = {m.id for m in client.models.list().data}
    except Exception:
        available_ids = set()  # If listing fails, try all anyway

    last_err = None
    for model_id in models_to_try:
        # Skip if we know it's not on this account
        if available_ids and model_id not in available_ids:
            continue
        try:
            response = client.chat.completions.create(
                model=model_id,
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
        except Exception as e:
            last_err = e
            print(f"[WARN] Groq model {model_id} failed: {e}")
            continue

    raise ValueError(
        f"No Groq vision model is available on this API key. "
        f"Tried: {models_to_try}. Last error: {last_err}. "
        f"Set GROQ_VISION_MODEL in .env to a vision-capable model."
    )


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

        ollama_error_str = "Not run"
        try:
            print("[INFO] Attempting Ollama local vision OCR...")
            result = ocr_via_ollama(buffer, ext)
            if result.strip():
                print("[INFO] Ollama OCR succeeded.")
                return result
            raise ValueError("Ollama returned empty text.")
        except Exception as ollama_err:
            ollama_error_str = str(ollama_err)
            print(f"[WARN] Ollama OCR failed: {ollama_error_str}")

        # 3. Fall back to Gemini (cloud — uses existing GEMINI_API_KEY)
        gemini_error_str = "Not run"
        try:
            print("[INFO] Attempting Gemini cloud vision OCR...")
            result = ocr_via_gemini(buffer, ext)
            if result.strip():
                print("[INFO] Gemini OCR succeeded.")
                return result
            raise ValueError("Gemini returned empty text.")
        except Exception as gemini_err:
            gemini_error_str = str(gemini_err)
            print(f"[WARN] Gemini OCR failed: {gemini_error_str}")

        # 4. Fall back to Groq (cloud)
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
                f"Ollama: {ollama_error_str}. "
                f"Gemini: {gemini_error_str}. "
                f"Groq: {groq_err}."
            )

    elif ext in ["txt", "md", "markdown"]:
        return buffer.decode("utf-8", errors="ignore")

    else:
        raise ValueError(f"Unsupported file type: .{ext}")
