from __future__ import annotations

import pathlib
import argparse
import html as html_lib
from spacy import displacy
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List
import json

from split_text import split_text
from pdf_markup import extract_pdf_to_markdown
from spacy_modulo import get_nlp, setup_entities, setup_entitiesIV
from relation_extractor_02 import sumario_dic, has_letters_ignoring_newlines, clean_sumario, sumario_to_blocks
from results import build_sumario_docs_from_grouped_blocks, classBuilder, classBuilder_III


OPTIONS = {
    "colors": {
        "Sumario": "#ffd166",
        "ORG_LABEL": "#6e77b8",
        "ORG_WITH_STAR_LABEL": "#6fffff",
        "DOC_NAME_LABEL": "#b23bbd",
        "DOC_TEXT": "#47965e",
        "PARAGRAPH": "#14b840",
        "JUNK_LABEL": "#e11111",
        "SERIE_III": "#D1B1B1",
        "ASSINATURA": "#d894df",
    }
}


def is_serie(filename: str) -> bool:
    return "iiiserie" in filename.lower()


def make_error_result(
    message: str,
    stage: str,
    code: str,
    pdf: Optional[Path] = None,
    raw_text: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the global result structure when something goes wrong.
    docs is always an empty list in this case.
    """
    error: Dict[str, Any] = {
        "stage": stage,          # e.g. "extract_pdf", "nlp", "split_text"
        "code": code,            # e.g. "memory_error", "unexpected_exception"
        "message": message,
        "pdf": str(pdf) if pdf else None,
    }
    if extra:
        error.update(extra)

    return {
        "error": error,
        "raw_text": raw_text,
        "docs": [],
    }


def make_ok_result(
    raw_text: str,
    docs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the global result structure for the success path.
    """
    return {
        "error": None,
        "raw_text": raw_text,
        "docs": docs,
    }


def normalize_serie_iii_docs(raw_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    III Série already looks like:
    [
      { "header_texts": [], "org_texts": [...], "doc_name": "...", "body": "..." },
      ...
    ]
    We just ensure keys exist.
    """
    normalized = []
    for d in raw_docs:
        normalized.append({
            "header_texts": d.get("header_texts", []),
            "org_texts": d.get("org_texts", []),
            "doc_name": d.get("doc_name", ""),
            "body": d.get("body", ""),
            # org_idx optional, won't exist for III série
            "org_idx": d.get("org_idx"),
        })
    return normalized


def normalize_other_docs(raw_by_org: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Other séries come as:
    {
      "0": [ { header_texts, org_idx, org_name, doc_name, body, ... }, ... ],
      "1": [ ... ],
      ...
    }

    We flatten into a single list of docs with `org_texts` instead of `org_name`.
    """
    normalized: List[Dict[str, Any]] = []

    for _, doc_list in raw_by_org.items():
        for d in doc_list:
            normalized.append({
                "header_texts": d.get("header_texts", []),
                "org_texts": [d["org_name"]] if "org_name" in d else [],
                "doc_name": d.get("doc_name", ""),
                "body": d.get("body", ""),
                "org_idx": d.get("org_idx"),
            })

    return normalized


def build_dicts(nlp, full_text: str):
    """
    Returns (doc, sumario_dict, body_dict)
    or (None, None, None) if something went wrong (e.g. MemoryError).
    """
    sumario_dict = None
    body_dict = None

    # --- spaCy processing ---
    try:
        doc = nlp(full_text)
    except MemoryError:
        print("⚠ MemoryError while processing text with spaCy. Skipping this file.")
        return None, None, None
    except Exception as e:
        print("❌ Unexpected error during spaCy processing:")
        print(repr(e))
        return None, None, None

    # --- split into sumário / body ---
    try:
        sumario_dict, body_dict = split_text(doc)
    except ValueError as e:
        print("❌ Error encountered during dictionary slicing (split_text):")
        print(f"Reason: {e}")
        # We still return doc so caller can decide what to do
        return doc, None, None

    return doc, sumario_dict, body_dict


def process_pdf(pdf: Path) -> Dict[str, Any]:
    print("=== DEBUG: process_pdf CALLED FROM API ===", pdf)
    serie = is_serie(pdf.name)
    nlp = get_nlp(serie)

    # Extract text from PDF
    try:
        text = extract_pdf_to_markdown(pdf)
    except MemoryError:
        print(f"⚠ MemoryError while extracting text from PDF {pdf}. Skipping this file.")
        return make_error_result(
            "MemoryError while extracting text from PDF",
            stage="extract_pdf",
            code="memory_error",
            pdf=pdf,
            raw_text=None,
        )
    except Exception as e:
        print(f"❌ Error extracting text from PDF {pdf}:")
        print(repr(e))
        return make_error_result(
            f"Unexpected exception during PDF extraction: {repr(e)}",
            stage="extract_pdf",
            code="unexpected_exception",
            pdf=pdf,
            raw_text=None,
        )

    raw_text = text  # keep it for the final result

    # Optionally keep this; it only bypasses spaCy's length guard, not memory limits
    nlp.max_length = max(nlp.max_length, len(text) + 1)

    # Build dictionaries (spaCy + split_text)
    doc, sumario_dict, body_dict = build_dicts(nlp, text)

    # If we failed due to MemoryError or other critical issue, bail out cleanly
    if doc is None:
        print(f"⚠ Skipping PDF {pdf} due to processing error (doc is None).")
        return make_error_result(
            "spaCy processing failed (doc is None)",
            stage="nlp",
            code="doc_is_none",
            pdf=pdf,
            raw_text=raw_text,
        )

    # Handle III série
    if serie:
        if sumario_dict is None or body_dict is None:
            print(f"⚠ Skipping III série PDF {pdf}: missing sumário/body dict.")
            return make_error_result(
                "Missing sumário_dict or body_dict after split_text for III série",
                stage="split_text",
                code="missing_sumario_or_body",
                pdf=pdf,
                raw_text=raw_text,
                extra={"serie": "III"},
            )

        cleaned = clean_sumario(sumario_dict)
        blocks = sumario_to_blocks(cleaned)

        all_orgs = classBuilder_III(blocks, body_dict)
        docs_normalized = normalize_serie_iii_docs(all_orgs)

    # Handle other séries
    else:
        if sumario_dict is None or body_dict is None:
            print(f"⚠ Skipping non-III série PDF {pdf}: missing sumário/body dict.")
            return make_error_result(
                "Missing sumário_dict or body_dict after split_text for non-III série",
                stage="split_text",
                code="missing_sumario_or_body",
                pdf=pdf,
                raw_text=raw_text,
                extra={"serie": "OTHER"},
            )

        sumario_list, sumario_group = sumario_dic(sumario_dict)
        docs, all_orgs = classBuilder(body_dict, sumario_group)
        docs_normalized = normalize_other_docs(all_orgs)

    # displacy/render errors are ignored for the `error` field (only logged for you)
    try:
        #print(sumario_dict)
        #print("========================================"
        #      "===================================================")
        #print(body_dict)
        html = displacy.render(doc, style="ent", options=OPTIONS, page=True)
        out_path = pathlib.Path("entities.html")
        out_path.write_text(html, encoding="utf-8")
    except MemoryError:
        print("⚠ MemoryError while rendering displacy HTML. Skipping visualize step for this file.")
    except Exception as e:
        print("❌ Error while rendering / writing displacy HTML:")
        print(repr(e))

    # Success case
    return make_ok_result(raw_text=raw_text, docs=docs_normalized)


def main():
    pdf = Path(r"pdf_input\\ISerie-003-1997-01-15.pdf")
    result = process_pdf(pdf)
    print(result)


# Uncomment if you want to run it as a script
if __name__ == "__main__":
    main()
