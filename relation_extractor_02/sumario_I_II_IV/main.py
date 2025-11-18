LABELS = {
    "Sumario",
    "ORG_LABEL",
    "ORG_WITH_STAR_LABEL",
    "DOC_NAME_LABEL",
    "DOC_TEXT",
    "PARAGRAPH",
    "JUNK_LABEL",
    "SERIE_III",
    "ASSINATURA",
}



def _split_by_org_headers(items):
    """
    items: dict[int, {"text": str, "label": str}]
    returns: list[dict[int, {"text", "label"}]]
    """
    blocks = []
    current = {}
    star_mode = False  # False = Phase 1 (ORG), True = Phase 2 (STAR)

    for i in sorted(items.keys()):
        label = items[i]["label"]

        if not star_mode:
            # Phase 1: split by ORG_LABEL, switch to star_mode on first ORG_WITH_STAR_LABEL
            if label == "ORG_WITH_STAR_LABEL":
                star_mode = True
                if current:
                    blocks.append(current)
                current = {i: items[i]}
            elif label == "ORG_LABEL":
                if current:
                    blocks.append(current)
                current = {i: items[i]}
            else:
                current[i] = items[i]
        else:
            # Phase 2: split only by ORG_WITH_STAR_LABEL
            if label == "ORG_WITH_STAR_LABEL":
                if current:
                    blocks.append(current)
                current = {i: items[i]}
            else:
                current[i] = items[i]

    if current:
        blocks.append(current)

    return blocks


def sumario_dic(items):

    blocks = _split_by_org_headers(items)

    return blocks