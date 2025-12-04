import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# 🔧 CHANGE THIS to the root folder where your PDFs live
PDF_ROOT_DIR = Path(r"D:\\joram").resolve()

# 🔧 DB file name
DB_PATH = Path("pdf_results_02-12-2025.db").resolve()

# 🔧 FastAPI endpoint
API_URL = "http://127.0.0.1:8000/process-pdf"

# 🔧 How many PDFs to process in parallel
MAX_WORKERS = 1  # you can try 4, 6, 8 depending on CPU/RAM


def init_db(db_path: Path):
    print(f"[DB] Initializing database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            status_code INTEGER,
            ok INTEGER NOT NULL,
            error_message TEXT,
            response_json TEXT,
            processed_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    print("[DB] Table pdf_results is ready.")
    return conn


def iter_pdfs(root: Path):
    """
    Recursively yield all .pdf files under root.
    """
    print(f"[SCAN] Walking directory: {root}")
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pdf"):
                pdf_path = Path(dirpath) / name
                print(f"[FOUND] {pdf_path}")
                yield pdf_path


def save_result(
    conn,
    file_path: Path,
    status_code: int | None,
    ok: bool,
    error_message: str | None,
    response_json: str | None,
):
    processed_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(
        f"[DB] Saving result for {file_path} | "
        f"status={status_code} ok={ok} at {processed_at}"
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO pdf_results
        (file_path, status_code, ok, error_message, response_json, processed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(file_path),
            status_code,
            1 if ok else 0,
            error_message,
            response_json,
            processed_at,
        ),
    )
    conn.commit()


def process_pdf_file(api_url: str, pdf_path: Path):
    """
    Worker function run in a thread.

    It ONLY talks to the API and returns the data needed
    for DB insertion. It does NOT touch SQLite.
    """
    print(f"[CALL] Sending to API: {pdf_path}")
    payload = {"path": str(pdf_path.resolve())}

    status_code: int | None = None
    ok = False
    response_json: str | None = None
    error_message: str | None = None

    try:
        # Using plain requests here; each thread has its own call
        resp = requests.post(api_url, json=payload, timeout=600)
        print(f"[CALL] Response {pdf_path} -> HTTP {resp.status_code}")

        status_code = resp.status_code
        ok = resp.ok

        if resp.ok:
            try:
                data = resp.json()
                response_json = json.dumps(data, ensure_ascii=False)
                error_message = None
                print(f"[OK] Parsed JSON for {pdf_path}")
            except json.JSONDecodeError as e:
                response_json = None
                error_message = f"JSON decode error: {e}; raw={resp.text}"
                print(f"[ERROR] JSON decode error for {pdf_path}: {e}")
        else:
            response_json = None
            error_message = resp.text
            print(f"[ERROR] Non-OK status for {pdf_path}: {status_code}")

    except requests.RequestException as e:
        status_code = None
        ok = False
        response_json = None
        error_message = f"Request error: {e}"
        print(f"[ERROR] Request failed for {pdf_path}: {e}")

    # Return everything so the main thread can save to DB
    return pdf_path, status_code, ok, error_message, response_json


def main():
    print("======================================")
    print(" PDF Batch Processor (Concurrent)")
    print("======================================")
    print(f"[CONFIG] PDF_ROOT_DIR = {PDF_ROOT_DIR}")
    print(f"[CONFIG] DB_PATH      = {DB_PATH}")
    print(f"[CONFIG] API_URL      = {API_URL}")
    print(f"[CONFIG] MAX_WORKERS  = {MAX_WORKERS}")
    print("")

    conn = init_db(DB_PATH)

    # 👉 Load already processed file paths from DB  # <<< ADDED
    cursor = conn.execute("SELECT file_path FROM pdf_results")  # <<< ADDED
    existing_paths = {row[0] for row in cursor.fetchall()}      # <<< ADDED
    print(f"[DB] Already have {len(existing_paths)} records in pdf_results")  # <<< ADDED

    # Collect all PDFs first (30k paths is fine)
    all_pdf_files = list(iter_pdfs(PDF_ROOT_DIR))
    total_found = len(all_pdf_files)
    print(f"[INFO] Total PDFs found on disk: {total_found}")

    # 👉 Filter out the ones that are already in the DB  # <<< ADDED
    pdf_files = []
    skipped = 0
    for p in all_pdf_files:
        if str(p) in existing_paths:
            skipped += 1
            print(f"[SKIP] Already in DB, skipping: {p}")
        else:
            pdf_files.append(p)

    total = len(pdf_files)
    print(f"[INFO] PDFs to process (not in DB): {total}")
    print(f"[INFO] PDFs skipped (already in DB): {skipped}")
    print("")

    if total == 0:
        print("[INFO] Nothing new to process. Exiting.")
        return

    success = 0
    failed = 0

    # Use a thread pool for concurrent API calls
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_pdf = {
            executor.submit(process_pdf_file, API_URL, pdf_path): pdf_path
            for pdf_path in pdf_files
        }

        for i, future in enumerate(as_completed(future_to_pdf), start=1):
            pdf_path = future_to_pdf[future]
            try:
                (
                    file_path,
                    status_code,
                    ok,
                    error_message,
                    response_json,
                ) = future.result()
            except Exception as e:
                # Catch any unexpected error in the worker
                print(f"[ERROR] Worker crashed for {pdf_path}: {e}")
                file_path = pdf_path
                status_code = None
                ok = False
                error_message = f"Worker exception: {e}"
                response_json = None

            # Save in DB (main thread only)
            save_result(conn, file_path, status_code, ok, error_message, response_json)

            if ok:
                success += 1
            else:
                failed += 1

            print(
                f"[PROGRESS] {i}/{total} processed | "
                f"success={success} failed={failed}"
            )
            print("--------------------------------------")

    print("======================================")
    print(" DONE")
    print("======================================")
    print(f"Total PDFs found      : {total_found}")
    print(f"Skipped (in DB)       : {skipped}")
    print(f"Processed this run    : {total}")
    print(f"Success (2xx)         : {success}")
    print(f"Failed / errors       : {failed}")
    print("Results saved in      :", DB_PATH)


if __name__ == "__main__":
    main()
