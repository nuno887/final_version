from .Serie_I_II.types import SpanInfo, DocSlice, OrgBlockResult
from .Serie_I_II.extract import divide_body_by_org_and_docs, print_summary, normalize_doc_title

# ======================= Serie III ==========================
from .Serie_III.segmenter import divide_body_by_org_and_docs_serieIII
from .Serie_III.models import SubSlice, DocSlice, OrgResult
from .Serie_IV.extract_IV import split_doc_by_assinatura
# from .Serie_IV.debug import  DBG


# ============================================================
__all__ = [
    "SpanInfo",
    "DocSlice",
    "OrgBlockResult",
    "divide_body_by_org_and_docs",
    "print_summary",
    "normalize_doc_title",
    "divide_body_by_org_and_docs_serieIII",
    "SubSlice",
    "DocSlice",
    "OrgResult",
    "split_doc_by_assinatura"
]

