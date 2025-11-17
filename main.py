from __future__ import annotations

import pathlib
import argparse
import html as html_lib
from spacy import displacy
from split_text import split_sumario_and_body
from relation_extractor import RelationExtractor, RelationExtractorSerieIII, export_relations_items_minimal_json, export_serieIII_items_minimal_json
from pdf_markup import extract_pdf_to_markdown
from spacy_modulo import get_nlp, setup_entities, setup_entitiesIV
from body_extraction import divide_body_by_org_and_docs, divide_body_by_org_and_docs_serieIII, split_doc_by_assinatura
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

OPTIONS = {"colors": {
    "Sumario": "#ffd166",
    "ORG_LABEL": "#6e77b8",
    "ORG_WITH_STAR_LABEL": "#6fffff",
    "DOC_NAME_LABEL": "#b23bbd",
    "DOC_TEXT": "#47965e",
    "PARAGRAPH": "#14b840",
    "JUNK_LABEL": "#e11111",
    "SERIE_III": "#D1B1B1",
    "ASSINATURA": "#d894df"
}}

def is_serie(filename: str) -> Optional[int]:

    if "iiiserie" in filename.lower():
        return 3
    if "iiserie" in filename.lower():
        return 2
    if "iserie" in filename.lower():
        return 1
    if "ivserie" in filename.lower():
        return 4
    return None


def build_docs(nlp, full_text: str):
    """
    Returns (doc, doc_sumario, doc_body, sumario_text, body_text, meta)
    """
    doc = nlp(full_text)
    sumario_text, body_text, meta = split_sumario_and_body(doc, None)
    doc_sumario = nlp(sumario_text)
    doc_body = nlp(body_text)
    return doc, doc_sumario, doc_body, sumario_text, body_text, meta


def extract_relations_and_payload(doc_sumario, serie_iii: int):
    if serie_iii == 3:
        rex = RelationExtractorSerieIII(debug=True)
        rels = rex.extract(doc_sumario)
        payload = export_serieIII_items_minimal_json(rels)
    else:
        rex = RelationExtractor(debug=True)
        rels = rex.extract(doc_sumario)
        payload = export_relations_items_minimal_json(rels, path=None)
    return rels, payload


def split_body(doc_body, payload, serie: int):
    if serie == 3:
        print("divide_body_by_org_and_docs_serieIII")
        # IMPORTANT: pass the same pipeline used to build doc_body
        results, summary = divide_body_by_org_and_docs_serieIII(
            doc_body,
            payload,

        )
        return results, summary
    if serie == 4:
        print(f"split_doc_by_assinatura")
        results = split_doc_by_assinatura(doc_body)
        summary = None
        return results, summary
    if serie in [1, 2]:
        # Keep your Serie I/II path as-is if you still use it elsewhere
        print("divide_body_by_org_and_docs")

        results, summary = divide_body_by_org_and_docs(
            doc_body,
            payload,
            write_org_files=False,
            write_doc_files=False,
        )
        return results, summary
    else:
        print("You should not be here")

def main():
    PDF = Path(r"pdf_input\\IIISerie-08-2020-05-08.pdf")

    serie = is_serie(PDF.name)
    nlp = get_nlp(serie)
    text = extract_pdf_to_markdown(PDF)
    nlp.max_lengt = max(nlp.max_length, len(text) + 1)
    doc, doc_sumario, doc_body, sumario_text, body_text, _meta = build_docs(nlp, text)
    rels, payload = extract_relations_and_payload(doc_sumario, serie)
    results, summary = split_body(doc_body, payload, serie)
