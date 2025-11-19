from typing import Dict, List, Optional, TypedDict
from .helper import _normalize_for_match_letters_only


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
        self.paragraphs: List[str] = []
        self.signature: Optional[str] = None

        self.header_start: Optional[int] = None
        self.next_header_texts: List[str] | None = None

    def attach_from_grouped_slice(self, grouped: Grouped, start: int, end: int) -> None:

        """
        Fill this SumarioDoc from a slice of 'grouped' between start and end (inclusive),
        preserving the original positional order for ALL labels
        """

        # 1) Get positions in order within [start, end]
        positions_in_slice = sorted(
            pos for pos in grouped.keys()
            if start <= pos <= end
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


    def __repr__(self) -> str:
        return (
            f"SumarioDoc(idx={self.idx}, "
            f"header_texts={self.header_texts}, "
            f"org_texts={self.org_texts}, "
            f"doc_name={self.doc_name}, "
            f"doc_paragraph={self.doc_paragraph}, "
            f"header_start={self.header_start}, "
            f"next_header_texts={self.next_header_texts})"
        )

        


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




def find_header_start_in_grouped_for_doc(
    grouped: Grouped,
    doc: SumarioDoc,
) -> Optional[int]:
    """
    Set and return the start position in `grouped` that corresponds to
    doc.header_texts[0].

    Logic:
      - Only consider the FIRST contiguous run of ORG_WITH_STAR_LABEL in `grouped`.
      - That run may contain:
          * true header lines (first 1, 2, ...) and
          * possibly extra ORG_WITH_STAR_LABEL lines that actually belong
            to a normal org/company.
      - We try prefixes of that run:
          run[0], run[0:2], run[0:3], ...
        and look for a prefix whose normalized text matches doc.header_texts[0]
        (using _normalize_for_match_letters_only).

      - If found, we set doc.header_start to the position of run[0] and return it.
      - We do NOT decide the end here; the end of this doc will be determined
        later from the next doc's header_start at the multi-doc level.
    """
    # No header text in the doc → nothing to match
    if not doc.header_texts:
        return None

    # Normalize target header text from the class
    header_target_raw = doc.header_texts[0]
    header_target_norm = _normalize_for_match_letters_only(header_target_raw)
    if not header_target_norm:
        return None

    # No content to search
    if not grouped:
        return None

    positions = sorted(grouped.keys())

    # 1) Find the first contiguous run of ORG_WITH_STAR_LABEL
    run_positions: List[int] = []
    started = False

    for pos in positions:
        label = grouped[pos]["label"]
        if label == "ORG_WITH_STAR_LABEL":
            if not started:
                started = True
            run_positions.append(pos)
        else:
            if started:
                # we already started a run and hit a different label → stop
                break
            # else: we haven't started yet, keep scanning

    if not run_positions:
        return None

    # 2) Try prefixes of that run to find header match
    start_pos = run_positions[0]

    for prefix_len in range(1, len(run_positions) + 1):
        subset = run_positions[:prefix_len]
        joined_text = " ".join(grouped[p]["text"] for p in subset)
        candidate_norm = _normalize_for_match_letters_only(joined_text)

        if candidate_norm == header_target_norm:
            # Found the header; we only care about its start
            doc.header_start = start_pos
            return start_pos

    # No matching prefix found
    return None


def assign_grouped_to_docs(grouped: Grouped, docs: List[SumarioDoc]) -> None:
    if not grouped or not docs:
        return

    # CASE 1: Only one doc → whole grouped goes to that doc
    if len(docs) == 1:
        doc = docs[0]
        min_pos = min(grouped.keys())
        max_pos = max(grouped.keys())
        doc.attach_from_grouped_slice(grouped, min_pos, max_pos)
        return

    # CASE 2: Multiple docs → use header_start positions
    docs_with_start = [d for d in docs if d.header_start is not None]
    if not docs_with_start:
        return

    docs_sorted = sorted(docs_with_start, key=lambda d: d.header_start)  # type: ignore[arg-type]
    max_pos = max(grouped.keys())

    for i, doc in enumerate(docs_sorted):
        start = doc.header_start  # type: ignore[assignment]
        if start is None:
            continue

        if i < len(docs_sorted) - 1:
            next_start = docs_sorted[i + 1].header_start
            end = (next_start - 1) if next_start is not None else max_pos
        else:
            end = max_pos

        doc.attach_from_grouped_slice(grouped, start, end)



def main(grouped , grouped_blocks: AllGroupedBlocks):
    docs = build_sumario_docs_from_grouped_blocks(grouped_blocks)
    for doc in docs:
        find_header_start_in_grouped_for_doc(grouped, doc)
    
    assign_grouped_to_docs(grouped, docs)

    print("Number of SumarioDoc instances:", len(docs))
    for d in docs:
        print(d)