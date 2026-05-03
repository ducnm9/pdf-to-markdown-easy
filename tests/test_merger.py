"""
Property-based tests for the Merger module (src/merger.py).

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs.

Properties covered:
  9 - Simple merge preserves content and ordering
"""

import itertools
import re
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.merger import _simple_merge


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Page numbers: 1 to 999 (arbitrary page numbers as specified)
_page_number = st.integers(min_value=1, max_value=999)

# Page content: arbitrary text (what a page Markdown file might contain)
# Note: "Cc" (control characters) is intentionally excluded to avoid \r
# (carriage return), which macOS normalises away on read-back, causing
# spurious test failures.  \n and \t are added explicitly via
# whitelist_characters instead.
_page_content = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po", "Pd"),
        whitelist_characters="\n\t #*`_[]()!",
    ),
    min_size=0,
    max_size=500,
)

# A single page: (page_number, content)
_page = st.tuples(_page_number, _page_content)

# A non-empty list of pages with distinct page numbers
_pages = st.lists(_page, min_size=1, max_size=20).map(
    lambda pages: list({num: content for num, content in pages}.items())
)


# ---------------------------------------------------------------------------
# Property 9: Simple merge preserves content and ordering
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 9: Simple merge preserves content and ordering
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(pages=_pages)
def test_simple_merge_preserves_content_and_ordering(
    tmp_path: Path,
    pages: list[tuple[int, str]],
):
    """
    **Validates: Requirements 4.2, 4.5**

    For any set of page Markdown files with arbitrary content and arbitrary
    page numbers, the simple merge output contains all page contents in
    ascending numeric page order, separated by <!-- Page X --> HTML comments
    where X matches each page's number.
    """
    example_id = next(itertools.count())
    run_dir = tmp_path / f"run_{id(pages)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write each page's content to a file named page_NNN.md
    markdown_paths: list[Path] = []
    for page_num, content in pages:
        page_path = run_dir / f"page_{page_num:03d}.md"
        page_path.write_text(content, encoding="utf-8")
        markdown_paths.append(page_path)

    # Run the simple merge
    result = _simple_merge(markdown_paths)

    # Sort pages by ascending page number (the expected order)
    sorted_pages = sorted(pages, key=lambda p: p[0])

    # --- Property: output contains all page contents ---
    for page_num, content in sorted_pages:
        assert content in result, (
            f"Page {page_num} content not found in merged output.\n"
            f"Content: {content!r}\n"
            f"Result snippet: {result[:200]!r}"
        )

    # --- Property: output contains <!-- Page X --> for each page ---
    for page_num, _ in sorted_pages:
        separator = f"<!-- Page {page_num} -->"
        assert separator in result, (
            f"Expected separator {separator!r} not found in merged output.\n"
            f"Result snippet: {result[:200]!r}"
        )

    # --- Property: pages appear in ascending numeric order ---
    # Find the position of each <!-- Page X --> separator in the result
    separator_positions = []
    for page_num, _ in sorted_pages:
        separator = f"<!-- Page {page_num} -->"
        pos = result.index(separator)
        separator_positions.append((page_num, pos))

    # Verify positions are strictly increasing (ascending order)
    for i in range(len(separator_positions) - 1):
        num_a, pos_a = separator_positions[i]
        num_b, pos_b = separator_positions[i + 1]
        assert pos_a < pos_b, (
            f"Page {num_a} separator appears after page {num_b} separator. "
            f"Expected ascending order. Positions: {separator_positions}"
        )

    # --- Property: separator X values match the actual page numbers ---
    # Extract all <!-- Page X --> comments from the result
    found_separators = re.findall(r"<!-- Page (\d+) -->", result)
    found_page_nums = [int(x) for x in found_separators]
    expected_page_nums = [p[0] for p in sorted_pages]

    assert found_page_nums == expected_page_nums, (
        f"Separator page numbers {found_page_nums} do not match "
        f"expected ascending page numbers {expected_page_nums}"
    )


# ---------------------------------------------------------------------------
# Unit tests for Merger (Requirements 4.1, 4.3, 4.4)
# ---------------------------------------------------------------------------

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import AppConfig
from src.merger import merge_pages


def _make_config(**overrides) -> AppConfig:
    """Return an AppConfig with sensible test defaults, allowing overrides."""
    defaults = dict(
        llm_base_url="http://localhost:1234",
        llm_api_key="test-key",
        llm_model="test-model",
        max_concurrency=1,
        max_retries=3,
        smart_merge=False,
        image_dpi=300,
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


# ---------------------------------------------------------------------------
# Test 1: Merged output is written to the correct path (Requirement 4.1)
# ---------------------------------------------------------------------------

def test_merge_pages_writes_output_to_correct_path(tmp_path: Path):
    """
    Verify that merge_pages creates the output file at the specified path.

    Requirements: 4.1
    """
    # Arrange: create two page Markdown files
    page1 = tmp_path / "page_001.md"
    page2 = tmp_path / "page_002.md"
    page1.write_text("# Page 1 content", encoding="utf-8")
    page2.write_text("# Page 2 content", encoding="utf-8")

    output_path = tmp_path / "output" / "final.md"
    config = _make_config(smart_merge=False)

    # Act
    asyncio.run(merge_pages([page1, page2], output_path, config))

    # Assert: output file exists at the specified path
    assert output_path.exists(), f"Expected output file at {output_path}"
    content = output_path.read_text(encoding="utf-8")
    assert "Page 1 content" in content
    assert "Page 2 content" in content


# ---------------------------------------------------------------------------
# Test 2: Smart merge calls LLM API with merge prompt content (Requirement 4.3)
# ---------------------------------------------------------------------------

def test_smart_merge_calls_llm_api_with_merge_prompt(tmp_path: Path):
    """
    Verify that when SMART_MERGE=true and merge_prompt_text is provided,
    merge_pages sends a request to the LLM API containing the merge prompt.

    Requirements: 4.3
    """
    # Arrange: create a page Markdown file
    page1 = tmp_path / "page_001.md"
    page1.write_text("# Some OCR content", encoding="utf-8")

    output_path = tmp_path / "final.md"
    config = _make_config(smart_merge=True)
    merge_prompt_text = "Please intelligently merge these pages."

    # Build a mock response that mimics httpx's response structure
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "# Merged content"}}]
    }

    mock_post = AsyncMock(return_value=mock_response)
    mock_client_instance = AsyncMock()
    mock_client_instance.post = mock_post
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        asyncio.run(
            merge_pages([page1], output_path, config, merge_prompt_text=merge_prompt_text)
        )

    # Assert: the LLM API was called once
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args

    # The URL should point to /v1/chat/completions
    called_url = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
    assert "/v1/chat/completions" in called_url, (
        f"Expected call to /v1/chat/completions, got: {called_url}"
    )

    # The request body should contain the merge prompt text
    request_body = call_kwargs[1].get("json") or (call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {})
    messages = request_body.get("messages", [])
    assert messages, "Expected messages in request body"
    combined_content = " ".join(
        str(m.get("content", "")) for m in messages
    )
    assert merge_prompt_text in combined_content, (
        f"Merge prompt text not found in request body. Content: {combined_content!r}"
    )

    # The output file should contain the LLM's response
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "# Merged content"


# ---------------------------------------------------------------------------
# Test 3: Missing merge_prompt.txt with SMART_MERGE=true falls back to
#         simple merge (Requirement 4.4)
# ---------------------------------------------------------------------------

def test_smart_merge_falls_back_to_simple_merge_when_prompt_missing(
    tmp_path: Path, caplog
):
    """
    Verify that when SMART_MERGE=true but merge_prompt_text is None,
    merge_pages falls back to simple merge and logs a warning.

    Requirements: 4.4
    """
    # Arrange: create a page Markdown file
    page1 = tmp_path / "page_001.md"
    page1.write_text("# Fallback content", encoding="utf-8")

    output_path = tmp_path / "final.md"
    config = _make_config(smart_merge=True)

    mock_post = AsyncMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock()
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with caplog.at_level(logging.WARNING, logger="src.merger"):
            asyncio.run(
                merge_pages([page1], output_path, config, merge_prompt_text=None)
            )

    # Assert: no LLM API call was made (simple merge used instead)
    mock_post.assert_not_called()

    # Assert: a warning was logged about the missing merge prompt
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("merge_prompt" in msg.lower() or "simple merge" in msg.lower() for msg in warning_messages), (
        f"Expected a warning about missing merge_prompt.txt. Got: {warning_messages}"
    )

    # Assert: output file was still created (simple merge ran)
    assert output_path.exists(), "Expected output file to be created via simple merge"
    content = output_path.read_text(encoding="utf-8")
    assert "Fallback content" in content


# ---------------------------------------------------------------------------
# Test 4: No page files found logs warning and skips merge (Requirement 4.4)
# ---------------------------------------------------------------------------

def test_merge_pages_with_empty_list_logs_warning_and_skips_output(
    tmp_path: Path, caplog
):
    """
    Verify that when merge_pages is called with an empty list of page files,
    it logs a warning and does NOT create the output file.

    Requirements: 4.4
    """
    output_path = tmp_path / "final.md"
    config = _make_config(smart_merge=False)

    with caplog.at_level(logging.WARNING, logger="src.merger"):
        asyncio.run(merge_pages([], output_path, config))

    # Assert: output file was NOT created
    assert not output_path.exists(), (
        "Expected no output file when no page files are provided"
    )

    # Assert: a warning was logged
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert warning_messages, "Expected at least one warning to be logged"
