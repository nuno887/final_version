import spacy
from .Entities import setup_entities
from .SerieIV.setupIV import setup_entitiesIV
from typing import Optional


def get_nlp(Serie: Optional[int]):
    exclude = ["ner"]
    nlp = spacy.load("pt_core_news_lg", exclude=exclude)
    if Serie == 4:
        setup_entitiesIV(nlp)
    else:
        setup_entities(nlp, Serie)
    return nlp
