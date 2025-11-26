from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import process_pdf 

class PdfPathRequest(BaseModel):
    path: str

app = FastAPI()

PDF_INPUT_DIR = Path("pdf_input")  

@app.post("/process-pdf")
def process_pdf_endpoint(req: PdfPathRequest):
    pdf_path = Path(req.path)

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_path}")
    
    try:
        result = process_pdf(pdf_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result
