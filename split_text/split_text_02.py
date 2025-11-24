
import re
import unicodedata
from typing import Dict, List, Any

def _normalize_for_match_letters_only(s: str) -> str:
    """Normalize a string for matching org names using letters-only semantics."""
    if s is None: return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.casefold()
    s = re.sub(r'\s+', '', s) 
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = "".join(ch for ch in s if ch.isalpha())
    return s



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

def _extract_text_to_dic(doc):
    insertion_dict = {}
    for dict_index, ent in enumerate(doc.ents):
        insertion_dict[dict_index] = {
            'text': ent.text,
            'label': ent.label_
        }
    
    return insertion_dict


def _find_org_after_last_sumario(indexed_entity_dict):
    last_sumario_position = -1
    target_org_text = None
    position_org = None

    for position in sorted(indexed_entity_dict.keys(), reverse=True):
        entry = indexed_entity_dict[position]
        text = entry['text']
        label = entry['label']
        if label == "Sumario":
            last_sumario_position= position
            break
    
    # 2. Search for the first "ORG_WITH_STAR_LABEL" after that position
    if last_sumario_position != -1:
        #Iterate through keys in normal order
        for position in sorted(indexed_entity_dict.keys()):
            if position > last_sumario_position:
                entry = indexed_entity_dict[position]
                text = entry['text']
                label = entry['label']
                if label in ["ORG_WITH_STAR_LABEL", "ORG_LABEL"]:
                    target_org_text = text
                    position_org = position 
                    break

    return target_org_text, position_org

def _find_next_matching_org(indexed_entity_dict, target_org_text, position_org):
    next_match_text = None
    next_match_position = None
    
    # Normalize the text of the previously found organization once
    normalized_target = _normalize_for_match_letters_only(target_org_text)
    
    # 1. Define the labels to search for
    target_labels = ["ORG_WITH_STAR_LABEL", "ORG_LABEL"]

    sorted_positions = sorted(indexed_entity_dict.keys())

    if position_org is None:
        raise ValueError(
            f"Cannot proceed: The starting organization text ('{target_org_text}') "
            "was found, but its position ('position_org') is invalid or missing. "
            "Check the preceding '_find_org_after_last_sumario' function."
        )

    # ----- FIRST PASS: safer prefix-based matching -----
    for position in sorted_positions:
        if position <= position_org:
            continue

        entity_entry = indexed_entity_dict[position]
        text = entity_entry['text']
        label = entity_entry['label']
        
        if label in target_labels:
            text_to_normalize = text.strip()
            normalized_current = _normalize_for_match_letters_only(text_to_normalize)
            
            # Match must start at the beginning in at least one direction
            if (
                normalized_current.startswith(normalized_target) or
                normalized_target.startswith(normalized_current)
            ):
                next_match_position = position
                break

    # ----- SECOND PASS (FALLBACK): original substring logic -----
    if next_match_position is None:
        for position in sorted_positions:
            if position <= position_org:
                continue

            entity_entry = indexed_entity_dict[position]
            text = entity_entry['text']
            label = entity_entry['label']

            if label in target_labels:
                text_to_normalize = text.strip()
                normalized_current = _normalize_for_match_letters_only(text_to_normalize)

                # Old behavior: substring either way
                if (normalized_target in normalized_current) or \
                   (normalized_current in normalized_target):
                    next_match_position = position
                    break

    if next_match_position is None:
        raise ValueError(
            f"Could not find a subsequent matching organization (labels: {target_labels}) "
            f"starting after position {position_org} with text '{target_org_text}'."
        )
    
    sumario_dict = {}
    body_dict = {}

    # If a match was found, slice the dictionary up to (but excluding) the match position
    for position in sorted_positions:
        if position >= position_org and position < next_match_position:
            sumario_dict[position] = indexed_entity_dict[position]
        elif position >= next_match_position:
            body_dict[position] = indexed_entity_dict[position]
            
    return sumario_dict, body_dict


def _merge_adjacent_star_orgs_in_dict(segment_dict: Dict[int, Dict[str, str]]) -> Dict[int, Dict[str, str]]:
    """
    Merges adjacent entities within a dictionary segment if they both have 
    the label 'ORG_WITH_STAR_LABEL'.
    """
    if not segment_dict:
        return segment_dict

    merged_dict = {}
    keys = sorted(segment_dict.keys())
    i = 0

    while i < len(keys):
        current_key = keys[i]
        current_entry = segment_dict[current_key]
        current_label = current_entry['label']
        
        # Start a merge operation if the current label is the target
        if current_label == "ORG_WITH_STAR_LABEL":
            merged_text = current_entry['text']
            j = i + 1
            
            # Look ahead for adjacent keys
            while j < len(keys):
                next_key = keys[j]
                
                # Check for adjacency: keys must be consecutive integers
                if next_key == current_key + 1:
                    next_entry = segment_dict[next_key]
                    next_label = next_entry['label']
                    
                    if next_label == "ORG_WITH_STAR_LABEL":
                        # MERGE: Append text and update the current_key reference
                        # Use a space to join the text for readability
                        merged_text += " " + next_entry['text']
                        current_key = next_key # Advance the current_key reference
                        j += 1 # Move to the next potential entity
                    else:
                        break # Stop merging if the next label is different
                else:
                    break # Stop merging if the keys aren't adjacent
            
            # After merging, store the combined entity at the STARTING position (keys[i])
            merged_dict[keys[i]] = {
                'text': merged_text,
                'label': current_label # Label remains ORG_WITH_STAR_LABEL
            }
            # Advance the main counter (i) past all merged entities
            i = j
        
        else:
            # If not merging, just copy the entity
            merged_dict[current_key] = current_entry
            i += 1
            
    return merged_dict


def split_text(doc):
    indexed_entity_dict = _extract_text_to_dic(doc)
    #print(f"dict:", indexed_entity_dict)
    target_org, target_position = _find_org_after_last_sumario(indexed_entity_dict)
    sumario_dict, body_dict = _find_next_matching_org(indexed_entity_dict, target_org, target_position)
    sumario_dict_merged = _merge_adjacent_star_orgs_in_dict(sumario_dict)

    return sumario_dict_merged, body_dict