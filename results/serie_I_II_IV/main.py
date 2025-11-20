from typing import Dict, List, Optional, TypedDict
from .helper import _normalize_for_match_letters_only, _is_close_match, _norm_for_match



class DocSegment(TypedDict):
    start: int              # first position (inclusive)
    end: int                # end position (exclusive)
    positions: List[int]    # all entity positions in [start, end)


class DocEntry(TypedDict):
    header_texts: List[str]
    org_idx: int
    org_name: str
    doc_name: Optional[str]
    segment_text: str



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

        
        self.org_positions: List[tuple[int, int]] = [] # (pos, idx_in_org_texts)      
        self.doc_name_positions: List[tuple[int, int]] = [] # (pos, idx_in_doc_name)
        

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
        """
        Use self.entities (already sliced) to align:
        - self.org_texts   with org-like entities
        - self.doc_name    with DOC_NAME_LABEL entities

        Fills:
        - self.org_positions      as list[(pos, idx_in_org_texts)]
        - self.doc_name_positions as list[(pos, idx_in_doc_name)]
        """

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

        # --- ORG matching ---
        used_org_positions: set[int] = set()
        for expected_idx, expected in enumerate(self.org_texts):
            match_pos = None

            for pos, text in org_candidates:
                if pos in used_org_positions:
                    continue

                if _is_close_match(expected, text):
                    match_pos = pos
                    used_org_positions.add(pos)
                    break

            if match_pos is not None:
                # store (position, index of expected org_text)
                self.org_positions.append((match_pos, expected_idx))

        # --- DOC_NAME matching ---
        used_doc_positions: set[int] = set()
        for expected_idx, expected in enumerate(self.doc_name):
            match_pos = None

            for pos, text in doc_name_candidates:
                if pos in used_doc_positions:
                    continue

                if _is_close_match(expected, text):
                    match_pos = pos
                    used_doc_positions.add(pos)
                    break

            if match_pos is not None:
                # store (position, index of expected doc_name)
                self.doc_name_positions.append((match_pos, expected_idx))

        # --- Fallback for blocks where no org matched ---
        # Example: header is one big ORG_LABEL in grouped_blocks,
        # but in grouped it's split into several ORG_WITH_STAR_LABEL lines.
        # If we have a known header_start and at least one org_text,
        # treat header_start as the org anchor for org_idx 0.
        if not self.org_positions and self.header_start is not None and self.org_texts:
            self.org_positions.append((self.header_start, 0))


    def build_docs_by_org(self) -> Dict[int, List[DocEntry]]:
        """
        Build a mapping:
            org_idx -> [DocEntry, DocEntry, ...]

        Segment rules (when there are doc_name_positions):
          - Each doc_name anchor defines a document.
          - Segment START:
                * if this is the first doc for that org: start at that org's position
                  (if it exists and is <= doc_name_pos), otherwise at doc_name_pos
                * if it's NOT the first doc for that org: start at doc_name_pos
          - Segment END:
                * min(next doc_name position, next org position > this doc_name_pos)
                * or end of entities if none.
        If there are no doc_name_positions, we use org_positions only.
        """
        if not self.entities:
            return {}

        all_positions = sorted(self.entities.keys())
        if not all_positions:
            return {}

        docs_by_org: Dict[int, List[DocEntry]] = {}

        doc_name_positions = sorted(self.doc_name_positions, key=lambda x: x[0])
        org_positions = sorted(self.org_positions, key=lambda x: x[0])

        last_entity_end = all_positions[-1] + 1

        segments: List[tuple[int, int, Optional[int], int, List[int]]] = []
        # each element: (start, end, doc_idx, org_idx, seg_positions)

        if doc_name_positions:
            # Helper: map from doc_name_pos to its org (last org <= doc_name_pos)
            def find_org_for_doc(doc_pos: int) -> Optional[tuple[int, int]]:
                """Return (org_pos, org_idx) where org_pos is the last org <= doc_pos."""
                org_pos_for_doc: Optional[int] = None
                org_idx_for_doc: Optional[int] = None
                for pos, idx in org_positions:
                    if pos <= doc_pos:
                        org_pos_for_doc = pos
                        org_idx_for_doc = idx
                    else:
                        break
                if org_idx_for_doc is None:
                    return None
                return org_pos_for_doc, org_idx_for_doc

            def next_doc_name_pos_after(pos: int) -> Optional[int]:
                for dn_pos, _ in doc_name_positions:
                    if dn_pos > pos:
                        return dn_pos
                return None

            def next_org_pos_after(pos: int) -> Optional[int]:
                for org_pos, _ in org_positions:
                    if org_pos > pos:
                        return org_pos
                return None

            seen_orgs: set[int] = set()

            for i, (doc_pos, doc_idx) in enumerate(doc_name_positions):
                org_info = find_org_for_doc(doc_pos)
                if org_info is None:
                    # No org found before this doc_name; skip or treat specially
                    continue

                org_pos_for_doc, org_idx_for_doc = org_info

                # START:
                #   - if first time we see this org → start at org_pos (if it’s <= doc_pos)
                #   - else → start at doc_pos
                if org_idx_for_doc not in seen_orgs and org_pos_for_doc is not None:
                    start_pos = min(org_pos_for_doc, doc_pos)
                    seen_orgs.add(org_idx_for_doc)
                else:
                    start_pos = doc_pos

                # END:
                #   min(next doc_name, next org change) or end of entities
                ndn = next_doc_name_pos_after(doc_pos)
                nog = next_org_pos_after(doc_pos)
                candidates = [x for x in (ndn, nog) if x is not None]
                if candidates:
                    end_pos = min(candidates)
                else:
                    end_pos = last_entity_end

                seg_positions = [p for p in all_positions if start_pos <= p < end_pos]
                if not seg_positions:
                    continue

                segments.append((start_pos, end_pos, doc_idx, org_idx_for_doc, seg_positions))

        else:
            # No doc_name_positions: segment only by org anchors
            if not org_positions:
                return {}

            for i, (org_pos, org_idx_for_segment) in enumerate(org_positions):
                if i + 1 < len(org_positions):
                    end_pos = org_positions[i + 1][0]
                else:
                    end_pos = last_entity_end

                start_pos = org_pos
                seg_positions = [p for p in all_positions if start_pos <= p < end_pos]
                if not seg_positions:
                    continue

                # doc_idx is None here
                segments.append((start_pos, end_pos, None, org_idx_for_segment, seg_positions))

        # Build final dict keyed by org_idx
        for start_pos, end_pos, doc_idx, org_idx_for_segment, seg_positions in segments:
            # org name
            if 0 <= org_idx_for_segment < len(self.org_texts):
                org_name = self.org_texts[org_idx_for_segment]
            else:
                org_name = ""

            # doc name
            if doc_idx is not None and 0 <= doc_idx < len(self.doc_name):
                doc_name_text: Optional[str] = self.doc_name[doc_idx]
            else:
                doc_name_text = None

            # concatenated text for segment
            segment_text = " ".join(
                self.entities[p]["text"] for p in seg_positions
            ).strip()
            if not segment_text:
                continue

            entry: DocEntry = {
                "header_texts": self.header_texts,
                "org_idx": org_idx_for_segment,
                "org_name": org_name,
                "doc_name": doc_name_text,
                "segment_text": segment_text,
            }

            docs_by_org.setdefault(org_idx_for_segment, []).append(entry)

        return docs_by_org
    
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
        header_texts = block.get("ORG_WITH_STAR_LABEL", [] or [])
        org_texts = block.get("ORG_LABEL", [] or [])
        doc_names = block.get("DOC_NAME_LABEL", [] or [])
        paragraphs = block.get("PARAGRAPH", [] or [])

        # Fallback: some docs only have ORG_LABEL, no ORG_with_STAR_LABEL
        if not header_texts and org_texts:
            header_texts = org_texts

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

    ORG_HEADER_LABELS = {"ORG_WITH_STAR_LABEL", "ORG_LABEL"}

    while i < n:
        pos = positions[i]
        ent = grouped[pos]
        label = ent["label"]

        if label not in ORG_HEADER_LABELS:
            i += 1
            continue

        # collect this header run (ORG_WITH_STAR_LABEL and/or ORG_LABEL)
        run_positions: List[int] = []
        j = i
        while j < n and grouped[positions[j]]["label"] in ORG_HEADER_LABELS:
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
        if doc.header_start is None or doc.doc_end is None:
            # Optional debug:
            print(f"[WARN] Skipping doc {doc.idx}: header_start={doc.header_start}, doc_end={doc.doc_end}")
            continue

        doc.attach_from_grouped_slice(grouped, doc.header_start, doc.doc_end)

        if doc.entities:
            doc.align_orgs_and_doc_names_from_entities()




def main(grouped: Grouped, grouped_blocks: AllGroupedBlocks):

    docs = build_sumario_docs_from_grouped_blocks(grouped_blocks)

    assign_grouped_to_docs(grouped, docs)

    for d in docs:

        print(
            f"[DEBUG] Doc {d.idx}: "
            f"header_start={d.header_start}, doc_end={d.doc_end}, "
            f"entities={len(d.entities)}, "
            f"org_positions={d.org_positions}, "
            f"doc_name_positions={d.doc_name_positions}"
        )
        
        org = d.build_docs_by_org()
        print("ORG_DICT:", org)