# Requirements Document

## Introduction

A Python CLI application that converts PDF files to Markdown using LLM-based OCR. The application processes PDF files from an `inputs/` directory, converts each page to an image, sends images to an OpenAI-compatible LLM API for OCR (optimized for Vietnamese text), and produces individual page Markdown files plus a merged final Markdown file. The tool supports both local LLM endpoints (LM Studio, Ollama) and cloud providers (DeepSeek, OpenAI) via a unified OpenAI-compatible API interface. All configuration is managed through a `.env` file.

## Glossary

- **CLI**: The command-line interface entry point (`python -m src.main` or `python src/main.py`) that orchestrates the full PDF-to-Markdown pipeline
- **Config_Loader**: The module (`config.py`) responsible for loading and validating configuration from the `.env` file using python-dotenv
- **PDF_Converter**: The module (`pdf_to_images.py`) responsible for converting PDF pages into PNG images using pdf2image
- **OCR_Client**: The module (`ocr.py`) responsible for sending base64-encoded images to an OpenAI-compatible LLM API and receiving Markdown text
- **Merger**: The module (`merger.py`) responsible for combining individual page Markdown files into a single final Markdown file
- **LLM_API**: An OpenAI-compatible API endpoint (`/v1/chat/completions`) that accepts vision requests with base64-encoded images
- **Simple_Merge**: A merge mode that concatenates page Markdown files with `<!-- Page X -->` HTML comment separators
- **Smart_Merge**: A merge mode that sends concatenated page content to the LLM_API using a merge prompt for intelligent cleanup and merging
- **Resume**: The ability to skip already-completed processing steps (image conversion or OCR) when re-running the pipeline on the same PDF

## Requirements

### Requirement 1: Configuration Loading

**User Story:** As a user, I want to configure the application through a `.env` file, so that I can easily switch between different LLM providers and adjust processing parameters without modifying code.

#### Acceptance Criteria

1. WHEN the CLI starts, THE Config_Loader SHALL read configuration values from the `.env` file in the project root directory using python-dotenv
2. WHEN the `.env` file defines LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, MAX_CONCURRENCY, MAX_RETRIES, SMART_MERGE, and IMAGE_DPI, THE Config_Loader SHALL load all defined values as application configuration
3. WHEN MAX_CONCURRENCY is not specified in the `.env` file, THE Config_Loader SHALL use a default value of 1
4. WHEN MAX_RETRIES is not specified in the `.env` file, THE Config_Loader SHALL use a default value of 3
5. WHEN SMART_MERGE is not specified in the `.env` file, THE Config_Loader SHALL use a default value of false
6. WHEN IMAGE_DPI is not specified in the `.env` file, THE Config_Loader SHALL use a default value of 300
7. IF LLM_BASE_URL or LLM_MODEL is missing from the `.env` file, THEN THE Config_Loader SHALL raise a configuration error with a descriptive message identifying the missing variable

### Requirement 2: PDF to Image Conversion

**User Story:** As a user, I want PDF pages to be converted to PNG images, so that each page can be individually processed by the LLM for OCR.

#### Acceptance Criteria

1. WHEN the CLI processes a PDF file, THE PDF_Converter SHALL convert each page of the PDF into a separate PNG image using pdf2image at the configured IMAGE_DPI resolution
2. WHEN the CLI processes a PDF file named `{pdf_name}.pdf`, THE PDF_Converter SHALL save images to the directory `images/{pdf_name}/` with filenames following the pattern `page_001.png`, `page_002.png`, etc.
3. WHEN the target image file already exists for a given page, THE PDF_Converter SHALL skip conversion for that page to support resume functionality
4. WHEN the `images/{pdf_name}/` directory does not exist, THE PDF_Converter SHALL create the directory before saving images
5. IF the PDF file is corrupted or unreadable, THEN THE PDF_Converter SHALL log an error message identifying the problematic file and skip processing of that file

### Requirement 3: LLM-Based OCR Processing

**User Story:** As a user, I want each page image to be sent to an LLM for OCR, so that the visual content is accurately converted to Markdown text, especially for Vietnamese documents.

#### Acceptance Criteria

1. WHEN a page image is ready for OCR, THE OCR_Client SHALL encode the image as base64 and send it to the LLM_API at the configured LLM_BASE_URL using the `/v1/chat/completions` endpoint with the configured LLM_MODEL
2. WHEN sending an OCR request, THE OCR_Client SHALL include the content of `prompt.txt` as the system or user prompt instructing the LLM to perform OCR with Vietnamese text support and Markdown output formatting
3. WHEN the LLM_API returns a successful response, THE OCR_Client SHALL save the extracted Markdown text to `markdowns/{pdf_name}/page_001.md`, `markdowns/{pdf_name}/page_002.md`, etc.
4. WHEN the target Markdown file already exists for a given page, THE OCR_Client SHALL skip OCR processing for that page to support resume functionality
5. WHEN MAX_CONCURRENCY is greater than 1, THE OCR_Client SHALL process up to MAX_CONCURRENCY pages concurrently using asyncio.Semaphore
6. WHEN MAX_CONCURRENCY is equal to 1, THE OCR_Client SHALL process pages sequentially
7. IF the LLM_API returns an error or the request times out, THEN THE OCR_Client SHALL retry the request up to MAX_RETRIES times with exponential backoff between attempts
8. IF all retry attempts for a page are exhausted, THEN THE OCR_Client SHALL log an error message identifying the failed page and continue processing remaining pages
9. THE OCR_Client SHALL use httpx as the async HTTP client for all LLM_API communication

### Requirement 4: Markdown Merging

**User Story:** As a user, I want all individual page Markdown files to be merged into a single final Markdown file, so that I have a complete document ready for use.

#### Acceptance Criteria

1. WHEN all pages of a PDF have been processed, THE Merger SHALL combine individual page Markdown files into a single file at `markdowns/{pdf_name}/final.md`
2. WHEN SMART_MERGE is set to false, THE Merger SHALL concatenate page Markdown files in page order with `<!-- Page X -->` HTML comment separators between pages (Simple_Merge mode)
3. WHEN SMART_MERGE is set to true, THE Merger SHALL send the concatenated page content to the LLM_API using the content of `merge_prompt.txt` as the prompt for intelligent cleanup and merging (Smart_Merge mode)
4. IF `merge_prompt.txt` does not exist and SMART_MERGE is set to true, THEN THE Merger SHALL fall back to Simple_Merge mode and log a warning message
5. WHEN performing Simple_Merge, THE Merger SHALL order pages by their numeric page number extracted from the filename

### Requirement 5: CLI Orchestration and Batch Processing

**User Story:** As a user, I want to run a single command to process all PDF files in the inputs directory, so that I can batch-convert multiple documents efficiently.

#### Acceptance Criteria

1. WHEN the user runs the CLI, THE CLI SHALL discover and process all `.pdf` files in the `inputs/` directory
2. WHEN processing multiple PDF files, THE CLI SHALL process each PDF file through the complete pipeline: image conversion, OCR, and merging
3. WHEN processing a PDF file, THE CLI SHALL log the current file name, current page number, and operation status (success or failure) for each step
4. WHEN all PDF files have been processed successfully, THE CLI SHALL exit with exit code 0
5. IF one or more PDF files fail during processing, THEN THE CLI SHALL exit with a non-zero exit code after attempting to process all remaining files
6. IF the `inputs/` directory does not exist or contains no PDF files, THEN THE CLI SHALL log an informative message and exit with exit code 0

### Requirement 6: Project Structure and Entry Points

**User Story:** As a user, I want a well-organized project with clear entry points, so that I can easily set up and run the application.

#### Acceptance Criteria

1. THE CLI SHALL be executable via `python -m src.main` or `python src/main.py`
2. THE CLI SHALL provide a `.env.example` file documenting all available configuration variables with example values
3. THE CLI SHALL provide a default `prompt.txt` file containing OCR instructions specifying Vietnamese text recognition, Markdown output format, and formatting preservation
4. THE CLI SHALL provide a default `merge_prompt.txt` file containing instructions for intelligent Markdown merging and cleanup

### Requirement 7: Dependency Management

**User Story:** As a developer, I want clearly defined dependencies, so that I can set up the project environment reliably.

#### Acceptance Criteria

1. THE CLI SHALL declare pdf2image as a dependency for PDF-to-image conversion
2. THE CLI SHALL declare httpx as a dependency for async HTTP communication with the LLM_API
3. THE CLI SHALL declare python-dotenv as a dependency for `.env` file loading
4. THE CLI SHALL declare Pillow as a dependency for image handling
5. THE CLI SHALL include a `requirements.txt` file listing all dependencies with pinned versions
