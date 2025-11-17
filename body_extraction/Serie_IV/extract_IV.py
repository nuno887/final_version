def split_doc_by_assinatura(doc):
    """
    Split a spaCy Doc into sections using entities with label 'ASSINATURA'
    as boundaries and return the desired item structure.

    When saving in the item, skip any text chunks that do not contain letters.
    """

    def has_letters(text: str) -> bool:
        # True if there's at least one alphabetic character
        return any(ch.isalpha() for ch in text)

    # Get ASSINATURA entities ordered by their position
    assinaturas = sorted(
        [ent for ent in doc.ents if ent.label_ == "ASSINATURA"],
        key=lambda e: e.start
    )

    # If no ASSINATURA entities, return the whole text as a single doc (only if it has letters)
    full_text = doc.text.strip()
    if not assinaturas:
        docs = []
        if full_text and has_letters(full_text):
            docs.append({
                "title": None,
                "sub_org": None,
                "text": full_text,
            })
        return {
            "org": None,
            "docs": docs,
        }

    docs = []
    last_token_i = 0  # token index, not char

    for ent in assinaturas:
        end_i = ent.end  # end is *exclusive* token index
        # Take text from last boundary up to (and including) this ASSINATURA
        chunk_text = doc[last_token_i:end_i].text.strip()
        if chunk_text and has_letters(chunk_text):
            docs.append({
                "title": None,
                "sub_org": None,
                "text": chunk_text,
            })
        last_token_i = end_i  # next block starts right after this ASSINATURA

    # Trailing text after the last ASSINATURA (optional)
    tail_text = doc[last_token_i:].text.strip()
    if tail_text and has_letters(tail_text):
        docs.append({
            "title": None,
            "sub_org": None,
            "text": tail_text,
        })

    item = {
        "org": None,
        "docs": docs,
    }
    return item
