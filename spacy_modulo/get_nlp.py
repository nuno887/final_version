import spacy
from .Entities import setup_entities
from .SerieIV.setupIV import setup_entitiesIV
from typing import Optional


def get_nlp(Serie: bool):
    exclude = ["ner"]
    nlp = spacy.load("pt_core_news_lg", exclude=exclude)
    if Serie:
        setup_entities(nlp)
    else:
        setup_entitiesIV(nlp)
        
    return nlp
