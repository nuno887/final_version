from typing import Dict, List, Optional, TypedDict
from .helper import _normalize_for_match_letters_only, _is_close_match, _norm_for_match


class Entity(TypedDict):
    text: str
    label: str

Grouped = Dict[int, Entity]  # your `grouped` block
GroupedBlock = Dict[str, List[str]]  # your `GroupedBlock` for that block
AllGroupedBlocks = Dict[int, GroupedBlock]  # block_idx → GroupedBlock


class SumarioDoc:
    """
    Represents ONE candidate document inside a block.
    Holds both:
      - the groupedBlock slice (header/org/doc_name texts)
      - the entities from `grouped` that belong to this doc.
    """
    def __init__(
        self,
        idx: int,                       # just an internal index (0,1,2...)
        header_texts: List[str],        # ORG_WITH_STAR_LABEL 
        org_texts: List[str],           # ORG_LABEL
        doc_name: List[str],            # DOC_NAME_LABEL
        doc_paragraph: List[str],       # PARAGRAPH

    ) -> None:
        self.idx = idx
        self.header_texts = header_texts
        self.org_texts = org_texts
        self.doc_name = doc_name
        self.doc_paragraph = doc_paragraph

        # will be filled later using `grouped`
        self.entities: Grouped = {}     # pos -> {text, label}
        self.paragraphs: List[str] = []          # para apagar???
        self.signature: Optional[str] = None     # para apagar???

        self.header_start: Optional[int] = None

        self.next_header_texts: List[str] | None = None

        # Optional
        self.doc_end: Optional[int] = None   # exclusive
        self.org_positions: List[int] = [] # positions of ORG_LABEL inside self.entities
        self.doc_name_positions: List[int] = [] # positions of DOC_NAME_LABEL inside self. entities
        

    def attach_from_grouped_slice(self, grouped: Grouped, start: int, end: int) -> None:

        """
        Fill this SumarioDoc from a slice of 'grouped' between start and end (inclusive),
        preserving the original positional order for ALL labels
        """

        # 1) Get positions in order within [start, end), end is exclusive
        positions_in_slice = sorted(
            pos for pos in grouped.keys()
            if start <= pos < end
        )
        # 2) Store entities in taht order
        # (dicts preserve insertion order in modern Python,  but we insert in sorted order explicitly)
        self.entities = {}
        for pos in positions_in_slice:
            self.entities[pos] = grouped[pos]
        
        # 3) Derive paragraphs and signatures also in positional order
        self.paragraphs = []
        signatures: List[str] = []

        for pos in positions_in_slice:
            ent = grouped[pos]
            label = ent["label"]
            text = ent["text"]

            if label == "PARAGRAPH":
                self.paragraphs.append(text)
            elif label == "ASSINATURA":
                signatures.append(text)
        
        self.signature = signatures[-1] if signatures else None
    
    def align_orgs_and_doc_names_from_entities(self) -> None:
        self.org_positions = []
        self.doc_name_positions = []

        if not self.entities:
            return

        ORG_LABELS_FOR_MATCH = {"ORG_LABEL", "ORG_WITH_STAR_LABEL"}

        org_candidates = [
            (pos, ent["text"])
            for pos, ent in self.entities.items()
            if ent["label"] in ORG_LABELS_FOR_MATCH
        ]

        doc_name_candidates = [
            (pos, ent["text"])
            for pos, ent in self.entities.items()
            if ent["label"] == "DOC_NAME_LABEL"
        ]

        used_org_positions: set[int] = set()
        for expected in self.org_texts:
            match_pos = None
            for pos, text in org_candidates:
                if pos in used_org_positions:
                    continue
                if _is_close_match(expected, text):
                    match_pos = pos
                    used_org_positions.add(pos)
                    break
            if match_pos is not None:
                self.org_positions.append(match_pos)

        used_doc_positions: set[int] = set()
        for expected in self.doc_name:
            match_pos = None
            for pos, text in doc_name_candidates:
                if pos in used_doc_positions:
                    continue
                if _is_close_match(expected, text):
                    match_pos = pos
                    used_doc_positions.add(pos)
                    break
            if match_pos is not None:
                self.doc_name_positions.append(match_pos)

    
    
    def __repr__(self) -> str:
        return (
            f"SumarioDoc(idx={self.idx}, "
            f"header_texts={self.header_texts}, "
            f"org_texts={self.org_texts}, "
            f"doc_name={self.doc_name}, "
            f"doc_paragraph={self.doc_paragraph}, "
            f"header_start={self.header_start}, "
            f"next_header_texts={self.next_header_texts}, "
            f"entities={self.entities}, "
            f"org_positions={self.org_positions}, "
            f"doc_name_positions={self.doc_name_positions}, )"
        )


# ==============================================================================================================================================

def build_sumario_docs_from_grouped_blocks(
    grouped_blocks: AllGroupedBlocks,
) -> List[SumarioDoc]:
    """
    Create ONE SumarioDoc per id in grouped_blocks.

    - grouped_blocks:
        {
          0: {"ORG_WITH_STAR_LABEL": [...], "ORG_LABEL": [...], "DOC_NAME_LABEL": [...], "PARAGRAPH": [...]},
          1: {...},
          ...
        }
    """
    docs: List[SumarioDoc] = []

    for idx, block in grouped_blocks.items():
        header_texts = block.get("ORG_WITH_STAR_LABEL", [])
        org_texts = block.get("ORG_LABEL", [])
        doc_names = block.get("DOC_NAME_LABEL", [])
        paragraphs = block.get("PARAGRAPH", [])

        doc = SumarioDoc(
            idx=idx,
            header_texts=header_texts[:],   
            org_texts=org_texts[:],
            doc_name=doc_names[:],
            doc_paragraph=paragraphs[:],
        )
        docs.append(doc)

    # Fill next_header_texts based on order
    for i in range(len(docs) - 1):
        docs[i].next_header_texts = docs[i + 1].header_texts[:]

    return docs


def _find_header_run_start(
    grouped: Grouped,
    header_texts: List[str],
) -> Optional[int]:
    """
    Find the start position in `grouped` where a contiguous run of
    ORG_WITH_STAR_LABEL lines matches the given header_texts (as a whole).
    Returns the first position of that run, or None if not found.
    """

    if not header_texts:

        return None

    target_raw = " ".join(header_texts)
    target_norm = _normalize_for_match_letters_only(target_raw)


    if not target_norm or not grouped:
        print("[DEBUG] no target_norm or empty grouped → return None")
        return None

    positions = sorted(grouped.keys())
    n = len(positions)
    i = 0

    while i < n:
        pos = positions[i]
        ent = grouped[pos]
        label = ent["label"]

        if label != "ORG_WITH_STAR_LABEL":
            i += 1
            continue

        # collect this ORG_WITH_STAR_LABEL run
        run_positions: List[int] = []
        j = i
        while j < n and grouped[positions[j]]["label"] == "ORG_WITH_STAR_LABEL":
            run_positions.append(positions[j])
            j += 1

        joined_run = " ".join(grouped[p]["text"] for p in run_positions)
        run_norm = _normalize_for_match_letters_only(joined_run)


        if run_norm.startswith(target_norm):

            return run_positions[0]
        else:
           pass

        # move past this run
        i = j

    return None

def compute_doc_bounds(
    grouped: Grouped,
    doc: SumarioDoc,
) -> None:
    if not grouped:
        return

    positions = sorted(grouped.keys())
    max_pos = positions[-1]

    # 1) start: where this doc's header is
    start = _find_header_run_start(grouped, doc.header_texts)
    doc.header_start = start

    if start is None:
        return

    # 2) end: where the NEXT header begins (exclusive)
    if doc.next_header_texts:
        next_start = _find_header_run_start(grouped, doc.next_header_texts)

        if next_start is not None and next_start > start:
            doc.doc_end = next_start  # EXCLUSIVE
        else:
            doc.doc_end = max_pos + 1
    else:
        # last doc → until after the last position
        doc.doc_end = max_pos + 1



def assign_grouped_to_docs(grouped: Grouped, docs: List[SumarioDoc]) -> None:
    if not grouped or not docs:
        return

    for doc in docs:
        compute_doc_bounds(grouped, doc)

    for doc in docs:
        doc.attach_from_grouped_slice(grouped, doc.header_start, doc.doc_end)
        
        if doc.entities:
            doc.align_orgs_and_doc_names_from_entities()



def main(grouped: Grouped, grouped_blocks: AllGroupedBlocks):

    docs = build_sumario_docs_from_grouped_blocks(grouped_blocks)

    assign_grouped_to_docs(grouped, docs)

    for d in docs:
        print(d)
