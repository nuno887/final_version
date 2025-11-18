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
from relation_extractor_02 import sumario_dic

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
    PDF = Path(r"pdf_input\\IISerie-005-2020-01-08Supl3.pdf")


    serie = is_serie(PDF.name)
    nlp = get_nlp(serie)
    text = extract_pdf_to_markdown(PDF)

    
    nlp.max_lengt = max(nlp.max_length, len(text) + 1)
    doc_1 =nlp(text)

    doc, sumario_dict, body_dict = build_dicts(nlp, text)

    print(f"Teste:", sumario_dict)
    print(f"======================================================================")
    print(f"body_dicts:", body_dict)

    #print(len(sumario_dic(doc_sumario)))

    html = displacy.render(doc, style = "ent", options= OPTIONS, page = True)
    out_path = pathlib.Path("entities.html")
    out_path.write_text(html, encoding = "utf-8")

  



main()