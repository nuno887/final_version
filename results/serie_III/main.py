from typing import Dict, List, Optional, TypedDict
from .helpers import _norm_for_match, _is_close_match, _normalize_for_match_letters_only


class ExportDoc(TypedDict):
    header_texts: List[str]
    org_texts: List[str]
    doc_name: str
    body: str


class Section(TypedDict):
    title_pos: int
    title_sumario: str
    title_body: str
    docs: List[Dict[str, object]]  # internal, not the final export


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

        self.anchor_idx: Optional[int] = None # where this doc starts in body_dict
        self.body_positions: List[int] = [] # list of body_dict keys
        self.body_entries: Dict[int, Dict[str, str]] = {} # slice of body_dict for this doc

        self.doc_name_positions: List[int] = []        # where doc_name matches in body_entries
        self.doc_paragraph_positions: List[int] = []   # where doc_paragraph matches in body_entries
        self.doc_name_matches: List[tuple[str, int, str]] = []
        self.doc_paragraph_matches: List[tuple[str, int, str]] = []

    
    @classmethod
    def from_block(cls, idx: int, block: Dict[str, List[str]]) -> "SumarioDoc":
        return cls(
            idx=idx,
            header_texts=block.get("ORG_WITH_STAR_LABEL", []),
            org_texts=block.get("ORG_LABEL", []),
            doc_name=block.get("DOC_NAME_LABEL", []),
            doc_paragraph=block.get("PARAGRAPH", []), 
        )
    
    #===================================================================================

    def build_sections(self) -> None:
        """
        Build internal sections structure:

            self.sections: List[Section]

        Each Section groups DOC_PARAGRAPH docs under one DOC_NAME title.
        Titles with no paragraphs are ignored.
        """
        self.sections: List[Section] = []

        if not self.body_entries:
            return

        # maps from body idx -> (sumário_text, body_text) for titles
        name_by_pos: Dict[int, tuple[str, str]] = {
            idx: (sum_text, body_text)
            for (sum_text, idx, body_text) in self.doc_name_matches
        }
        # maps from body idx -> sumário_text for paragraph docs
        para_by_pos: Dict[int, str] = {
            idx: sum_text for (sum_text, idx, _body_text) in self.doc_paragraph_matches
        }

        all_body_indices = sorted(self.body_entries.keys())
        if not all_body_indices:
            return

        title_positions = sorted(self.doc_name_positions)
        para_positions = sorted(self.doc_paragraph_positions)

        if not title_positions and not para_positions:
            return

        for i, title_pos in enumerate(title_positions):
            # title metadata
            title_sumario, title_body = name_by_pos.get(
                title_pos, ("", self.body_entries[title_pos]["text"])
            )

            # section end boundary = next title or end of org block
            if i + 1 < len(title_positions):
                section_end = title_positions[i + 1]
            else:
                section_end = max(all_body_indices) + 1  # sentinel

            # paragraphs for this section
            my_para_positions = [
                p for p in para_positions if title_pos <= p < section_end
            ]

            # ignore titles with no paragraph docs
            if not my_para_positions:
                continue

            docs_in_section: List[Dict[str, object]] = []

            for j, start_pos in enumerate(my_para_positions):
                if j + 1 < len(my_para_positions):
                    next_start = my_para_positions[j + 1]
                    end_boundary = next_start
                else:
                    end_boundary = section_end

                doc_indices = [
                    idx
                    for idx in all_body_indices
                    if start_pos <= idx < end_boundary
                ]
                if not doc_indices:
                    continue

                sumario_text = para_by_pos.get(start_pos, "")

                docs_in_section.append(
                    {
                        "start_pos": min(doc_indices),
                        "end_pos": max(doc_indices) + 1,
                        "sumario_text": sumario_text,
                        "indices": doc_indices,
                    }
                )

            if not docs_in_section:
                continue

            self.sections.append(
                Section(
                    title_pos=title_pos,
                    title_sumario=title_sumario,
                    title_body=title_body,
                    docs=docs_in_section,
                )
            )

    def to_flat_docs(self) -> List[ExportDoc]:
        """
        Export this SumarioDoc as a flat list of docs with:
          header_texts, org_texts, doc_name (section title), body (concatenated slice).
        """
        results: List[ExportDoc] = []

        # if sections not built yet, build them
        if not hasattr(self, "sections") or not self.sections:
            self.build_sections()

        for section in self.sections:
            # choose which version of the title to emit as DOC_NAME:
            #   - section["title_sumario"] (sumário-cleaned), or
            #   - section["title_body"] (exact body text)
            doc_name = section["title_sumario"] or section["title_body"]

            for sub in section["docs"]:
                indices = sorted(sub["indices"])  # type: ignore
                texts = [self.body_entries[i]["text"] for i in indices]
                body_text = "\n\n".join(texts)

                results.append(
                    ExportDoc(
                        header_texts=self.header_texts,
                        org_texts=self.org_texts,
                        doc_name=doc_name,
                        body=body_text,
                    )
                )

        return results
    #===================================================================================
    
    def compute_doc_positions(self) -> None:
        """
        Populate:
          - doc_name_positions / doc_name_matches
          - doc_paragraph_positions / doc_paragraph_matches
        by matching sumário texts against DOC_NAME_LABEL in body_entries.
        """
        self.doc_name_positions = []
        self.doc_paragraph_positions = []
        self.doc_name_matches = []
        self.doc_paragraph_matches = []

        # collect DOC_NAME_LABEL entries inside this org block
        docname_entries: List[tuple[int, str]] = []
        for idx in sorted(self.body_entries.keys()):
            entry = self.body_entries[idx]
            if entry.get("label") == "DOC_NAME_LABEL":
                docname_entries.append((idx, entry.get("text", "")))

        if not docname_entries:
            return

        def _match_texts(
            texts: List[str],
        ) -> tuple[List[int], List[tuple[str, int, str]]]:
            positions: List[int] = []
            matches: List[tuple[str, int, str]] = []
            used_indices: set[int] = set()
            cursor = 0

            for t in texts:
                if not t:
                    continue
                for j in range(cursor, len(docname_entries)):
                    idx, body_text = docname_entries[j]
                    if idx in used_indices:
                        continue
                    if _is_close_match(t, body_text):
                        positions.append(idx)
                        matches.append((t, idx, body_text))
                        used_indices.add(idx)
                        cursor = j + 1
                        break
            return positions, matches

        # doc_name → positions + matches
        self.doc_name_positions, self.doc_name_matches = _match_texts(self.doc_name)

        # doc_paragraph → positions + matches
        self.doc_paragraph_positions, self.doc_paragraph_matches = _match_texts(
            self.doc_paragraph
        )
    
    def __repr__(self) -> str:
        return (
            f"SumarioDoc(idx={self.idx}, "
            f"anchor_idx={self.anchor_idx}, "
            f"org_texts={self.org_texts!r}, "
            f"doc_name={self.doc_name!r}, "
            f"body_entries={self.body_entries})"
        )



def build_sumario_docs(blocks: List[GroupedBlock]) -> List[SumarioDoc]:
    docs: List[SumarioDoc] = []
    for idx, block in enumerate(blocks):
        docs.append(SumarioDoc.from_block(idx, block))
    return docs



ORG_LABELS = {"ORG_LABEL", "ORG_WITH_STAR_LABEL"}


def build_body_org_index(body_dict: Dict[int, Dict[str, str]]) -> List[tuple[int, str]]:
    """
    Returns a list of (idx, text) for org entries in body_dict,
    in ascending idx order.
    """
    org_entries: List[tuple[int, str]] = []
    for idx in sorted(body_dict.keys()):
        entry = body_dict[idx]
        if entry.get("label") in ORG_LABELS:
            org_entries.append((idx, entry.get("text", "")))
    return org_entries


def assign_doc_anchors(
    sumario_docs: List[SumarioDoc],
    body_dict: Dict[int, Dict[str, str]],
) -> None:
    """
    For each SumarioDoc, find the corresponding org position in body_dict
    by scanning only ORG_LABEL / ORG_WITH_STAR_LABEL entries and using
    _is_close_match. Updates doc.anchor_idx in-place.
    """
    org_entries = build_body_org_index(body_dict)  # [(idx, text), ...]
    pos = 0  # current index in org_entries

    for doc in sumario_docs:
        # Collect candidate names to match for this doc
        candidates: List[str] = []
        candidates.extend(doc.org_texts)
        candidates.extend(doc.header_texts)

        if not candidates:
            continue  # nothing to match for this doc

        anchor_idx: Optional[int] = None

        # search in org_entries from current pos forward
        while pos < len(org_entries) and anchor_idx is None:
            body_idx, body_text = org_entries[pos]

            # if any candidate "close matches" this body org text, we anchor here
            if any(_is_close_match(cand, body_text) for cand in candidates):
                anchor_idx = body_idx

            pos += 1  # always move forward to avoid reusing the same org

        doc.anchor_idx = anchor_idx


def attach_body_segments(
    sumario_docs: List[SumarioDoc],
    body_dict: Dict[int, Dict[str, str]],
) -> None:
    """
    Using anchor_idx on each SumarioDoc, assign each doc:
      - body_positions: the body_dict keys that belong to that doc
      - body_entries: a dict[int, entry] slice of body_dict
    """
    anchored_docs = [d for d in sumario_docs if d.anchor_idx is not None]
    if not anchored_docs:
        return

    anchored_docs.sort(key=lambda d: d.anchor_idx)  # type: ignore

    all_body_indices = sorted(body_dict.keys())

    for i, doc in enumerate(anchored_docs):
        start = doc.anchor_idx  # type: ignore

        if i + 1 < len(anchored_docs):
            next_start = anchored_docs[i + 1].anchor_idx  # type: ignore
        else:
            next_start = None

        positions: List[int] = []
        for idx in all_body_indices:
            if idx < start:
                continue
            if next_start is not None and idx >= next_start:
                break
            positions.append(idx)

        doc.body_positions = positions
        doc.body_entries = {idx: body_dict[idx] for idx in positions}





def main(blocks, body_dict):
    all_docs: list[ExportDoc] = []

    sumario_docs = build_sumario_docs(blocks)
    assign_doc_anchors(sumario_docs, body_dict)
    attach_body_segments(sumario_docs, body_dict)


    for doc in sumario_docs:
        doc.compute_doc_positions()
        flat_docs = doc.to_flat_docs()
        all_docs.extend(flat_docs)

    return all_docs



