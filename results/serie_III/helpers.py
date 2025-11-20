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
    return _normalize_for_match_letters_only(s or "")


def _is_close_match(
    a: str,
    b: str,
    *,
    prefix_threshold: float = 0.85,
    contain_threshold: float = 0.6,
) -> bool:
    """
    Returns True if a and b are "close enough" after normalization.
    - First tries strict equality.
    - Then a long common-prefix ratio.
    - Then a containment check: shorter is substring of longer
      and is at least `contain_threshold` fraction of it.
    """
    na = _norm_for_match(a)
    nb = _norm_for_match(b)

    if not na or not nb:
        return False

    # 1) strict equality
    if na == nb:
        return True

    # 2) large common prefix
    common_len = len(os.path.commonprefix([na, nb]))
    longest = max(len(na), len(nb))
    if longest == 0:
        return False

    prefix_ratio = common_len / float(longest)
    if prefix_ratio >= prefix_threshold:
        return True

    # 3) containment: shorter fully inside longer with enough coverage
    if len(na) < len(nb):
        shorter, longer = na, nb
    else:
        shorter, longer = nb, na

    if shorter and shorter in longer:
        contain_ratio = len(shorter) / float(len(longer))
        if contain_ratio >= contain_threshold:
            return True

    return False
