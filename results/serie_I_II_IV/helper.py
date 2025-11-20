import unicodedata
import re
import os

def _normalize_for_match_letters_only(s: str) -> str:
    """Normalize a string for matching org names using letters-only semantics."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.casefold()
    s = re.sub(r'\s+', '', s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = "".join(ch for ch in s if ch.isalpha())
    return s


def _norm_for_match(s: str) -> str:
    # If you already have _normalize_for_match_letters_only, you can reuse it
    return _normalize_for_match_letters_only(s or "")

def _is_close_match(a: str, b: str, *, prefix_threshold: float = 0.85) -> bool:
    """
    Returns True if a and b are "close enough" after normalization.
    - First tries strict equality.
    - Then falls back to a long common-prefix ratio.
    """
    na = _norm_for_match(a)
    nb = _norm_for_match(b)

    if not na or not nb:
        return False

    # 1) strict equality
    if na == nb:
        return True

    # 2) large common prefix (e.g. only suffix differs: ABERTO vs FECHADO)
    common_len = len(os.path.commonprefix([na, nb]))
    longest = max(len(na), len(nb))
    if longest == 0:
        return False

    prefix_ratio = common_len / float(longest)
    return prefix_ratio >= prefix_threshold

