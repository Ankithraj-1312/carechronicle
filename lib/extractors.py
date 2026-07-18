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
        return text
    elif ext == 'docx':
        doc = docx.Document(io.BytesIO(buffer))
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext in ['txt', 'md', 'markdown']:
        return buffer.decode('utf-8', errors='ignore')
    else:
        raise ValueError(f"Unsupported file type: .{ext}")
