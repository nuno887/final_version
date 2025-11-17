from spacy.pipeline import EntityRuler
import re, unicodedata
from spacy.language import Language
from spacy.util import filter_spans
from .DocText import *
from .Paragraphs import *
from typing import Optional
from spacy.tokens import Doc, Span



OPTIONS = {"colors": {
    "Sumario": "#ffd166",
    "ORG_LABEL": "#6e77b8",
    "ORG_WITH_STAR_LABEL": "#6fffff",
    "DOC_NAME_LABEL": "#b23bbd",
    "DOC_TEXT": "#47965e",
    "PARAGRAPH": "#14b840",
    "JUNK_LABEL": "#e11111",
    "SERIE_III": "#D1B1B1"
    }}


RULER_PATTERNS = [

{"label": "Sumario", "pattern": "###**Sumário**"},
{"label": "Sumario", "pattern": "###**Sumario**"},
{"label": "Sumario",
 "pattern": [
   {"TEXT": {"IN": ["Sumário", "Sumario"]}},
   {"ORTH": ":", "OP": "!"}
 ]},
 {"label": "JUNK_LABEL", "pattern": "## **Suplemento**"},

{"label": "SERIE_III", "pattern": "**Regulamentação do Trabalho**"},
{"label": "SERIE_III", "pattern": "** Direção Regional do Trabalho e da Ação Inspetiva**"},

{"label": "SERIE_III", "pattern": "Direção Regional do Trabalho"},
{"label": "SERIE_III", "pattern": "Direcção Regional do Trabalho"},

{"label": "DOC_NAME_LABEL", "pattern": "Convenções Coletivas de Trabalho:"},
{"label": "DOC_NAME_LABEL", "pattern": "Portarias de Extensão:"},
{"label": "DOC_NAME_LABEL", "pattern": "Despachos:"},
{"label": "DOC_NAME_LABEL", "pattern": "Portarias de Condições de Trabalho:"},
{"label": "DOC_NAME_LABEL", "pattern": "Eleição de Representantes:"},
{"label": "DOC_NAME_LABEL", "pattern": "Avisos de Cessação da Vigência de Convenções Colectivas de Trabalho:"},
{"label": "DOC_NAME_LABEL", "pattern": "Direção:"},
{"label": "DOC_NAME_LABEL", "pattern": "Convocatórias:"},
{"label": "DOC_NAME_LABEL", "pattern": "Eleições:"},
{"label": "DOC_NAME_LABEL", "pattern": "Estatutos:"},
{"label": "DOC_NAME_LABEL", "pattern": "Corpos Gerentes / Alterações:"},
{"label": "DOC_NAME_LABEL", "pattern": "Corpos Gerentes/Alterações:"},
{"label": "DOC_NAME_LABEL", "pattern": "Corpos Gerentes:"},
{"label": "DOC_NAME_LABEL", "pattern": "Alterações:"},
{"label": "DOC_NAME_LABEL", "pattern": "Associações Sindicais/Corpos Gerentes:"},
{"label": "DOC_NAME_LABEL", "pattern": "Associações de Empregadores/Direcção:"},
{"label": "DOC_NAME_LABEL", "pattern": "Associações de Empregadores/Direção:"},

]

KNOWN_DOC_NAMES = [
    "Regulamentação do Trabalho",
    "Portarias de Extensão:",
    "Convenções Colectivas de Trabalho:",
    "Despachos:",
    "Regulamentos de Condições Mínimas:",
    "Estatutos/Alterações:",
]

def _normalize_for_match(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))  # strip accents
    s = re.sub(r"\s+", "", s)  # drop ALL whitespace (handles "Tr a b a l h o")
    return s.casefold()

KNOWN_DOC_NAMES_NORM = { _normalize_for_match(x) for x in KNOWN_DOC_NAMES }

_pattern_allcaps = re.compile(r'[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ0-9 ,.\'&\-\n]{5,}')
_junk_rx = re.compile(r"^[\d\s\-\–—\.\,;:·•*'\"`´\+\=\(\)\[\]\{\}/\\<>~^_|]{1,20}$")

def _is_junk_line(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    if '|' in s:          
        return False
    if any(ch.isalpha() for ch in s):
        return False
    return bool(_junk_rx.match(s))



def _docname_line_is_eligible(line: str) -> bool:
    s = line.strip()
    return (
        s != ""
        and "*" in s
        and any(ch.isalpha() for ch in s)     # has letters
        and any(ch.isalpha() and ch.islower() for ch in s)  # has lowercase
    )


def _line_has_lowercase(line: str) -> bool:
    # count only characters in the Unicode "Ll" (Letter, lowercase) category
    return any(ch.isalpha() and unicodedata.category(ch) == 'Ll' for ch in line)

def _eligible_line(line: str) -> bool:
    # non-empty, contains letters, at least two words, and NO lowercase letters
    stripped = line.strip()
    return (
        any(ch.isalpha() for ch in stripped)
        and not _line_has_lowercase(line)
    )


@Language.component("strip_junk_ents")
def strip_junk_ents(doc):
    doc.ents = tuple(e for e in doc.ents if e.label_ != "JUNK_LABEL")
    return doc

# --- REPLACE your allcaps_entity component with this ---
@Language.component("allcaps_entity")
def allcaps_entity(doc):
    text = doc.text
    spans = []

    lines = text.splitlines(keepends=True)
    pos = 0

    # Current run state
    run_label = None         # ORG_LABEL / ORG_WITH_STAR_LABEL / None
    run_start = None         # char start of current run (first non-space)
    run_end = None           # char end (exclusive), trimmed of trailing \n

    def flush_run():
        nonlocal run_label, run_start, run_end
        if run_label is not None and run_start is not None and run_end is not None and run_end > run_start:
            # Trim trailing newline if present
            end_idx = run_end - 1 if text[run_end - 1:run_end] == "\n" else run_end
            span = doc.char_span(run_start, end_idx, label=run_label, alignment_mode="contract")
            if span is not None:
                spans.append(span)
        run_label = None
        run_start = None
        run_end = None

    for ln in lines:
        line_end = pos + len(ln)
        content = ln[:-1] if ln.endswith("\n") else ln
        stripped = content.strip()

        if _eligible_line(stripped):
            # Determine this line's type
            this_label = "ORG_WITH_STAR_LABEL" if "*" in stripped else "ORG_LABEL"

            # Compute start index at first non-space on this line
            leading_spaces = len(content) - len(content.lstrip())
            line_start_idx = pos + leading_spaces
            line_end_idx = line_end - (1 if ln.endswith("\n") else 0)

            if run_label is None:
                # start a new run
                run_label = this_label
                run_start = line_start_idx
                run_end = line_end_idx
            elif this_label == run_label:
                # extend current run
                run_end = line_end_idx
            else:
                # label changed → flush previous, start new
                flush_run()
                run_label = this_label
                run_start = line_start_idx
                run_end = line_end_idx
        else:
            # not eligible
            # If the line is blank/whitespace-only, keep the current run open
            # so headings separated by empty lines are merged.
            if stripped == "":
                if run_label is not None:
                    # extend the run to include this newline/whitespace
                    run_end = line_end
            else:
                # real content that breaks the run → flush
                flush_run()

        pos = line_end

    # close final run
    flush_run()

    if spans:
        from spacy.util import filter_spans
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc





def _iter_bold_pairs_no_merge_III(text: str):
    """
    Yield primitive bold pairs without merging across whitespace.
    Returns (outer_start, inner_start, inner_end, outer_end) for each **...**.
    """
    n = len(text)
    i = 0
    while i < n:
        open_idx = text.find("**", i)
        if open_idx == -1:
            break
        inner_start = open_idx + 2
        close_idx = text.find("**", inner_start)
        if close_idx == -1:
            break
        yield open_idx, inner_start, close_idx, close_idx + 2
        i = close_idx + 2

STOP_PUNCT = set(".:;?!…")  # add more here later

def _ends_with_stop(inner: str, stops: set[str] = STOP_PUNCT) -> bool:
    i = len(inner) - 1
    while i >= 0 and inner[i].isspace():
        i -= 1
    return i >= 0 and inner[i] in stops


@Language.component("docname_entity_III")
def docname_entity(doc):
    text = doc.text

    # Collect SERIE_III spans from existing ents (EntityRuler ran first)
    serie3_spans = [(e.start_char, e.end_char) for e in doc.ents if e.label_ == "SERIE_III"]

    def overlaps_serie3(s, e):
        for a, b in serie3_spans:
            if not (e <= a or s >= b):
                return True
        return False

    def serie3_in_gap(left_e, right_s):
        for a, b in serie3_spans:
            if a < right_s and b > left_e:
                return True
        return False

    # Known SERIE_III titles (normalized)
    KNOWN_SERIE3_TITLES = [
        "Direção Regional do Trabalho",
        "Direcção Regional do Trabalho",
        "Regulamentação do Trabalho",
    ]
    KNOWN_SERIE3_TITLES_NORM = {_normalize_for_match(x) for x in KNOWN_SERIE3_TITLES}

    # 1) Collect primitive bold pairs that look like doc names
    prim = []
    for os, is_, ie, oe in _iter_bold_pairs_no_merge_III(text):
        inner = text[is_:ie]
        inner_norm = _normalize_for_match(inner)

        # skip if overlaps SERIE_III or is a known SERIE_III heading
        if overlaps_serie3(os, oe):
            continue
        if inner_norm in KNOWN_SERIE3_TITLES_NORM:
            continue

        looks_like_docname = (
            inner_norm in KNOWN_DOC_NAMES_NORM
            or any(ch.isalpha() and ch.islower() for ch in inner)
        )
        if looks_like_docname:
            # keep full (OUTER) bounds so ** are included
            prim.append((os, is_, ie, oe))

    if not prim:
        return doc

    prim.sort(key=lambda t: t[0])  # by outer_start

    # 2) Merge adjacent primitives when only whitespace is between,
    #    but stop on colon or trailing dot, and never cross SERIE_III.
    merged = []
    cur_os, cur_is, cur_ie, cur_oe = prim[0]
    for os, is_, ie, oe in prim[1:]:
        between = text[cur_oe:os]
        left_inner = text[cur_is:cur_ie]

        hard_stop = left_inner.rstrip().endswith(":") or _ends_with_stop(left_inner)

        if (between.strip() == "") and (not hard_stop) and (not serie3_in_gap(cur_oe, os)):
            # extend current group to include the next segment
            cur_oe = oe
            cur_ie = ie
        else:
            # store OUTER bounds so ** markers are part of the entity
            merged.append((cur_os, cur_oe))
            cur_os, cur_is, cur_ie, cur_oe = os, is_, ie, oe
    merged.append((cur_os, cur_oe))

    # 3) Create spans using OUTER bounds to include the ** markers
    spans = []
    for s, e in merged:
        if s < e:
            span = doc.char_span(s, e, label="DOC_NAME_LABEL", alignment_mode="expand")
            if span is not None:
                spans.append(span)

    if spans:
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc

# ===================================================
BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")

@Language.component("docname_entity")
def docname_entity(doc):
    text = doc.text
    spans = []

    for m in BOLD_PATTERN.finditer(text):
        outer_start, outer_end = m.span()
        inner_start = outer_start + 2
        inner_end = outer_end - 2

        # find the full line containing this bold block
        line_start = text.rfind("\n", 0, outer_start)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1  # move past the newline

        line_end = text.find("\n", outer_end)
        if line_end == -1:
            line_end = len(text)

        line = text[line_start:line_end]
        line_stripped = line.strip()

        # 1) If there's any non-space text before the ** on this line, skip.
        before_bold = line[: outer_start - line_start]
        if before_bold.strip():
            # e.g. "- Secretária ... **", so NOT a doc name
            continue

        # 2) Keep the "exactly one bold pair on the line" rule if you want:
        if line.count("**") != 2:
            continue

        # 3) (Optional) keep your semantic check if you still want it:
        # inner = text[inner_start:inner_end]
        # if (
        #     _normalize_for_match(inner) not in KNOWN_DOC_NAMES_NORM
        #     and not any(ch.isalpha() and ch.islower() for ch in inner)
        # ):
        #     continue

        span = doc.char_span(
            outer_start,
            outer_end,
            label="DOC_NAME_LABEL",
            alignment_mode="contract",
        )
        if span is not None:
            spans.append(span)

    if spans:
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc

# ===================================================



_BOLD_PAIR_RE = re.compile(r"\*\*.+?\*\*", re.DOTALL)

def _overlaps(a_s, a_e, b_s, b_e):
    return (a_s < b_e) and (b_s < a_e)

@Language.component("paragraph_to_org_star")
def paragraph_to_org_star(doc):
    text = doc.text
    new_spans = []

    for e in doc.ents:
        if e.label_ != "PARAGRAPH":
            continue

        segment = text[e.start_char:e.end_char]

        # 🔸 Skip paragraphs that have any lowercase (Unicode-aware)
        # This ensures we only process ALL-CAPS paragraphs.
        if any(ch.islower() for ch in segment):
            continue

        # Find all **…** pairs inside this ALL-CAPS paragraph
        for m in _BOLD_PAIR_RE.finditer(segment):
            inner = segment[m.start()+2 : m.end()-2]
            if _eligible_line(inner):
                os = e.start_char + m.start()
                oe = e.start_char + m.end()
                span = doc.char_span(os, oe, label="ORG_WITH_STAR_LABEL", alignment_mode="expand")
                if span is not None:
                    new_spans.append(span)

    if not new_spans:
        return doc

    kept = []
    for e in doc.ents:
        if e.label_ != "PARAGRAPH":
            kept.append(e)
            continue
        if any(_overlaps(e.start_char, e.end_char, s.start_char, s.end_char) for s in new_spans):
            continue
        kept.append(e)

    doc.ents = filter_spans(kept + new_spans)
    return doc



# Words that suggest the first bold block is a header/topline (normalize & casefold before comparing)
_ORG_HEADER_HINTS = {
    "funchal",
    "conservatoria",
    "registo",
    "comercial",
    "madeira",
    "portugal",
    "camara",
    "municipal",
    "servico",
    "servicos",
    "direcao",
    "direccao",
    "direcção",
    "direção",
    "regional",
    "nacional",
    "ministerio",
    "ministério",
    "governo",
}
# Characters that must NOT appear in the first bold block if we are to split
_DISALLOWED_IN_FIRST = {"-", "%", "&"}

def _contains_any_keyword(s: str, keywords: set[str]) -> bool:
    sn = _normalize_for_match(s)  # strip accents, collapse spaces, casefold
    # because _normalize_for_match removes spaces, we do a simple containment test per keyword
    # keywords in this set are simple words; we check any of them appear
    for kw in keywords:
        if kw in sn:
            return True
    return False

@Language.component("split_org_with_star")
def split_org_with_star(doc):
    text = doc.text
    keep = []
    add_spans = []

    for e in doc.ents:
        if e.label_ != "ORG_WITH_STAR_LABEL":
            keep.append(e)
            continue

        segment = text[e.start_char:e.end_char]

        # Find **...** pairs inside this span
        bold_matches = list(_BOLD_PAIR_RE.finditer(segment))
        if len(bold_matches) < 2:
            # nothing to split
            keep.append(e)
            continue

        # Inspect the FIRST bold block
        first_m = bold_matches[0]
        first_inner = segment[first_m.start()+2:first_m.end()-2]

        # Rule: first must NOT contain any of the disallowed chars, and MUST contain a hint word
        if (any(ch in _DISALLOWED_IN_FIRST for ch in first_inner)
            or not _contains_any_keyword(first_inner, _ORG_HEADER_HINTS)):
            # do not split; keep original
            keep.append(e)
            continue

        # Split: create one ORG_WITH_STAR_LABEL per bold block (keeping the ** in the span)
        for m in bold_matches:
            os = e.start_char + m.start()       # outer start (**)
            oe = e.start_char + m.end()         # outer end (after **)
            span = doc.char_span(os, oe, label="ORG_WITH_STAR_LABEL", alignment_mode="expand")
            if span is not None:
                add_spans.append(span)
        # Do NOT keep the original combined span (we replaced it)

    if add_spans:
        doc.ents = filter_spans(keep + add_spans)
    else:
        doc.ents = tuple(keep)
    return doc

# ===================================================================================
# resolve the problem in ISerie-051-2010-06-25


@Language.factory("orglabel_to_paragraph_sanitizer")
def create_orglabel_to_paragraph_sanitizer(nlp, name):
    patt = re.compile(r"[;]|\d")  # dot, comma, hyphen, or any digit
    PARAGRAPH = nlp.vocab.strings.add("PARAGRAPH")  # ensure label exists

    def component(doc):
        new_ents = []
        for ent in doc.ents:
            # compare by string label to avoid StringStore lookups
            if ent.label_ == "ORG_LABEL" and patt.search(ent.text):
                new_ents.append(Span(doc, ent.start, ent.end, label=PARAGRAPH))
            else:
                new_ents.append(ent)
        doc.ents = tuple(new_ents)
        return doc

    return component




# ===================================================================================

# ===================================================================================
#resolves the probem in ISerie-031-2020-02-19sup.pdf (Sumario)


@Language.factory("concat_doc_name_label")
def create_concat_doc_name_label(nlp, name):
    DOC_NAME = nlp.vocab.strings.add("DOC_NAME_LABEL")

    def component(doc):
        if not doc.ents:
            return doc

        ents = list(doc.ents)          # sorted by start
        new_ents = []
        i, n = 0, len(ents)

        while i < n:
            ent = ents[i]
            if ent.label == DOC_NAME:
                start = ent.start
                end = ent.end
                j = i + 1

                # Merge ONLY if there's *only whitespace* between spans
                while (
                    j < n
                    and ents[j].label == DOC_NAME
                    and doc[end:ents[j].start].text.strip() == ""  # <-- key guard
                ):
                    end = ents[j].end
                    j += 1

                new_ents.append(Span(doc, start, end, label=DOC_NAME))
                i = j
            else:
                new_ents.append(ent)
                i += 1

        doc.ents = tuple(new_ents)
        return doc

    return component

# ===================================================================================
@Language.factory("concat_ORG_WITH_STAR_label")
def create_concat_doc_name_label(nlp, name):
    ORG_NAME = nlp.vocab.strings.add("ORG_WITH_STAR_LABEL")

    def component(doc):
        if not doc.ents:
            return doc

        ents = list(doc.ents)          # sorted by start
        new_ents = []
        i, n = 0, len(ents)

        while i < n:
            ent = ents[i]
            if ent.label == ORG_NAME:
                start = ent.start
                end = ent.end
                j = i + 1

                # Merge ONLY if there's *only whitespace* between spans
                while (
                    j < n
                    and ents[j].label == ORG_NAME
                    and doc[end:ents[j].start].text.strip() == ""  # <-- key guard
                ):
                    end = ents[j].end
                    j += 1

                new_ents.append(Span(doc, start, end, label=ORG_NAME))
                i = j
            else:
                new_ents.append(ent)
                i += 1

        doc.ents = tuple(new_ents)
        return doc

    return component

# ====================== Sumario (inicio)=================================================================
# 1) Markdown heading form: one or more '#' tokens, optional **/***, then Sumário/Sumario (optionally repeated once), nothing else
_SUMARIO_HEADING_RE = re.compile(
    r"""
    ^\s*
    (?:[#]{1,4}\s+)+              # one or more heading tokens
    (?:\*\*\s*)?                  # optional opening **
    \**\s*                        # tolerate stray *
    (sumario|sumário)
    \s*\**\s*                     # tolerate stray *
    (?:\*\*\s*)?                  # optional closing **
    (?:\s+(sumario|sumário))?     # optional second word
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)



@Language.component("sumario_detector")
def sumario_detector(doc: Doc) -> Doc:
    text = doc.text
    spans = []
    pos = 0
    for ln in text.splitlines(keepends=True):
        line_start = pos
        pos += len(ln)
        content = ln.rstrip("\n")

        if not content.strip():
            continue

        if _SUMARIO_HEADING_RE.match(content):
            s = line_start
            e = line_start + len(content)      # span = the visible line only
            sp = doc.char_span(s, e, label="Sumario", alignment_mode="contract")
            if sp is not None:
                spans.append(sp)

    if spans:
        from spacy.util import filter_spans
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc

# ====================== Sumario (fim) =================================================================

def setup_entities(nlp, Serie: Optional[int]):

    ruler = nlp.add_pipe("entity_ruler", first = True)
    ruler.add_patterns(RULER_PATTERNS)
    nlp.add_pipe("sumario_detector")
    nlp.add_pipe("allcaps_entity")

    if Serie == 3:
        nlp.add_pipe("docname_entity_III")
    else:
        nlp.add_pipe("docname_entity")
        nlp.add_pipe("concat_doc_name_label")
 
    nlp.add_pipe("doc_text_entity")

    nlp.add_pipe("paragraph_entity")
    nlp.add_pipe("paragraph_to_org_star")
    nlp.add_pipe("split_org_with_star")
    nlp.add_pipe("orglabel_to_paragraph_sanitizer")
    nlp.add_pipe("concat_ORG_WITH_STAR_label")

  

 