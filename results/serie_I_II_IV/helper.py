import unicodedata
import re


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