
uvicorn api:app --reload --port 8000


.\.venv\Scripts\activate

python -m pip install spacy==3.8.9 pymupdf==1.26.6 pymupdf4llm==0.2.2
python -m spacy download pt_core_news_lg

creating a new relation_extractor

-----------------------------------------------------------------------------------------------
# Main Title (H1) - Use only once
## Major Section (H2)
### Sub-section (H3)
#### Minor section (H4)
-----------------------------------------------------------------------------------------------
This is **bold text**.
This is *italic text*.
This is ~~crossed out~~.
-----------------------------------------------------------------------------------------------

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
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>ORG_LABEL</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>ORG_WITH_STAR_LABEL</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>DOC_NAME_LABEL</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>DOC_TEXT</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>PARAGRAPH</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>JUNK_LABEL</td>
      <td></td>
      <td></td>
    </tr>
    <tr>
      <td>SERIE_III</td>
      <td></td>
      <td></td>
    </tr>
  </tbody>
</table>

This modulo handles the classification of the text so we don't need to work with raw text, that way we don't need to worry about every time we make a comparation, division of the text, etc with the text. For a better classification, we created 2 spacy pipelines, one for the **Series (I, II, IV)** and another for the **Serie III**.

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






