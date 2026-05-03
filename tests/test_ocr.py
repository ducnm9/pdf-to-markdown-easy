"""
Property-based tests for the OCR Client module (src/ocr.py).

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs.

Properties covered:
  5 - OCR request formation
  6 - OCR output saving
  7 - OCR resume skips existing files
  8 - Retry attempts match configuration
"""

import asyncio
import base64
import itertools
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.config import AppConfig
from src.ocr import OcrError, _ocr_single_page, ocr_pages


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# PDF names: filesystem-safe alphanumeric with underscores/hyphens
_pdf_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=32,
).filter(lambda s: s[0].isalnum() and s[-1].isalnum())

# Page numbers: 1 to 999
_page_number = st.integers(min_value=1, max_value=999)

# Prompt text: arbitrary non-empty printable text
_prompt_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po", "Pd")),
    min_size=1,
    max_size=200,
)

# Response content: arbitrary text (what the LLM returns as Markdown)
_response_content = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po", "Pd")),
    min_size=0,
    max_size=500,
)

# Image data: arbitrary bytes (simulating PNG file content)
_image_data = st.binary(min_size=1, max_size=256)

# Model names: non-empty alphanumeric strings
_model_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.",
    min_size=1,
    max_size=64,
)

# Base URLs: simple http URLs
_base_url = st.just("http://localhost:1234")

# max_retries: 0 to 10 as specified in the property
_max_retries = st.integers(min_value=0, max_value=10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_example_counter = itertools.count()


def _make_config(
    model: str = "test-model",
    base_url: str = "http://localhost:1234",
    max_retries: int = 3,
    max_concurrency: int = 1,
    api_key: str = "",
) -> AppConfig:
    """Build an AppConfig for testing."""
    return AppConfig(
        llm_base_url=base_url,
        llm_api_key=api_key,
        llm_model=model,
        max_concurrency=max_concurrency,
        max_retries=max_retries,
        smart_merge=False,
        image_dpi=300,
    )


def _make_success_response(content: str) -> MagicMock:
    """Build a mock httpx.Response that returns a successful OCR result."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return response


def _make_error_response(status_code: int = 500) -> MagicMock:
    """Build a mock httpx.Response that returns an HTTP error."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.request = MagicMock()
    return response


# ---------------------------------------------------------------------------
# Property 5: OCR request formation
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 5: OCR request formation
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    image_data=_image_data,
    prompt=_prompt_text,
    model=_model_name,
)
def test_ocr_request_formation(
    tmp_path: Path,
    image_data: bytes,
    prompt: str,
    model: str,
):
    """
    **Validates: Requirements 3.1, 3.2**

    For any image data and prompt text, the OCR client constructs an API
    request where:
    - The messages array contains the prompt text
    - The messages array contains a base64-encoded data URI of the image
    - The model field matches the configured LLM_MODEL
    - The endpoint targets /v1/chat/completions
    """
    example_id = next(_example_counter)
    run_dir = tmp_path / f"run_{example_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write fake image file
    image_path = run_dir / "page_001.png"
    image_path.write_bytes(image_data)

    output_path = run_dir / "page_001.md"
    config = _make_config(model=model)

    captured_requests: list[dict] = []

    async def fake_post(url: str, json: dict, headers: dict):
        captured_requests.append({"url": url, "body": json, "headers": headers})
        return _make_success_response("# OCR Result")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = fake_post
    semaphore = asyncio.Semaphore(1)

    asyncio.run(
        _ocr_single_page(
            image_path=image_path,
            output_path=output_path,
            config=config,
            prompt_text=prompt,
            semaphore=semaphore,
            client=mock_client,
        )
    )

    assert len(captured_requests) == 1, "Expected exactly one API request"
    req = captured_requests[0]

    # Endpoint must target /v1/chat/completions
    assert req["url"].endswith("/v1/chat/completions"), (
        f"Expected URL ending with /v1/chat/completions, got: {req['url']}"
    )

    body = req["body"]

    # Model field must match configured LLM_MODEL
    assert body["model"] == model, (
        f"Expected model={model!r}, got {body['model']!r}"
    )

    # Messages array must be present
    messages = body["messages"]
    assert len(messages) >= 1, "Expected at least one message"

    # Find the user message content parts
    user_message = messages[0]
    assert user_message["role"] == "user"
    content_parts = user_message["content"]
    assert isinstance(content_parts, list), "Content must be a list of parts"

    # Extract text and image_url parts
    text_parts = [p for p in content_parts if p.get("type") == "text"]
    image_parts = [p for p in content_parts if p.get("type") == "image_url"]

    # Prompt text must be present
    assert any(p["text"] == prompt for p in text_parts), (
        f"Prompt text {prompt!r} not found in text parts: {text_parts}"
    )

    # Base64 data URI must be present and correct
    assert len(image_parts) >= 1, "Expected at least one image_url part"
    image_url = image_parts[0]["image_url"]["url"]
    expected_b64 = base64.b64encode(image_data).decode("ascii")
    expected_uri = f"data:image/png;base64,{expected_b64}"
    assert image_url == expected_uri, (
        f"Expected data URI with correct base64 encoding"
    )


# ---------------------------------------------------------------------------
# Property 6: OCR output saving
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 6: OCR output saving
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    pdf_name=_pdf_name,
    page_num=_page_number,
    response_content=_response_content,
)
def test_ocr_output_saving(
    tmp_path: Path,
    pdf_name: str,
    page_num: int,
    response_content: str,
):
    """
    **Validates: Requirement 3.3**

    For any PDF name, page number, and LLM response content, the OCR client
    saves the response content to markdowns/{pdf_name}/page_NNN.md where NNN
    matches the page number's zero-padded format.
    """
    example_id = next(_example_counter)
    run_dir = tmp_path / f"run_{example_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create a fake image file for the page
    page_stem = f"page_{page_num:03d}"
    image_path = run_dir / f"{page_stem}.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header

    # Expected output path: markdowns/{pdf_name}/page_NNN.md
    output_dir = run_dir / "markdowns" / pdf_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{page_stem}.md"

    config = _make_config()

    async def fake_post(url: str, json: dict, headers: dict):
        return _make_success_response(response_content)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = fake_post
    semaphore = asyncio.Semaphore(1)

    result = asyncio.run(
        _ocr_single_page(
            image_path=image_path,
            output_path=output_path,
            config=config,
            prompt_text="Extract text",
            semaphore=semaphore,
            client=mock_client,
        )
    )

    # The returned path must match the expected output path
    assert result == output_path, (
        f"Expected result path {output_path}, got {result}"
    )

    # The file must exist at markdowns/{pdf_name}/page_NNN.md
    assert output_path.exists(), (
        f"Expected output file to exist at {output_path}"
    )

    # The file must contain exactly the response content
    saved_content = output_path.read_text(encoding="utf-8")
    assert saved_content == response_content, (
        f"Expected saved content {response_content!r}, got {saved_content!r}"
    )

    # Verify the filename follows page_NNN.md pattern
    assert output_path.name == f"page_{page_num:03d}.md", (
        f"Expected filename page_{page_num:03d}.md, got {output_path.name}"
    )


# ---------------------------------------------------------------------------
# Property 7: OCR resume skips existing files
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 7: OCR resume skips existing files
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    page_count=st.integers(min_value=1, max_value=20),
    existing_page_indices=st.data(),
)
def test_ocr_resume_skips_existing_files(
    tmp_path: Path,
    page_count: int,
    existing_page_indices: st.DataObject,
):
    """
    **Validates: Requirement 3.4**

    For any set of page image paths and any subset of those pages that
    already have corresponding Markdown files on disk, the OCR client only
    sends API requests for pages whose output .md files do not yet exist.
    """
    existing_indices = existing_page_indices.draw(
        st.frozensets(
            st.integers(min_value=0, max_value=page_count - 1),
            max_size=page_count,
        )
    )

    example_id = next(_example_counter)
    run_dir = tmp_path / f"run_{example_id}"

    images_dir = run_dir / "images" / "test_pdf"
    images_dir.mkdir(parents=True, exist_ok=True)
    output_dir = run_dir / "markdowns" / "test_pdf"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create fake image files for all pages
    image_paths = []
    for i in range(page_count):
        page_num = i + 1
        img_path = images_dir / f"page_{page_num:03d}.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        image_paths.append(img_path)

    # Pre-create .md files for "existing" pages
    for idx in existing_indices:
        page_num = idx + 1
        md_path = output_dir / f"page_{page_num:03d}.md"
        md_path.write_text("# Existing content", encoding="utf-8")

    # Track which pages triggered API calls
    api_call_count = 0

    async def fake_post(url: str, json: dict, headers: dict):
        nonlocal api_call_count
        api_call_count += 1
        return _make_success_response("# New OCR content")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    config = _make_config(max_concurrency=1)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result_paths = asyncio.run(
            ocr_pages(
                image_paths=image_paths,
                output_dir=output_dir,
                config=config,
                prompt_text="Extract text",
            )
        )

    # API should only be called for pages that did NOT already have .md files
    expected_api_calls = page_count - len(existing_indices)
    assert api_call_count == expected_api_calls, (
        f"Expected {expected_api_calls} API calls (skipping {len(existing_indices)} "
        f"existing pages), but got {api_call_count}"
    )

    # All page paths should be returned (existing + newly created)
    assert len(result_paths) == page_count


# ---------------------------------------------------------------------------
# Property 8: Retry attempts match configuration
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 8: Retry attempts match configuration
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(max_retries=_max_retries)
def test_retry_attempts_match_configuration(
    tmp_path: Path,
    max_retries: int,
):
    """
    **Validates: Requirement 3.7**

    For any max_retries value (0 to 10), when the LLM API consistently
    returns errors, the OCR client makes exactly max_retries + 1 total
    attempts (1 initial + max_retries retries) before raising OcrError.
    """
    example_id = next(_example_counter)
    run_dir = tmp_path / f"run_{example_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    image_path = run_dir / "page_001.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    output_path = run_dir / "page_001.md"

    config = _make_config(max_retries=max_retries)

    attempt_count = 0

    async def always_fail_post(url: str, json: dict, headers: dict):
        nonlocal attempt_count
        attempt_count += 1
        # Return an HTTP 500 error response
        error_response = _make_error_response(500)
        raise httpx.HTTPStatusError(
            "HTTP 500",
            request=MagicMock(),
            response=error_response,
        )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = always_fail_post
    semaphore = asyncio.Semaphore(1)

    # Patch asyncio.sleep to avoid actual delays during testing
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(OcrError):
            asyncio.run(
                _ocr_single_page(
                    image_path=image_path,
                    output_path=output_path,
                    config=config,
                    prompt_text="Extract text",
                    semaphore=semaphore,
                    client=mock_client,
                )
            )

    # Must make exactly max_retries + 1 total attempts
    expected_attempts = max_retries + 1
    assert attempt_count == expected_attempts, (
        f"Expected {expected_attempts} total attempts for max_retries={max_retries}, "
        f"but got {attempt_count}"
    )


# ===========================================================================
# Unit Tests for OCR Client
# ===========================================================================

# ---------------------------------------------------------------------------
# Unit Test 1: Sequential processing when MAX_CONCURRENCY=1
# ---------------------------------------------------------------------------

def test_sequential_processing_with_concurrency_1(tmp_path: Path):
    """
    Test that with MAX_CONCURRENCY=1, pages are processed one at a time.

    Verifies that the semaphore limits to 1 concurrent request by checking
    that pages are processed sequentially (no overlap in active requests).
    """
    images_dir = tmp_path / "images" / "test_pdf"
    images_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "markdowns" / "test_pdf"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create 3 fake image files
    image_paths = []
    for i in range(1, 4):
        img_path = images_dir / f"page_{i:03d}.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        image_paths.append(img_path)

    # Track concurrent active requests
    active_requests = 0
    max_concurrent_seen = 0
    call_order: list[int] = []

    async def fake_post(url: str, json: dict, headers: dict):
        nonlocal active_requests, max_concurrent_seen
        active_requests += 1
        max_concurrent_seen = max(max_concurrent_seen, active_requests)
        # Extract page number from the request to track call order
        image_url = json["messages"][0]["content"][1]["image_url"]["url"]
        call_order.append(active_requests)
        # Simulate some async work
        await asyncio.sleep(0)
        active_requests -= 1
        return _make_success_response("# Page content")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    config = _make_config(max_concurrency=1)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result_paths = asyncio.run(
            ocr_pages(
                image_paths=image_paths,
                output_dir=output_dir,
                config=config,
                prompt_text="Extract text",
            )
        )

    # With concurrency=1, max concurrent requests should never exceed 1
    assert max_concurrent_seen <= 1, (
        f"Expected max 1 concurrent request with MAX_CONCURRENCY=1, "
        f"but saw {max_concurrent_seen} concurrent requests"
    )

    # All 3 pages should be processed
    assert len(result_paths) == 3
    for path in result_paths:
        assert path.exists()


# ---------------------------------------------------------------------------
# Unit Test 2: Exhausted retries logs error and raises OcrError
# ---------------------------------------------------------------------------

def test_exhausted_retries_logs_error_and_raises(tmp_path: Path):
    """
    Test that when all retries are exhausted, the error is logged and
    OcrError is raised. The caller (main.py) handles continuing with
    remaining pages.
    """
    image_path = tmp_path / "page_001.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    output_path = tmp_path / "page_001.md"

    config = _make_config(max_retries=2)

    attempt_count = 0

    async def always_fail_post(url: str, json: dict, headers: dict):
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.HTTPStatusError(
            "HTTP 500",
            request=MagicMock(),
            response=_make_error_response(500),
        )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = always_fail_post
    semaphore = asyncio.Semaphore(1)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("src.ocr.logger") as mock_logger:
            with pytest.raises(OcrError) as exc_info:
                asyncio.run(
                    _ocr_single_page(
                        image_path=image_path,
                        output_path=output_path,
                        config=config,
                        prompt_text="Extract text",
                        semaphore=semaphore,
                        client=mock_client,
                    )
                )

    # Should have made max_retries + 1 = 3 total attempts
    assert attempt_count == 3, (
        f"Expected 3 total attempts (1 initial + 2 retries), got {attempt_count}"
    )

    # OcrError message should identify the failed page
    assert "page_001.png" in str(exc_info.value), (
        f"Expected OcrError to mention the failed page, got: {exc_info.value}"
    )

    # Error should have been logged
    mock_logger.error.assert_called_once()
    error_call_args = str(mock_logger.error.call_args)
    assert "page_001.png" in error_call_args, (
        "Expected logger.error to be called with the page filename"
    )

    # Output file should NOT have been created
    assert not output_path.exists(), (
        "Expected no output file to be created when all retries are exhausted"
    )


# ---------------------------------------------------------------------------
# Unit Test 3: Correct base64 encoding and request body structure
# ---------------------------------------------------------------------------

def test_correct_base64_encoding_and_request_body(tmp_path: Path):
    """
    Test that the request body has the correct structure with a properly
    base64-encoded image and all required fields.
    """
    import base64 as b64_module

    # Write a known byte sequence as the "image"
    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    image_path = tmp_path / "page_001.png"
    image_path.write_bytes(image_bytes)
    output_path = tmp_path / "page_001.md"

    prompt = "Please extract all text from this image as Markdown."
    model = "my-vision-model"
    config = _make_config(model=model, api_key="secret-key")

    captured: dict = {}

    async def capture_post(url: str, json: dict, headers: dict):
        captured["url"] = url
        captured["body"] = json
        captured["headers"] = headers
        return _make_success_response("# Extracted text")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = capture_post
    semaphore = asyncio.Semaphore(1)

    asyncio.run(
        _ocr_single_page(
            image_path=image_path,
            output_path=output_path,
            config=config,
            prompt_text=prompt,
            semaphore=semaphore,
            client=mock_client,
        )
    )

    # Verify URL targets /v1/chat/completions
    assert captured["url"].endswith("/v1/chat/completions"), (
        f"Expected URL ending with /v1/chat/completions, got: {captured['url']}"
    )

    body = captured["body"]

    # Verify model field
    assert body["model"] == model, (
        f"Expected model={model!r}, got {body['model']!r}"
    )

    # Verify messages structure
    assert "messages" in body
    messages = body["messages"]
    assert len(messages) == 1
    message = messages[0]
    assert message["role"] == "user"

    content_parts = message["content"]
    assert isinstance(content_parts, list)

    # Find text and image parts
    text_parts = [p for p in content_parts if p.get("type") == "text"]
    image_parts = [p for p in content_parts if p.get("type") == "image_url"]

    assert len(text_parts) == 1, f"Expected 1 text part, got {len(text_parts)}"
    assert text_parts[0]["text"] == prompt

    assert len(image_parts) == 1, f"Expected 1 image_url part, got {len(image_parts)}"

    # Verify base64 encoding is correct
    expected_b64 = b64_module.b64encode(image_bytes).decode("ascii")
    expected_uri = f"data:image/png;base64,{expected_b64}"
    actual_uri = image_parts[0]["image_url"]["url"]
    assert actual_uri == expected_uri, (
        f"Expected data URI with correct base64 encoding.\n"
        f"Expected: {expected_uri[:80]}...\n"
        f"Got:      {actual_uri[:80]}..."
    )

    # Verify Authorization header is set when api_key is provided
    assert "Authorization" in captured["headers"], (
        "Expected Authorization header when api_key is set"
    )
    assert captured["headers"]["Authorization"] == "Bearer secret-key"


# ---------------------------------------------------------------------------
# Unit Test 4: Resume skips pages with existing Markdown files
# ---------------------------------------------------------------------------

def test_resume_skips_pages_with_existing_md_files(tmp_path: Path):
    """
    Test that pages with existing .md files are not sent to the API.
    Verifies resume functionality: only missing pages trigger API calls.
    """
    images_dir = tmp_path / "images" / "my_doc"
    images_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "markdowns" / "my_doc"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create 4 fake image files
    image_paths = []
    for i in range(1, 5):
        img_path = images_dir / f"page_{i:03d}.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        image_paths.append(img_path)

    # Pre-create .md files for pages 1 and 3 (simulating a previous run)
    existing_content_p1 = "# Page 1 existing content"
    existing_content_p3 = "# Page 3 existing content"
    (output_dir / "page_001.md").write_text(existing_content_p1, encoding="utf-8")
    (output_dir / "page_003.md").write_text(existing_content_p3, encoding="utf-8")

    # Track which pages triggered API calls
    api_called_for: list[str] = []

    async def fake_post(url: str, json: dict, headers: dict):
        # Extract the image data URI to identify which page was called
        image_url = json["messages"][0]["content"][1]["image_url"]["url"]
        api_called_for.append(image_url[:30])  # just a marker
        return _make_success_response("# New OCR content")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    config = _make_config(max_concurrency=1)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result_paths = asyncio.run(
            ocr_pages(
                image_paths=image_paths,
                output_dir=output_dir,
                config=config,
                prompt_text="Extract text",
            )
        )

    # Only pages 2 and 4 should have triggered API calls (pages 1 and 3 existed)
    assert len(api_called_for) == 2, (
        f"Expected 2 API calls (for pages 2 and 4), got {len(api_called_for)}"
    )

    # All 4 result paths should be returned
    assert len(result_paths) == 4

    # Existing pages should retain their original content (not overwritten)
    assert (output_dir / "page_001.md").read_text(encoding="utf-8") == existing_content_p1, (
        "Page 1 existing content should not have been overwritten"
    )
    assert (output_dir / "page_003.md").read_text(encoding="utf-8") == existing_content_p3, (
        "Page 3 existing content should not have been overwritten"
    )

    # Newly processed pages should have the new content
    assert (output_dir / "page_002.md").read_text(encoding="utf-8") == "# New OCR content"
    assert (output_dir / "page_004.md").read_text(encoding="utf-8") == "# New OCR content"
