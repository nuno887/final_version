
uvicorn api:app --reload --port 8000


.\.venv\Scripts\activate

python -m pip install spacy==3.8.9 pymupdf==1.26.6 pymupdf4llm==0.2.2
python -m spacy download pt_core_news_lg

creating a new relation_extractor

=====================================================================================
# Results:
## Json structure

The system produces Json results with the following  top-level structure:<br>

{<br>
"error": ...,<br>
"raw_text": ...,<br>
"docs": [...]<br>
}
## Top level fields
<code>error</code>
Describes whether parsing succeeded or failed
* <code>null</code> -> Parsing was successful.
* Object -> Parsing failed, and the object contains diagnostic details.

### Example error object:

{<br>
"stage": "split_text",<br>
"code": "missing_sumario_or_body",<br>
"message": "Missing sumário_dict or body_dict after split after split_text for non-III série",<br>
"pdf": "path/to/file.pdf",<br>
"serie": "OTHER"<br>
}<br>
### Common fiels inside <code>error</code>:
<table>
  <thead>
    <tr>
      <th>Filed</th>
      <th>Meaning</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th><code>stage</code></th>
      <th>Step in processing where failure occurred</th>
    </tr>
    <tr>
      <th><code>code</code></th>
      <th>Exception</th>
    </tr>
    <tr>
      <th><code>message</code></th>
      <th>Human-readable explanation</th>
    </tr>
    <tr>
      <th><code>pdf</code></th>
      <th>Source file path</th>
    </tr>
    <tr>
      <th><code>serie</code></th>
      <th>Document classification/series type</th>
    </tr>
  </tbody>
</table>







# Componentes:
## pdf_markup (Transformar PDF's em texto):

<table>
  <thead>
    <tr>
      <th>File Name</th>
      <th>Primary Role</th>
      <th>Key Functionality</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>__init.py__</td>
      <td><strong> Package<br>Definition </strong></td>
      <td>Exposes the public API:<code>page_to_markdown</code>,<br><code>extract_pdf_to_markdown </code> and <code> get_settings </code>.</td>
    </tr>
    <tr>
      <td>config.py</td>
      <td><strong>Configuration<br>Loading</strong></td>
      <td>Defines the <code>Settings</code> data structure and the <code>get_settings</code> <br>function for hierarchical settings resolution.</td>
    </tr>
    <tr>
      <td>extractor.py</td>
      <td><strong>PDF Processing<br>Core</strong></td>
      <td>Contains the main logic for opening PDFs, applying crop<br>settings, convertng pages to Markdown using <code>pymupdf4llm</code>,<br> and applying cleanup heuristics.</td>
    </tr>
    <tr>
      <td>heuristics.py</td>
      <td><strong>Text Cleaning<br>Rules</strong></td>
      <td>Implements various functions (<code>crop_top</code>, <code>merge_bold_runs</code>)<br>to clean up common PDF-to-Markdown conversion artifacts.</td>
    </tr>
  </tbody>
</table>

 
  ### config.py
  This module handles how the application gets its configuration parameters (input_dir, output_dir, and crop_top). The get_settings function implements a clear precedence hierarchy to determine the final values:

  * Environment Variables (Highest Precedence): Checks for environment variables like PDF_MARKUP_INPUT.

  * appsettings.json
  
  * Built-in Defaults (Lowest Precedence): (input/, output/, crop_top=0.10).
  
  
  ### extracto.py
  
  This module is the heart of the PDF processing workflow, relying on external libraries like fitz (PyMuPDF) and pymupdf4llm (for optimized Markdown conversion).
  
  * **page_to_markdown**: Converts a single specified page of PDF to Markdown.
  * **extract_pdf_to_markdown**: Converts the entire PDF (excluding the last page if  **skip_last_page=True**) page by page.
    * It applies the **crop_top** heuristic (from **heuristics.py**) to remove headers/footers from the top of the page based on the **crop_top_ratio**.
    * It applies two different **bold-merging heuristics** based on the PDF file name (cheking for "IIISerie


### heuristics.py

This module contains functions to fix common structural errors introduced during the PDF-to-Markdown conversion process, mostly related to how text runs are represented.

* **crop_top(page, ratio)**: Modifies the PDF page's crop box to effectively hide the top portion, often used to eliminate repeated headers.
* **is_table_row(line)**: A helper function to detect if a line is part of a Markdown table (e.g., checks for the pipe | character).
* **merge_bold_runs_table_safe(md)**: This is a post-processing cleanup. It looks for consecutive lines that are entirely bold <code>(e.g., **TITLE**\n**SECTION**)</code> and merges them into a single bold block <code>(**TITLE\nSECTION**)</code>, as long as they are not inside a table.
* **merge_bold_runs_table_safe_allcaps(md)**: A stricter version of the bold merge that only consolidates consecutive bold lines if the content is also entirely **ALL-CAPS**. This is a more targeted approach to merging titles and headers while minimizing the risk of incorrectly combining normal bold text.

## spacy_modulo (Defining the Entities in the text)

<table>
  <thead>
    <tr>
      <th>Entity Label</th>
      <th>Example</th>
      <th>Definition</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Sumario</td>
      <td>{## **Sumário**, ## **Suplemento**}</td>
      <td>Represents the beginning of the document’s Sumário. Note: Select the last occurrence because multiple Sumário segments may appear..</td>
    </tr>
    <tr>
      <td>ORG_LABEL</td>
      <td>{SECRETARIA REGIONAL DE INCLUSÃO E JUVENTUDE}</td>
      <td>Represents the organization. Note: Identified by being in all-caps and located within the Sumário segment.</td>
    </tr>
    <tr>
      <td>ORG_WITH_STAR_LABEL</td>
      <td>{**RELAÇÕES DE TRABALHO**} </td>
      <td>Represents the organization or secretary and takes priority over the <code>"ORG_LABEL"</code>, Note: Same detection properties as <code>ORG_LABEL</code>, but contains *, which indicates bold text in the original document.</td>
    </tr>
    <tr>
      <td>DOC_NAME_LABEL</td>
      <td>{**Ato Societário n.º 72/2024**, **Cessação de funções de embro do órgão social**, **Decreto Legislativo Regional n.º 2-A/2008/M**  }</td>
      <td>Represents the specific document being reported by the organization. Note: Considered a <code>DOC_NAME_LABEL</code> when bold text appears in the Sumário and is associated with an <code>ORG_LABEL</code> / <code>ORG_WITH_STAR_LABEL</code>"</td>
    </tr>
    <tr>
      <td>DOC_TEXT</td>
      <td>Random line of text</td>
      <td>Represents secondary text without importance for document segmentation. Note: Still processed because all text must be labeled for downstream modules.</td>
    </tr>
    <tr>
      <td>PARAGRAPH</td>
      <td>Larger text excerpts, common in series III PDFs within the Sumário portion.</td>
      <td>Only relevant for series III documents due to the way their Sumário content is structured.</td>
    </tr>
    <tr>
      <td>JUNK_LABEL</td>
      <td>{1n\2n\\n, ..., ------, oisdjfds}</td>
      <td>Random characters resulting from older PDFs. Note: No text was removed except (1) everything before the start of Sumário and (2) the last page of each PDF.</td>
    </tr>
    <tr>
      <td>SERIE_III</td>
      <td>{Direção Regional do Trabalho e da Ação Inspetiva, **Regulamentação do Trabalho**, etc}</td>
      <td>Used only to avoid breaking classification groups (ORG_LABEL, ORG_WITH_STAR_LABEL, DOC_NAME_LABEL). Note: Not used for any other processing; only improves labeling for series III documents.</td>
    </tr>
  </tbody>
</table>

This modulo handles the classification of the text so we don't need to work with raw text, that way we don't need to worry about every time we make a comparation, division of the text, etc. For a better classification, we created 2 spacy pipelines, one for the **Series (I, II, IV)** and another for the **Serie III**.

To work with the pipelines we need to search for the def setup_entities, present in the (spacy_modulo/SerieIV/setupIV.py) and (spacy_modulo/Entities.py):

### Notes:
* Each **nlp.add_pipe**, represents a classification rule, and the order matters, some of the pipes modify the changes that came before.


## split_text (Devides the Sumario from the Body of the document)

This module contains utility functionality for cleaning, normalizing nad segmentating labeled entities extracted from a document (labeled by the spaCy). It's designed to separate the text from the summary information from its main textual content.

### Core Features
*  **String Normalization**: Cleans and standardizes text strings for comparison, ignoring common variations like accents, case, and whitespace.
*  **Entity Segmentation**: Splits a list of indexed entities into two distinct segments: a **Summary** and the **Document Body**
*  **Organization Merging**: Combines fragmented organization names into single, coherent entities.

<table>
  <thead>
    <tr>
      <th>Function</th>
      <th>Purpose</th>
      <th>Semantics</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>_normalize_for_match_letters_only(s)</code></td>
      <td>Used primarily for<br><strong>ORG_LABEL/ORG_WITH_STAR_LABEL</strong><br>matching.</td>
      <td>Converts to lowercase, removes, accents, removes all whitespace, and keeps <strong>only alphabetics characters</strong>.</td>
    </tr>
     <tr>
      <td><code>_normalize_for_match_letters_and_digits(s)</code></td>
      <td>Used for<br><strong>DOC_NAME_LABEL</strong><br>matching.</td>
      <td>Same as above, but keeps <strong>both letters and digits</strong> (e.g., to preserve document numbers like "Portaria 123").</td>
    </tr>

  </tbody>
</table>

**Notes** 
* The **sumario_dict_merged**, represent a dict of list, where we have labeled all the entities that the spaCy found, with the respective order in the original text. This section represents the summary.
* The **body_dict**, represent a dict of list, where we have labeled all the entities that the spaCy found, with the respective order in the original text. This section represents the body text.
* The function "_normalize_for_match_letters_and_digits(s)", for the pdf's where whe don't have the name of the organization in present in the body. We can consider this cases a error by the part of the author of the pdf.
    *  Important for the rest of the next modulos to work, we need to add that organization to the body segment, at the top of the **"body_dict"**.


## relation_extractor_02 (organization of the sumario_dict_merged)

This is a simple modulo that i made just for having a more organized **sumario_dict_merged**, we group the organizations with their respective sub-organizations/documento. That way we get the schema for the **body_dict** (body section), and we have a schema for dividing it in a concrete way. Important we can consider this the source of truth, but there are some pdf's that don't respect the order of the summary, not all the items in the summary are in the text, for this we will try to reslve in the next modulo **"results"**.

## results (final step)

### serie_I_II_IV

This module is the final assembly step, responsible for mapping raw, position-indexed entities (<code>grouped</code>) and pre-grouped header texts (<code>grouped_blocks</code>) into fully structured <code>SumarioDoc</code> objects.
#### Core Data Structures
<table>
  <thead>
    <tr>
      <th>Class/Type</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>Entity</code></code></td>
      <td>The base type: <code>{text: str, label: str}</code>.</td>
    </tr>
     <tr>
      <td><code>Grouped</code></td>
      <td>A dictionary mapping an entity's <bold>position</bold>(int) to its <code>Entity</code> data. This is the source of all raw data in positional order.</td>
    </tr>
     <tr>
      <td><code>AllGroupedBlocks</code></td>
      <td>A dictionary mapping a <bold>block index</bold> to list of texts grouped by their label (e.g., <code>ORG_LABEL</code>, <code>DOC_NAME_LABEL</code>). This prvides the clean, authoritative header texts for matching.</td>
    </tr>
     <tr>
      <td><code>SumarioDoc</code></td>
      <td><bold>The central object</bold> representing a single document candidate. It holds the authoritative header lists (from <code>grouped_blocks</code>) and, once processed, the actual sliced entities (self.entities) and calculated bounds (<code>header_start</code>, <code>doc_end</code>).</td>
    </tr>
     <tr>
      <td><code>DocEntry</code></td>
      <td>The final structured output: represents a sigle document (or sub-document(entry) defined by an Organization and Document Name, containing the concatenated <code>segment_text</code> (the document body</td>
    </tr>

  </tbody>
</table>

#### Key Functions and Workflow
The workflow starts by creating a <code>SumarioDoc</code> object for every header block found, then calculates the boundaries of where that document start and ends within the full entity list. Every **ORG_WITH_STAR_LABEL** represents a object.

1. <code>build_sumario_docs_from_grouped_blocks</code>
*  **Goal**: Initialization.
*  Creates one <code>SumarioDoc</code> instance for every entry in the input <code>grouped_blocks</code>.
*  Separates the lists of texts by label (<code>header_texts</code>, <code>org_texts</code>, <code>doc_name</code>, etc.).
*  Also calculates and assigns <code>next_header_texts</code> to each document, which is crucial for determining where the current document ends.

2. <code>_find_header_run_start</code>
*  **Goal**: Find Document Start.
*  Takes the authoritative header text (e.g, the ORG name) from <code>grouped_blocks</code>.
*  Searches the raw, positional entties (<code>grouped</code>) for a contiguous run of ORG_like labels that **closely match** taht header text (using prefix matching on normalized text).
*  Returns the **position** whre this run starts, defining the <code>header_start</code> of the <code>SumarioDoc</code>.

3. <code>compute_doc_bounds</code>
*  **Goal**: Define Document Boundaries.
*  Uses <code>_find_header_run_start</code> to set the document's <code>header_start</code>.
*  Sets the document's <code>doc_end</code> to be the <code>header_start</code> of the next <code>SumarioDoc</code> in the list (or the end of all entities if it's the last document).

4. <code>assign_grouped_to_docs</code>
*  **Goal**: Slice and Align Data.
*  Iterates through all <code>SumarioDoc</code> objects after their boundaries are computed.
*  <code>attach_from_grouped_slice</code>: Slices the raw <code>grouped</code> entities using the calculated <code>header_start</code> and <code>doc_end</code>, storing the resulting entities directly in <code>doc.entities</code>.
*  <code>align_orgs_and_doc_names_from_entities</code>: Matches the expected header texts (from the <code>grouped_blocks</code> input) to the actual entities found in the slice (<code>doc.entities</code>). This calculates the precise positional anchors (<code>org_positions</code>, <code>doc_name_positions</code>) within the document's boundaries.

5. <code>build_docs_by_org</code>**(The Segmentation Core)**
*  **Goal**: Finalize Segmentation and Output.
*  This is the most complex function, responsible for **sub-segmenting** the document's contents into one or more final <code>DocEntry</code> objects.
*  **Segmentation Logic**: It uses the calculated <code>org_positions</code> and <code>doc_name_positions</code> as anchors.
    *  If <code>doc_name_positions</code> exist, each one defines a sub-document. The segment runs from the preceding ORG position (or the previous doc name) up to the next organizational change or document name.
    *  If **no** <code>doc_name_positions</code> exist, the document is segmented purely by the change in <code>org_positions</code>.
*  It then concatenates the text of all entities in each segment to create the final <code>segment_text</code> for each resulting <code>DocEntry</code>.


### serie_III

This module is responsible for matching document summaries/headers to their body text and then performing a **secondary segmentation** to extract individual sections within the body segment.

#### Core Data Structures

<table>
  <thead>
    <tr>
      <th>Class/Type</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>SumarioDoc</code></td>
      <td><bold>Document Anchor</bold>: Represents a single document candidate, initialized with header lists (ORG, DOC_NAME) and later holds the sliced body content.</td>
    </tr>
     <tr>
      <td><code>ExportDoc</code></td>
      <td><bold>Final Output</bold>: The desired flat structure containing the definitive header texts, organization names, document title, and the concatenated document body.</td>
    </tr>
    <tr>
      <td><code>Section</code></td>
      <td><bold>Internal Structure</bold>: Used to group multiple sub-documents under a single primary title (like a chapter).</td>
    </tr>
    <tr>
      <td><code>Body_dict</code></td>
      <td><bold>Input Data</bold>: The dictionary containing all entity content from the main document body, indexed by position.</td>
    </tr>
  </tbody>
</table>

#### Key Steps and Logic
The workflow processes the documents in three major phases: Anchoring, Slicing, and Sectioning.

1.  **Anchoring Documents** (<code>assign_doc_anchors</code>)

The goal is to determine where the content of each <code>SumarioDoc</code> actually begins in the <code>body_dict</code>.

*  **Process**: It compares the authoritative **Organization Names** (<code>org_texts</code> and <code>header_texts</code>) stored in each SumarioDoc against the list of **Organization Entities** found in the <code>body_dict</code> (<code>org_entries</code>).
*  **Matching**: It uses the <code>_is_close_match</code> helper to find the first organizational entity in the body that closely matches the document's header organization.
*  **Result**: The position of this matching entity becomes the document's <code>anchor_idx</code>. Crucially, the search for the next document starts **after** the previous document's anchor to prevent overlap.

2. **Slicing the Body** (<code>attach_body_segments</code>)

Once the anchors are set, the content is sliced based on these start points.

*  **Process**: It uses the <code>anchor_idx</code> of the current document as the **start** of its body content. The **end** of the current document's body is set by the <code>anchor_idx</code> of the next document.
*  **Result**: Each <code>SumarioDoc</code> receives its specific slice of the main entity dictionary, stored in <code>body_entries</code> and <code>body_positions</code>.

3. **Sectioning and Alignment** (<code>compute_doc_positions</code> and <code>build_sections</code>)

This phase breaks the single document body into smaller, title-based sections.

A. **Title Alignment** (<code>compute_doc_positions</code>)
*  It compares the document titles/paragraphs expected from the header data (<code>doc_name</code>, <code>doc_paragraph</code>) against the actual **DOC_NAME_LABEL** entities found within the <code>body_entries</code>.
*  This determines the <code>doc_name_positions</code> and <code>doc_paragraph_positions</code>, which serve as the anchors for the sections within the document body.

B. **Section Building** (<code>build_sections</code>)
*  It iterates over the aligned <code>doc_name_positions</code> (the main titles). Each title defines the start of a new <code>Section</code>.
*  The content of this section is then sub-segmented by the <code>doc_paragraph_positions</code>. This means that the main document body is split into smaller **sub-documents** (list of dictionaries under <code>Section.docs</code>), each starting at a paragraph or sub-title position.

4. **Final Export** (<code>to_flat_docs</code>)
*  The function iterates through the newly created <code>sections</code> and their embedded sub-documents.
*  It concatenates the text of all entities belonging to a single sub-document to create the final, clean <code>body</code> string.
*  It compiles the header information, the section title (as the document name), and the body into the final flat <code>ExportDoc</code> format.


