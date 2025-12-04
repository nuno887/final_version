from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

from main import process_pdf  # expects: process_pdf(pdf_path: Path) -> dict-like

# -----------------------
# Logging setup
# -----------------------

logger = logging.getLogger("api")

# If you want a basic config for local runs (Uvicorn also configures logging,
# so this is mainly useful when running `python api.py` directly)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# -----------------------
# Models
# -----------------------

class PdfPathRequest(BaseModel):
    path: str


# -----------------------
# App
# -----------------------

app = FastAPI(title="PDF Processor API")


# -----------------------
# Helpers
# -----------------------

def save_upload_to_temp(upload: UploadFile) -> Path:
    """
    Save an UploadFile to a temporary file on disk with no extra restrictions.
    Returns the Path to the temp file.
    """
    filename = upload.filename or "upload.pdf"
    suffix = Path(filename).suffix or ".pdf"

    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
    )
    tmp_path = Path(tmp.name)

    try:
        # Read and write in chunks (no size limit)
        while True:
            chunk = upload.file.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            tmp.write(chunk)

        tmp.flush()
        tmp.close()
    except Exception as e:
        tmp.close()
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        # LOG the error so it appears in console / docker logs
        logger.exception("Failed to store upload to temp file")
        raise HTTPException(status_code=400, detail=f"Failed to store upload: {e}")

    return tmp_path


# -----------------------
# Endpoints
# -----------------------

@app.post("/process-pdf")
def process_pdf_endpoint(req: PdfPathRequest):
    """
    Process a PDF given a filesystem path.

    NOTE: In Docker, this path must exist INSIDE the container.
    """
    pdf_path = Path(req.path)
    logger.info("Received request to process PDF from path: %s", pdf_path)

    if not pdf_path.exists():
        logger.warning("PDF not found at path: %s", pdf_path)
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_path}")

    try:
        result = process_pdf(pdf_path)
        logger.info("Successfully processed PDF from path: %s", pdf_path)
    except Exception as e:
        # This prints full traceback to console / docker logs
        logger.exception("Error while processing PDF from path: %s", pdf_path)
        raise HTTPException(status_code=500, detail=str(e))

    return result


@app.post("/process-pdf-upload")
async def process_pdf_upload(
    file: UploadFile = File(..., description="PDF file to process"),
):
    """
    Process a PDF uploaded as a file.
    This does not depend on any host filesystem path.
    """
    logger.info("Received file upload: %s", file.filename)
    temp_path: Optional[Path] = None

    try:
        # Save uploaded content to a temp file
        temp_path = save_upload_to_temp(file)
        logger.info("Saved uploaded file to temp path: %s", temp_path)

        # Reuse the same core function
        result = process_pdf(temp_path)
        logger.info("Successfully processed uploaded PDF: %s", file.filename)
        return result

    except HTTPException:
        # Already logged inside helpers or here before raising
        raise
    except Exception as e:
        logger.exception("Error while processing uploaded PDF: %s", file.filename)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
                logger.info("Deleted temp file: %s", temp_path)
            except Exception:
                logger.warning("Failed to delete temp file: %s", temp_path, exc_info=True)


@app.get("/health")
def health() -> Dict[str, Any]:
    logger.info("Health check requested")
    return {"status": "ok"}


# -----------------------
# Local dev entrypoint
# -----------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
