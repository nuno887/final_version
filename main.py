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

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import json