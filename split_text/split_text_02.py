
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

def _normalize_for_match_letters_and_digits(s: str) -> str:
    """
    Normalize a string for matching doc names using letters+digits semantics.

    Same as _normalize_for_match_letters_only, but keeps numeric characters.
    Use this for DOC_NAME_LABEL comparisons where numbers matter.
    """
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.casefold()
    s = re.sub(r'\s+', '', s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # keep letters and digits
    s = "".join(ch for ch in s if ch.isalnum())
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
    initial_doc_name_text = None  # Variable to store the first DOC_NAME_LABEL

    # 1. Find the position of the last "Sumario"
    for position in sorted(indexed_entity_dict.keys(), reverse=True):
        entry = indexed_entity_dict[position]
        label = entry['label']
        if label == "Sumario":
            last_sumario_position = position
            break
    
    # 2. Search for the first ORG and subsequently the first DOC_NAME_LABEL after that position
    if last_sumario_position != -1:
        # Iterate through keys in normal order
        for position in sorted(indexed_entity_dict.keys()):
            if position > last_sumario_position:
                entry = indexed_entity_dict[position]
                text = entry['text']
                label = entry['label']

                # A. Find the first ORG (Required starting point)
                if target_org_text is None and label in ["ORG_WITH_STAR_LABEL", "ORG_LABEL"]:
                    target_org_text = text
                    position_org = position 
                    # DO NOT BREAK YET, we need to continue searching for the DOC_NAME_LABEL

                # B. Find the first DOC_NAME_LABEL *after* the ORG was found
                if target_org_text is not None:
                    # Only search for DOC_NAME_LABEL once target_org_text has been set
                    if initial_doc_name_text is None and label == "DOC_NAME_LABEL":
                        initial_doc_name_text = text
                        
                        # We can break now, as both required entities have been found
                        break
                        
    # The function returns three values
    return target_org_text, initial_doc_name_text, position_org

def _find_next_matching_org(indexed_entity_dict, target_org_text, initial_doc_name_text, position_org):
    next_match_position = None
    
    # Normalizations and Labels
    normalized_target_org = _normalize_for_match_letters_only(target_org_text)
    target_org_labels = ["ORG_WITH_STAR_LABEL", "ORG_LABEL"]
    target_doc_labels = ["DOC_NAME_LABEL"] 
    sorted_positions = sorted(indexed_entity_dict.keys())

    if position_org is None:
        raise ValueError(
            f"Cannot proceed: The starting organization text ('{target_org_text}') "
            "was found, but its position ('position_org') is invalid or missing. "
            "Check the preceding '_find_org_after_last_sumario' function."
        )

    # --------------------------------------------------------------------------
    # ----- FIRST PASS: safer prefix-based matching (ORG LABELS) -----
    # --------------------------------------------------------------------------
    for position in sorted_positions:
        if position <= position_org:
            continue

        entity_entry = indexed_entity_dict[position]
        label = entity_entry['label']
        
        if label in target_org_labels:
            text_to_normalize = entity_entry['text'].strip()
            normalized_current = _normalize_for_match_letters_only(text_to_normalize)
            
            if (normalized_current.startswith(normalized_target_org) or
                normalized_target_org.startswith(normalized_current)
            ):
                next_match_position = position
                break

    # --------------------------------------------------------------------------
    # ----- SECOND PASS (FALLBACK): original substring logic (ORG LABELS) -----
    # --------------------------------------------------------------------------
    if next_match_position is None:
        for position in sorted_positions:
            if position <= position_org:
                continue

            entity_entry = indexed_entity_dict[position]
            label = entity_entry['label']

            if label in target_org_labels:
                text_to_normalize = entity_entry['text'].strip()
                normalized_current = _normalize_for_match_letters_only(text_to_normalize)

                if (normalized_target_org in normalized_current) or \
                   (normalized_current in normalized_target_org):
                    next_match_position = position
                    break

    # --------------------------------------------------------------------------
    # ----- THIRD PASS (FINAL FALLBACK): DOC_NAME_LABEL comparison (SECOND MATCH) -----
    # --------------------------------------------------------------------------
    if next_match_position is None:
        
        if not initial_doc_name_text:
            print(f"DEBUG: Skipping DOC_NAME_LABEL fallback as initial_doc_name_text is empty.")
        else:
            normalized_target_doc = _normalize_for_match_letters_and_digits(initial_doc_name_text)
            match_count = 0 

            for position in sorted_positions:
                if position <= position_org:
                    continue
    
                entity_entry = indexed_entity_dict[position]
                label = entity_entry['label']
    
                if label in target_doc_labels:
                    text_to_normalize = entity_entry['text'].strip()
                    normalized_current = _normalize_for_match_letters_and_digits(text_to_normalize)
                    
                    # Using the combined prefix/substring logic
                    prefix_match = (
                        normalized_current.startswith(normalized_target_doc) or
                        normalized_target_doc.startswith(normalized_current)
                    )
                    substring_match = (
                        normalized_target_doc in normalized_current
                    ) or (
                        normalized_current in normalized_target_doc
                    )
                    
                    if prefix_match or substring_match:
                        match_count += 1
                        
                        if match_count == 2:
                            next_match_position = position
                            break


    if next_match_position is None:
        all_target_labels = target_org_labels + target_doc_labels
        raise ValueError(
            f"Could not find a subsequent matching entity (labels: {all_target_labels}) "
            f"starting after position {position_org}. Target ORG: '{target_org_text}', "
            f"Target DOC: '{initial_doc_name_text}'."
        )
    
    # --------------------------------------------------------------------------
    # ----- FINAL DICTIONARY SLICING (WITH REQUIRED OVERLAP AT position_org) -----
    # --------------------------------------------------------------------------
    
    # Determine if the DOC_NAME_LABEL fallback was used
    division_label = indexed_entity_dict[next_match_position]['label']
    doc_fallback_used = division_label in target_doc_labels

    sumario_dict = {}
    body_dict = {}

    for position in sorted_positions:
        if position < position_org:
            continue

        # 1. Entities from the division point onward go to the body
        if position >= next_match_position:
            body_dict[position] = indexed_entity_dict[position]
        
        # 2. Entities between the initial ORG and the division point (inclusive of position_org)
        elif position >= position_org and position < next_match_position:
            
            # This entity always belongs to the sumario/header segment
            sumario_dict[position] = indexed_entity_dict[position]
            
            # If the DOC fallback was used AND we are at the starting ORG, add it to body_dict
            if doc_fallback_used and position == position_org:
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
    
    # Capture the new initial_doc_name_text
    target_org, initial_doc_name, target_position = _find_org_after_last_sumario(indexed_entity_dict) 
    
    # Pass the initial_doc_name to the next function
    sumario_dict, body_dict = _find_next_matching_org(
        indexed_entity_dict, 
        target_org, 
        initial_doc_name,
        target_position
    )
    
    sumario_dict_merged = _merge_adjacent_star_orgs_in_dict(sumario_dict)

    return sumario_dict_merged, body_dict