# Implementation Plan: OCR PDF to Markdown

## Overview

This plan implements a Python CLI tool that converts PDF files to Markdown using LLM-based OCR. The implementation follows a bottom-up approach: project scaffolding and configuration first, then core modules (PDF converter, OCR client, merger), then CLI orchestration that wires everything together. Each task builds on previous ones, and testing is integrated alongside implementation.

## Tasks

- [x] 1. Set up project structure, dependencies, and configuration module
  - [x] 1.1 Create project scaffolding and dependency files
    - Create `src/__init__.py` (empty, makes `src` a Python package)
    - Create `src/__main__.py` with `from src.main import main; import asyncio, sys; sys.exit(asyncio.run(main()))` to enable `python -m src`
    - Create `requirements.txt` with pinned versions: `pdf2image`, `httpx`, `python-dotenv`, `Pillow`
    - Create `.env.example` documenting all configuration variables: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `MAX_CONCURRENCY`, `MAX_RETRIES`, `SMART_MERGE`, `IMAGE_DPI`
    - Create `prompt.txt` with default OCR instructions specifying Vietnamese text recognition, Markdown output format, and formatting preservation
    - Create `merge_prompt.txt` with default instructions for intelligent Markdown merging and cleanup
    - Create `tests/__init__.py` and `tests/conftest.py` with shared fixtures (temp dirs, mock configs)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 1.2 Implement the Config Loader module (`src/config.py`)
    - Define `ConfigError` exception class
    - Define `AppConfig` frozen dataclass with fields: `llm_base_url`, `llm_api_key`, `llm_model`, `max_concurrency`, `max_retries`, `smart_merge`, `image_dpi`
    - Implement `load_config(env_path=".env")` function that reads `.env` via `python-dotenv`, validates required fields (`LLM_BASE_URL`, `LLM_MODEL`), applies defaults (`MAX_CONCURRENCY=1`, `MAX_RETRIES=3`, `SMART_MERGE=False`, `IMAGE_DPI=300`), validates integer fields and boolean parsing
    - Raise `ConfigError` with descriptive message listing all missing required variables
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x] 1.3 Write property tests for Config Loader
    - **Property 1: Configuration round-trip** — For any valid set of config values, writing to `.env` and loading via `load_config` produces an `AppConfig` with matching fields
    - **Validates: Requirement 1.2**
    - **Property 2: Missing required config raises error** — For any `.env` missing `LLM_BASE_URL`, `LLM_MODEL`, or both, `load_config` raises `ConfigError` naming each missing variable
    - **Validates: Requirement 1.7**

  - [x] 1.4 Write unit tests for Config Loader
    - Test loading all values from a complete `.env` file
    - Test default value for `MAX_CONCURRENCY=1` when not specified
    - Test default value for `MAX_RETRIES=3` when not specified
    - Test default value for `SMART_MERGE=False` when not specified
    - Test default value for `IMAGE_DPI=300` when not specified
    - Test `ConfigError` raised for missing `LLM_BASE_URL`
    - Test `ConfigError` raised for missing `LLM_MODEL`
    - Test invalid integer values raise `ConfigError`
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6, 1.7_

- [x] 2. Checkpoint - Ensure config module tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement PDF to Image Conversion module
  - [x] 3.1 Implement the PDF Converter module (`src/pdf_to_images.py`)
    - Define `PdfConversionError` exception class
    - Implement `convert_pdf_to_images(pdf_path, output_dir, dpi=300)` function
    - Create `output_dir` with `Path.mkdir(parents=True, exist_ok=True)`
    - Use `pdf2image.convert_from_path` to convert PDF pages to PIL Image objects
    - Save images as `page_001.png`, `page_002.png`, etc. with zero-padded 3-digit page numbers
    - Implement resume support: check if `page_NNN.png` already exists before converting, skip existing pages
    - Return sorted list of all page image paths
    - Catch corrupted/unreadable PDF errors and raise `PdfConversionError`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.2 Write property tests for PDF Converter
    - **Property 3: Image output naming convention** — For any PDF name and page count (1–999), generated paths follow `images/{pdf_name}/page_NNN.png` pattern
    - **Validates: Requirement 2.2**
    - **Property 4: Image conversion resume skips existing files** — For any subset of pages already on disk, the converter only processes pages whose output files do not exist
    - **Validates: Requirement 2.3**

  - [x] 3.3 Write unit tests for PDF Converter
    - Test output directory is created when it doesn't exist
    - Test corrupted PDF logs error and raises `PdfConversionError`
    - Test resume skips pages that already have PNG files on disk
    - Test correct page count and file naming for a multi-page PDF
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 4. Implement OCR Client module
  - [x] 4.1 Implement the OCR Client module (`src/ocr.py`)
    - Define `OcrError` exception class
    - Implement `ocr_pages(image_paths, output_dir, config, prompt_text)` async function
    - Create `output_dir` with `Path.mkdir(parents=True, exist_ok=True)`
    - Implement resume support: skip pages where `page_NNN.md` already exists
    - Create `asyncio.Semaphore(config.max_concurrency)` for concurrency control
    - Create single `httpx.AsyncClient` with 120s timeout for connection pooling
    - Launch all page OCR tasks with `asyncio.gather(*tasks, return_exceptions=True)`
    - Implement `_ocr_single_page` helper: base64-encode image, construct OpenAI-compatible request body with model, prompt text, and image data URI, POST to `/v1/chat/completions`, extract `choices[0].message.content`, save to `page_NNN.md`
    - Implement retry with exponential backoff: on HTTP errors (status >= 400), `httpx.TimeoutException`, or `httpx.RequestError`, wait `2^attempt` seconds, retry up to `config.max_retries` times
    - After all retries exhausted, log error identifying the failed page and raise `OcrError`
    - Include `Authorization: Bearer {api_key}` header when `llm_api_key` is non-empty
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [x] 4.2 Write property tests for OCR Client
    - **Property 5: OCR request formation** — For any image data and prompt text, the request contains the prompt, base64 data URI, correct model, and targets `/v1/chat/completions`
    - **Validates: Requirements 3.1, 3.2**
    - **Property 6: OCR output saving** — For any PDF name, page number, and response content, the output is saved to `markdowns/{pdf_name}/page_NNN.md`
    - **Validates: Requirement 3.3**
    - **Property 7: OCR resume skips existing files** — For any subset of pages with existing `.md` files, the client only sends API requests for missing pages
    - **Validates: Requirement 3.4**
    - **Property 8: Retry attempts match configuration** — For any `max_retries` (0–10), the client makes exactly `max_retries + 1` total attempts before raising `OcrError`
    - **Validates: Requirement 3.7**

  - [x] 4.3 Write unit tests for OCR Client
    - Test sequential processing when `MAX_CONCURRENCY=1`
    - Test that exhausted retries logs error and continues with remaining pages
    - Test correct base64 encoding and request body structure
    - Test resume skips pages with existing Markdown files
    - _Requirements: 3.1, 3.4, 3.6, 3.7, 3.8_

- [x] 5. Checkpoint - Ensure OCR module tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Markdown Merger module
  - [x] 6.1 Implement the Merger module (`src/merger.py`)
    - Implement `merge_pages(markdown_paths, output_path, config, merge_prompt_text=None)` async function
    - Implement `_simple_merge(markdown_paths)`: read each file, concatenate with `<!-- Page X -->` separators, order by numeric page number extracted from filename
    - Implement `_smart_merge(content, config, merge_prompt_text)`: send concatenated content to LLM API using `merge_prompt.txt` content as prompt, return LLM-processed result
    - When `config.smart_merge` is `True` and `merge_prompt_text` is provided, use smart merge; on LLM failure, fall back to simple merge with warning log
    - When `merge_prompt_text` is `None` and `config.smart_merge` is `True`, log warning and fall back to simple merge
    - Write merged output to `output_path` (e.g., `markdowns/{pdf_name}/final.md`)
    - Skip merge if no page Markdown files are found, log warning
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 6.2 Write property test for Merger
    - **Property 9: Simple merge preserves content and ordering** — For any set of page Markdown files with arbitrary content, the simple merge output contains all page contents in ascending page order with `<!-- Page X -->` separators
    - **Validates: Requirements 4.2, 4.5**

  - [x] 6.3 Write unit tests for Merger
    - Test merged output is written to the correct path
    - Test smart merge calls LLM API with merge prompt content
    - Test missing `merge_prompt.txt` with `SMART_MERGE=true` falls back to simple merge
    - Test no page files found logs warning and skips merge
    - _Requirements: 4.1, 4.3, 4.4_

- [x] 7. Implement CLI orchestration and wire all modules together
  - [x] 7.1 Implement the CLI entry point (`src/main.py`)
    - Implement `_discover_pdfs(inputs_dir)`: return sorted list of `.pdf` files in the directory
    - Implement `main()` async function that orchestrates the full pipeline:
      1. Configure logging to stderr at INFO level with format `%(asctime)s - %(levelname)s - %(message)s`
      2. Call `load_config()` and handle `ConfigError` (log error, return exit code 1)
      3. Load `prompt.txt` content (log error and exit if missing)
      4. Optionally load `merge_prompt.txt` content (None if missing)
      5. Discover PDFs in `inputs/` directory; if directory missing or empty, log message and return exit code 0
      6. For each PDF, run the pipeline sequentially: `convert_pdf_to_images` → `ocr_pages` → `merge_pages`
      7. Wrap each PDF's processing in try/except to isolate errors — log error, mark as failed, continue with next PDF
      8. Log current file name, page number, and operation status at each step
      9. Return exit code 0 if all PDFs succeeded, 1 if any failed
    - Add `if __name__ == "__main__"` block: `sys.exit(asyncio.run(main()))`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1_

  - [x] 7.2 Write property test for PDF discovery
    - **Property 10: PDF discovery filters by extension** — For any directory with a mix of `.pdf` and non-`.pdf` files, the discovery function returns exactly the `.pdf` files
    - **Validates: Requirement 5.1**

  - [x] 7.3 Write unit tests for CLI orchestration
    - Test CLI processes all PDFs through the full pipeline
    - Test CLI logs file name, page number, and status for each step
    - Test exit code 0 when all PDFs succeed
    - Test exit code 1 when one or more PDFs fail
    - Test empty or missing `inputs/` directory logs message and exits with code 0
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 8. Smoke tests for project structure
  - [x] 8.1 Write smoke tests (`tests/test_smoke.py`)
    - Test `src.main` and `src.config` are importable
    - Test `.env.example` exists and contains all expected variable names
    - Test `prompt.txt` exists and contains OCR instructions
    - Test `merge_prompt.txt` exists
    - Test `requirements.txt` exists and has pinned versions (contains `==`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.5_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major module
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases using pytest
- All LLM API calls should be mocked in tests — no real API calls
- Use `tmp_path` pytest fixture for isolated file system operations
- Use `monkeypatch` to control environment variables and `.env` file content
