import io
import docx
from pypdf import PdfReader

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
    elif ext in ['txt', 'md', 'markdown']:
        return buffer.decode('utf-8', errors='ignore')
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

