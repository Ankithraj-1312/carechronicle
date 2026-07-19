import io
import os
import docx
from pypdf import PdfReader

def ocr_via_gemini(buffer: bytes, ext: str) -> str:
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is not set in environment variables.")
    
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    mime_type = f"image/{ext}" if ext != 'jpg' else 'image/jpeg'
    
    contents = [
        {
            'mime_type': mime_type,
            'data': buffer
        },
        "Extract all readable text from this clinical document/prescription image exactly as written. Do not add any introductory text, headers, explanation, or markdown formatting. Just return the raw text."
    ]
    response = model.generate_content(contents)
    return response.text or ""

def extract_text(buffer: bytes, filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    
    if ext == 'pdf':
        reader = PdfReader(io.BytesIO(buffer))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            
        # Scanned PDF Check: if extracted text is very short/empty, try OCR fallback
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
    elif ext == 'docx':
        doc = docx.Document(io.BytesIO(buffer))
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext in ['png', 'jpg', 'jpeg']:
        try:
            from PIL import Image
            import pytesseract
            img = Image.open(io.BytesIO(buffer))
            return pytesseract.image_to_string(img) or ""
        except Exception as e:
            try:
                print(f"[INFO] Tesseract failed or not installed. Attempting Gemini multimodal fallback...")
                return ocr_via_gemini(buffer, ext)
            except Exception as gemini_err:
                print(f"[WARN] Gemini OCR fallback failed: {str(gemini_err)}")
                raise ValueError(f"OCR failed for image .{ext}: {str(e)}. (Gemini fallback also failed: {str(gemini_err)})")
    elif ext in ['txt', 'md', 'markdown']:
        return buffer.decode('utf-8', errors='ignore')
    else:
        raise ValueError(f"Unsupported file type: .{ext}")



