from __future__ import annotations

import pathlib
import argparse
import html as html_lib
from spacy import displacy
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from split_text import split_text
from pdf_markup import extract_pdf_to_markdown
from spacy_modulo import get_nlp, setup_entities, setup_entitiesIV
from relation_extractor_02 import sumario_dic, has_letters_ignoring_newlines, clean_sumario, sumario_to_blocks
from results import build_sumario_docs_from_grouped_blocks, classBuilder, classBuilder_III


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
        return True
    else:
        return False



def build_dicts(nlp, full_text: str):
    """
    Returns (doc, doc_sumario, doc_body, sumario_text, body_text)
    """
    sumario_dict = None
    body_dict = None
    doc = nlp(full_text)
    try:
        sumario_dict, body_dict = split_text(doc)

    except ValueError as e:
        print("❌ Error encountered during dictionary slicing:")
        print(f"Reason: {e}")
 
    return doc, sumario_dict, body_dict



def main():
    PDF = Path(r"pdf_input\\IIISerie-11-2020-06-18.pdf")


    serie = is_serie(PDF.name)
    nlp = get_nlp(serie)
    text = extract_pdf_to_markdown(PDF)
    nlp.max_length = max(nlp.max_length, len(text) + 1)
    if serie:
        doc, sumario_dict, body_dict = build_dicts(nlp, text)
        cleaned = clean_sumario(sumario_dict)
        blocks = sumario_to_blocks(cleaned)

        alldocs = classBuilder_III(blocks, body_dict)
        print(alldocs)

    
    else:
        doc, sumario_dict, body_dict = build_dicts(nlp, text)
        sumario_list , sumario_group= sumario_dic(sumario_dict)
        docs, all_orgs = classBuilder(body_dict, sumario_group)
        print(all_orgs)
 
    html = displacy.render(doc, style = "ent", options = OPTIONS, page = True)
    out_path = pathlib.Path("entities.html")
    out_path.write_text(html, encoding = "utf-8")

  
main()