# ========================================================================
def has_letters_ignoring_newlines(text: str) -> bool:
    # Remove newlines so they don't interfere
    t = text.replace("\n", "")
    # Keep entry if ANY character is alphabetic (works with accents too)
    return any(ch.isalpha() for ch in t)


def clean_sumario(sumario_dict: dict) -> dict:
    return {
        k: v
        for k, v in sumario_dict.items()
        if has_letters_ignoring_newlines(v.get("text", ""))
    }

from collections import defaultdict

ORG_BREAK_LABELS = {"ORG_LABEL", "ORG_WITH_STAR_LABEL"}

def sumario_to_blocks(sumario_dict: dict) -> list[dict]:
    """
    Turn a flat sumario_dict into a list of blocks.
    - Each block is a dict: {label: [text, text, ...]}
    - A new block starts whenever we see ORG_LABEL or ORG_WITH_STAR_LABEL.
    - ORG text is included in the block.
    """
    blocks: list[dict] = []
    current_block: dict | None = None

    # iterate in order of keys
    for k in sorted(sumario_dict.keys()):
        entry = sumario_dict[k]
        label = entry["label"]
        text = entry["text"]

        # New org ⇒ start new block
        if label in ORG_BREAK_LABELS:
            current_block = {}
            blocks.append(current_block)

        # ignore anything before the first org
        if current_block is None:
            continue

        current_block.setdefault(label, []).append(text)

    return blocks


# =========================================================================