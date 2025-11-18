from collections import defaultdict
from typing import Dict, List


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

def _group_block_entities_by_label(blocks: List[Dict[int, Dict[str, str]]]) -> Dict[int, Dict[str, List[str]]]:
    """
    Processes a list of entity blocks and groups the entity text within each block
    by its label.

    Args:
        blocks: A list of dictionaries, where each dict is a block 
                (key=position, value={'text': str, 'label': str}).

    Returns:
        A dictionary where the key is the block's index (position) and the value 
        is a dictionary mapping labels to a list of corresponding texts.
    """
    final_grouped_dict = {}
    
    # 1. Iterate through the list of blocks using enumerate to get the position
    for block_index, block in enumerate(blocks):
        # Use defaultdict to simplify grouping within the current block
        label_groups = defaultdict(list)
        
        # 2. Iterate through the items within the current block
        # We don't care about the entity position (i) here, just the data
        for i in block:
            item = block[i]
            text = item['text']
            label = item['label']
            
            # 3. Group the text under its label
            label_groups[label].append(text)
            
        # 4. Store the result for the current block index
        final_grouped_dict[block_index] = dict(label_groups)
        
    return final_grouped_dict


def sumario_dic(items):

    blocks = _split_by_org_headers(items)
    blocks_list = _group_block_entities_by_label(blocks)

    return blocks, blocks_list