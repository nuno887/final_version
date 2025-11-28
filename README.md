
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








