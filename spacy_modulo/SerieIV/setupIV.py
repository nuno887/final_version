from __future__ import annotations

from spacy.pipeline import EntityRuler
import re, unicodedata
from spacy.language import Language
from spacy.util import filter_spans
from typing import Optional, List
from spacy.language import Language

from spacy.tokens import Doc, Span

import re



RULER_PATTERNS = [
    # For simple SpaCy rules
]


def _normalize_for_match(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))  # strip accents
    s = re.sub(r"\s+", "", s)  # drop ALL whitespace (handles "Tr a b a l h o")
    return s.casefold()

def _has_unicode_lower(line: str) -> bool:
    """True if s contains any Unicode lowercase letter (category 'Ll')."""
    return any(ch.isalpha() and unicodedata.category(ch) == "Ll" for ch in line)

def _eligible_allcaps_line(line: str) -> bool:
    """Line has letters and no lowercase letters (Unicode-aware)."""
    stripped = line.strip()
    return any(ch.isalpha() for ch in stripped) and not _has_unicode_lower(stripped)


@Language.component("allcaps_entity")
def allcaps_entity(doc: Doc) -> Doc:
    """
    Group consecutive ALL-CAPS lines into a single span.
    Label = ORG_WITH_STAR_LABEL if '*' occurs in the line, else ORG_LABEL.
    Blank lines inside a run are included; any non-blank ineligible line flushes the run.
    """
    text = doc.text
    spans: list[Span] = []

    lines = text.splitlines(keepends=True)
    pos = 0
    run_label: Optional[str] = None
    run_start: Optional[int] = None
    run_end: Optional[int] = None

    def flush_run():
        nonlocal run_label, run_start, run_end
        if run_label is not None and run_start is not None and run_end is not None and run_end > run_start:
            # Trim trailing newline if present
            end_idx = run_end - 1 if text[run_end - 1:run_end] == "\n" else run_end
            span = doc.char_span(run_start, end_idx, label=run_label, alignment_mode="contract")
            if span is not None:
                spans.append(span)
        run_label = run_start = run_end = None

    for ln in lines:
        line_end = pos + len(ln)
        content = ln[:-1] if ln.endswith("\n") else ln
        stripped = content.strip()

        if _eligible_allcaps_line(stripped):
            this_label = "ORG_WITH_STAR_LABEL" if "*" in stripped else "ORG_LABEL"
            leading_spaces = len(content) - len(content.lstrip())
            line_start_idx = pos + leading_spaces
            line_end_idx = line_end - (1 if ln.endswith("\n") else 0)

            if run_label is None:
                run_label, run_start, run_end = this_label, line_start_idx, line_end_idx
            elif this_label == run_label:
                run_end = line_end_idx
            else:
                flush_run()
                run_label, run_start, run_end = this_label, line_start_idx, line_end_idx
        else:
            if stripped == "":
               flush_run()
            else:
                flush_run()

        pos = line_end

    flush_run()

    if spans:
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc



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


# ======================sanitize ORG_LABEL (inicio) ========================================================

_NUM_DASH_NUM = re.compile(r"\b\d+\s*[-–—]\s*\d+\b")

@Language.factory("orglabel_symbol_sanitizer")
def create_orglabel_symbol_sanitizer(nlp, name):
    PARAGRAPH = nlp.vocab.strings.add("PARAGRAPH")

    def component(doc: Doc) -> Doc:
        new_ents = []
        for ent in doc.ents:
            if ent.label_ == "ORG_LABEL":
                txt = ent.text
                has_parens = ("(" in txt) or (")" in txt)
                has_numdashnum = bool(_NUM_DASH_NUM.search(txt))
                has_colon = ":" in txt
                has_slash = "/" in txt
                one_word = len([w for w in re.split(r"[^\w]+", ent.text) if any(ch.isalnum() for ch in w)]) <= 1

                if has_parens or has_numdashnum or has_colon or has_slash or one_word:
                    new_ents.append(Span(doc, ent.start, ent.end, label=PARAGRAPH))
                else:
                    new_ents.append(ent)
            else:
                new_ents.append(ent)
        doc.ents = tuple(new_ents)
        return doc

    return component
# ======================sanitize ORG_LABEL (fim)========================================================

# ===================== ASSINATURA (inicio)=================================================================
@Language.component("assinatura_detector")
def assinatura_detector(doc: Doc) -> Doc:
    """
    Detect lines like: ALL-CAPS BLOCK , mixed-case name
    → label entire line as 'Assinatura'
    """
    text = doc.text
    spans = []

    # process per line to catch signature lines cleanly
    pos = 0
    for ln in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(ln)
        pos = line_end

        content = ln.rstrip("\n")
        if not content.strip():
            continue
        if ":" in content:
            continue
        if content.count(",") > 1:
            continue

        # split on first comma
        if "," not in content:
            continue
        left, right = content.split(",", 1)

        left_stripped = left.strip()
        right_stripped = right.strip()

        if "-" in right_stripped:
            continue
        if '"' in left_stripped:
            continue

        if any(ch.isdigit() for ch in left_stripped):
            if not re.search(r"\.(?:º|ª)\b", left_stripped):
                continue
        if (left_stripped.count(".") > 2) or (right_stripped.count(".") > 2):
            continue
        if any(ch.isdigit() for ch in right_stripped):
            continue

        # left must have letters and NO lowercase (unicode-aware)
        if not any(ch.isalpha() for ch in left_stripped):
            continue
        if _has_unicode_lower(left_stripped):
            continue

        # right must contain at least one lowercase letter (name-like)
        if not _has_unicode_lower(right_stripped):
            continue

        name_words = [w for w in re.split(r"\s+", right_stripped) if any (ch.isalpha() for ch in w)]
        if len(name_words) < 2:
            continue

        # good: create span over full line (without trailing newline)
        s = line_start + (0)  # include any leading spaces; adjust if you prefer trim
        e = line_start + len(content)
        span = doc.char_span(s, e, label="ASSINATURA", alignment_mode="contract")
        if span is not None:
            spans.append(span)

    if spans:
        # merge with existing ents safely
        from spacy.util import filter_spans
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc
# ===================== ASSINATURA (fim)=================================================================

# =================== DOC_NAME_LABEL (inicio)===============================================================
@Language.component("docname_entity")
def docname_entity(doc: Doc) -> Doc:
    text = doc.text
    spans = []
    pos = 0
    for ln in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(ln)
        pos = line_end

        content = ln.rstrip("\n")
        if not content or "*" not in content:
            continue

        # span over the visible line (without trailing newline)
        s = line_start
        e = line_start + len(content)
        span = doc.char_span(s, e, label="DOC_NAME_LABEL", alignment_mode="contract")
        if span is not None:
            spans.append(span)

    if spans:
        from spacy.util import filter_spans
        doc.ents = filter_spans(list(doc.ents) + spans)
    return doc
# =================== DOC_NAME_LABEL (fim)===============================================================

# =================== PARAGRAPGH (inicio)=================================================================

@Language.component("paragraph_filler")
def paragraph_filler(doc: Doc) -> Doc:
    text = doc.text
    new_spans = []

    # quick overlap check
    def has_ent_between(s: int, e: int) -> bool:
        for ent in doc.ents:
            if not (e <= ent.start_char or s >= ent.end_char):
                return True
        return False

    pos = 0
    for ln in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(ln)
        pos = line_end

        content = ln.rstrip("\n")
        if not content.strip():
            continue  # skip blank lines

        s = line_start
        e = line_start + len(content)

        if not has_ent_between(s, e):
            span = doc.char_span(s, e, label="PARAGRAPH", alignment_mode="contract")
            if span is not None:
                new_spans.append(span)

    if new_spans:
        doc.ents = filter_spans(list(doc.ents) + new_spans)
    return doc

# =================== PARAGRAPH (fim)=================================================================

# =================== Merge PARAGRAPH (inicio)==========================================================

@Language.component("merge_paragraphs")
def merge_paragraphs(doc: Doc) -> Doc:
    ents = list(doc.ents)
    if not ents:
        return doc

    # ensure left-to-right order
    ents.sort(key=lambda e: (e.start_char, e.end_char))
    merged = []
    i = 0
    while i < len(ents):
        ent = ents[i]
        if ent.label_ != "PARAGRAPH":
            merged.append(ent)
            i += 1
            continue

        # start a run of PARAGRAPHs
        run_start = ent.start_char
        run_end = ent.end_char
        j = i + 1
        while j < len(ents) and ents[j].label_ == "PARAGRAPH":
            run_end = max(run_end, ents[j].end_char)
            j += 1

        span = doc.char_span(run_start, run_end, label="PARAGRAPH", alignment_mode="expand")
        if span is not None:
            merged.append(span)

        i = j

    doc.ents = tuple(filter_spans(merged))
    return doc
# =================== Merge PARAGRAPH (fim)==========================================================

# ======================== JUNK (inicio)================================================================

@Language.component("junk_line_detector")
def junk_line_detector(doc: Doc) -> Doc:
    text = doc.text
    junk_spans = []
    pos = 0

    for ln in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(ln)
        pos = line_end

        content = ln.rstrip("\n")
        # if the line has NO alphabetic characters at all → JUNK
        if content == "" or not any(ch.isalpha() for ch in content):
            s = line_start
            e = line_start + len(content)
            if e > s:
                sp = doc.char_span(s, e, label="JUNK_LABEL", alignment_mode="contract")
                if sp is not None:
                    junk_spans.append(sp)

    if not junk_spans:
        return doc

    # drop PARAGRAPH ents that overlap junk, keep others
    kept = []
    for ent in doc.ents:
        overlaps = any(not (ent.end_char <= js.start_char or ent.start_char >= js.end_char) for js in junk_spans)
        if ent.label_ == "PARAGRAPH" and overlaps:
            continue
        kept.append(ent)

    doc.ents = filter_spans(kept + junk_spans)
    return doc
# ======================== JUNK (fim)================================================================

# ================================ ORG/JUNK -> PARAGRAPH (inicio)============================================
@Language.component("orglabel_adjacent_paragraph_demoter")
def orglabel_adjacent_paragraph_demoter(doc: Doc) -> Doc:
    text = doc.text

    # build line index: [(start, end_wo_nl)]
    lines = []
    pos = 0
    for ln in text.splitlines(keepends=True):
        start = pos
        end_wo_nl = start + (len(ln) - (1 if ln.endswith("\n") else 0))
        pos += len(ln)
        lines.append((start, end_wo_nl))

    if not lines:
        return doc

    def line_index_for_char(ch: int) -> int:
        # linear scan is fine for typical page-sized docs
        for i, (s, e) in enumerate(lines):
            if s <= ch <= e:
                return i
        # if exactly at end of last newline, snap to last line
        return len(lines) - 1

    def line_has_paragraph(idx: int) -> bool:
        if idx < 0 or idx >= len(lines):
            return False
        s, e = lines[idx]
        for ent in doc.ents:
            if ent.label_ == "PARAGRAPH":
                if not (e <= ent.start_char or s >= ent.end_char):
                    return True
        return False

    new_ents = []
    for ent in doc.ents:
        if ent.label_ not in  ["ORG_LABEL", "JUNK_LABEL"]:
            new_ents.append(ent)
            continue

        idx = line_index_for_char(ent.start_char)
        above = line_has_paragraph(idx - 1)
        below = line_has_paragraph(idx + 1)

        if above or below:
            new_ents.append(Span(doc, ent.start, ent.end, label=doc.vocab.strings["PARAGRAPH"]))
        else:
            new_ents.append(ent)

    doc.ents = tuple(filter_spans(new_ents))
    return doc

# ================================ ORG/JUNK -> PARAGRAPH (fim)============================================
# ================================ connecting adjacent ORG_LABELS (inicio) ========================================

@Language.component("merge_plain_org_labels")
def merge_plain_org_labels(doc: Doc) -> Doc:
    ORG = "ORG_LABEL"

    ents = sorted(doc.ents, key=lambda e: (e.start_char, e.end_char))
    out = []
    i = 0
    while i < len(ents):
        ent = ents[i]
        # only merge plain ORG_LABEL; leave others (incl. ORG_WITH_STAR_LABEL) as-is
        if ent.label_ != ORG:
            out.append(ent)
            i += 1
            continue

        # start a run of ORG_LABELs
        run_start = ent.start_char
        run_end = ent.end_char
        j = i + 1
        while j < len(ents) and ents[j].label_ == ORG:
            gap = doc.text[run_end:ents[j].start_char]
            # merge only if gap is whitespace AND not a blank line
            #if gap.strip() != "" or "\n\n" in gap:
                #break
            run_end = max(run_end, ents[j].end_char)
            j += 1

        span = doc.char_span(run_start, run_end, label=ORG, alignment_mode="expand")
        if span is not None:
            out.append(span)
        i = j

    doc.ents = tuple(filter_spans(out))
    return doc
# ================================ connecting adjacent ORG_LABELS (fim) ========================================
# ================================= orglabel_prohibited_words_demoter (inicio) =================================

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace(".", "").casefold()

@Language.factory("orglabel_prohibited_words_demoter", default_config={"words": []})
def create_orglabel_prohibited_words_demoter(nlp, name, words):
    PARAGRAPH = nlp.vocab.strings.add("PARAGRAPH")
    prohibited = {_norm(w) for w in (words or [])}

    # split into word-like parts; keep dotted abbreviations (e.g., S.A., S.G.P.S.)
    splitter = re.compile(r"[^\w\.]+", flags=re.UNICODE)

    def component(doc: Doc) -> Doc:
        new_ents = []
        for ent in doc.ents:
            if ent.label_ != "ORG_LABEL":
                new_ents.append(ent)
                continue

            parts = [p for p in splitter.split(ent.text) if p]
            parts_norm = {_norm(p) for p in parts}

            if prohibited & parts_norm:
                new_ents.append(Span(doc, ent.start, ent.end, label=PARAGRAPH))
            else:
                new_ents.append(ent)

        doc.ents = tuple(new_ents)
        return doc

    return component
# ================================= orglabel_prohibited_words_demoter (fim) =================================

def setup_entitiesIV(nlp):

   # ruler = nlp.add_pipe("entity_ruler", first = True)
   # ruler.add_patterns(RULER_PATTERNS)
    nlp.add_pipe("sumario_detector")
    nlp.add_pipe("allcaps_entity")
    nlp.add_pipe("orglabel_symbol_sanitizer", after = "allcaps_entity")
    nlp.add_pipe("assinatura_detector", after="orglabel_symbol_sanitizer")
    nlp.add_pipe("docname_entity", after="assinatura_detector")
    nlp.add_pipe("junk_line_detector", after="docname_entity")
    nlp.add_pipe("paragraph_filler", after="junk_line_detector")
    nlp.add_pipe("merge_paragraphs", after="paragraph_filler")
    nlp.add_pipe("orglabel_adjacent_paragraph_demoter", after="merge_paragraphs")
    nlp.add_pipe("merge_plain_org_labels", after="orglabel_adjacent_paragraph_demoter")
    nlp.add_pipe(
    "orglabel_prohibited_words_demoter",
    after="merge_plain_org_labels",
    config={"words": [
        "ASSINATURA", 
        "ANEXO", 
        "MODELO", 
        "ALTERACOES", 
        "CONTRATO", 
        "MUDANCA", 
        "FORA", 
        "QUOTAS", 
        "DISSOLUCAO", 
        "ENCERRAMENTO", 
        "LIQUIDACAO",
        "CESSACAO",
        "CONSTITUICAO",
        "DESIGNACAO"
        ]}
)


        