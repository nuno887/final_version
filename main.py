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
from results import build_sumario_docs_from_grouped_blocks, classBuilder

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
        return 4
    if "iserie" in filename.lower():
        return 4
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
    PDF = Path(r"pdf_input\\ISerie-028-2020-02-14sup2.pdf")


    serie = is_serie(PDF.name)
    nlp = get_nlp(serie)
    text = extract_pdf_to_markdown(PDF)
    
    nlp.max_lengt = max(nlp.max_length, len(text) + 1)

    doc, sumario_dict, body_dict = build_dicts(nlp, text)

    sumario_list , sumario_group= sumario_dic(sumario_dict)

    docs = classBuilder(body_dict, sumario_group)


    #print(f"sumario_list:", sumario_list)
    #print(f"sumario_list:", len(sumario_list))
    #print(f"==========================================================================")
    #print(f"sumario_group:", sumario_group)
    #print("========================================================================")
    #print(f"Body:", body_dict)
    #print(f"Teste:", sumario_dict)
    #print(f"======================================================================")
    #print(f"body_dicts:", body_dict)

    #print(len(sumario_dic(doc_sumario)))

    html = displacy.render(doc, style = "ent", options = OPTIONS, page = True)
    out_path = pathlib.Path("entities.html")
    out_path.write_text(html, encoding = "utf-8")

  
main()