"""
Property-based and unit tests for the CLI entry point (src/main.py).
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from src.main import _discover_pdfs


# ---------------------------------------------------------------------------
# Property 10: PDF discovery filters by extension
# ---------------------------------------------------------------------------

# Strategy: generate valid filename stems (non-empty, no path separators)
_filename_stem = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
    min_size=1,
    max_size=20,
)

# Non-pdf extensions to mix in
_non_pdf_extensions = st.sampled_from([
    ".txt", ".png", ".jpg", ".docx", ".md", ".csv", ".xml", ".json", ".html",
])


@given(
    pdf_stems=st.lists(_filename_stem, min_size=0, max_size=10, unique=True),
    non_pdf_names=st.lists(
        st.tuples(_filename_stem, _non_pdf_extensions),
        min_size=0,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_discover_pdfs_filters_by_extension(
    pdf_stems: list[str],
    non_pdf_names: list[tuple[str, str]],
):
    # Feature: ocr-pdf-to-markdown, Property 10: PDF discovery filters by extension
    # Validates: Requirement 5.1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Create .pdf files
        for stem in pdf_stems:
            (tmp_path / f"{stem}.pdf").touch()

        # Create non-.pdf files
        for stem, ext in non_pdf_names:
            (tmp_path / f"{stem}{ext}").touch()

        result = _discover_pdfs(tmp_path)

        # All returned paths must have a .pdf suffix
        assert all(p.suffix == ".pdf" for p in result), (
            f"Non-.pdf file(s) returned: {[p for p in result if p.suffix != '.pdf']}"
        )

        # The returned paths must correspond exactly to the .pdf files we created
        expected = sorted(tmp_path / f"{stem}.pdf" for stem in pdf_stems)
        assert sorted(result) == expected, (
            f"Expected {expected}, got {sorted(result)}"
        )


# ---------------------------------------------------------------------------
# Unit tests for CLI orchestration (Task 7.3)
# ---------------------------------------------------------------------------

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.main import main


def _make_config():
    """Return a minimal AppConfig for testing."""
    from src.config import AppConfig
    return AppConfig(
        llm_base_url="http://localhost:1234",
        llm_api_key="",
        llm_model="test-model",
        max_concurrency=1,
        max_retries=0,
        smart_merge=False,
        image_dpi=300,
    )


def _setup_tmp_dir(tmp_path: Path, pdf_names: list[str]) -> None:
    """Create inputs/ dir with dummy PDFs and a prompt.txt in tmp_path."""
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for name in pdf_names:
        (inputs / name).write_bytes(b"%PDF-1.4 dummy")
    (tmp_path / "prompt.txt").write_text("OCR this page.")


# ---------------------------------------------------------------------------
# Test 1: CLI processes all PDFs through the full pipeline
# ---------------------------------------------------------------------------

def test_cli_processes_all_pdfs_through_full_pipeline(tmp_path, monkeypatch):
    """
    Each PDF in inputs/ must pass through all three pipeline stages:
    convert_pdf_to_images, ocr_pages, and merge_pages.
    Validates: Requirements 5.1, 5.2
    """
    pdf_names = ["doc_a.pdf", "doc_b.pdf"]
    _setup_tmp_dir(tmp_path, pdf_names)
    monkeypatch.chdir(tmp_path)

    mock_images = [Path("images/doc_a/page_001.png")]
    mock_markdowns = [Path("markdowns/doc_a/page_001.md")]

    with (
        patch("src.main.load_config", return_value=_make_config()),
        patch("src.main.convert_pdf_to_images", return_value=mock_images) as mock_convert,
        patch("src.main.ocr_pages", new_callable=AsyncMock, return_value=mock_markdowns) as mock_ocr,
        patch("src.main.merge_pages", new_callable=AsyncMock) as mock_merge,
    ):
        exit_code = asyncio.run(main())

    assert exit_code == 0
    # Both PDFs should have triggered each stage once
    assert mock_convert.call_count == 2
    assert mock_ocr.call_count == 2
    assert mock_merge.call_count == 2

    # Verify the correct pdf_path was passed for each call
    called_pdf_names = {call.kwargs["pdf_path"].name for call in mock_convert.call_args_list}
    assert called_pdf_names == set(pdf_names)


# ---------------------------------------------------------------------------
# Test 2: CLI logs file name and operation status for each step
# ---------------------------------------------------------------------------

def test_cli_logs_filename_and_status(tmp_path, monkeypatch, caplog):
    """
    The CLI must log the file name and operation status at each pipeline step.
    Validates: Requirement 5.3
    """
    _setup_tmp_dir(tmp_path, ["report.pdf"])
    monkeypatch.chdir(tmp_path)

    mock_images = [Path("images/report/page_001.png")]
    mock_markdowns = [Path("markdowns/report/page_001.md")]

    with (
        patch("src.main.load_config", return_value=_make_config()),
        patch("src.main.convert_pdf_to_images", return_value=mock_images),
        patch("src.main.ocr_pages", new_callable=AsyncMock, return_value=mock_markdowns),
        patch("src.main.merge_pages", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger="src.main"),
    ):
        asyncio.run(main())

    log_text = "\n".join(caplog.messages)
    # File name must appear in logs
    assert "report.pdf" in log_text
    # Status messages for each stage must appear
    assert any("image" in msg.lower() for msg in caplog.messages)
    assert any("ocr" in msg.lower() for msg in caplog.messages)
    assert any("merg" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Test 3: Exit code 0 when all PDFs succeed
# ---------------------------------------------------------------------------

def test_exit_code_0_when_all_pdfs_succeed(tmp_path, monkeypatch):
    """
    main() must return 0 when every PDF processes without error.
    Validates: Requirement 5.4
    """
    _setup_tmp_dir(tmp_path, ["success.pdf"])
    monkeypatch.chdir(tmp_path)

    mock_images = [Path("images/success/page_001.png")]
    mock_markdowns = [Path("markdowns/success/page_001.md")]

    with (
        patch("src.main.load_config", return_value=_make_config()),
        patch("src.main.convert_pdf_to_images", return_value=mock_images),
        patch("src.main.ocr_pages", new_callable=AsyncMock, return_value=mock_markdowns),
        patch("src.main.merge_pages", new_callable=AsyncMock),
    ):
        exit_code = asyncio.run(main())

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 4: Exit code 1 when one or more PDFs fail
# ---------------------------------------------------------------------------

def test_exit_code_1_when_a_pdf_fails(tmp_path, monkeypatch):
    """
    main() must return 1 when at least one PDF raises an exception during
    processing, and must continue processing remaining PDFs.
    Validates: Requirement 5.5
    """
    _setup_tmp_dir(tmp_path, ["bad.pdf", "good.pdf"])
    monkeypatch.chdir(tmp_path)

    call_count = {"n": 0}

    def convert_side_effect(**kwargs):
        call_count["n"] += 1
        if kwargs["pdf_path"].name == "bad.pdf":
            raise RuntimeError("Simulated conversion failure")
        return [Path("images/good/page_001.png")]

    mock_markdowns = [Path("markdowns/good/page_001.md")]

    with (
        patch("src.main.load_config", return_value=_make_config()),
        patch("src.main.convert_pdf_to_images", side_effect=convert_side_effect),
        patch("src.main.ocr_pages", new_callable=AsyncMock, return_value=mock_markdowns),
        patch("src.main.merge_pages", new_callable=AsyncMock),
    ):
        exit_code = asyncio.run(main())

    assert exit_code == 1
    # Both PDFs were attempted (error isolation)
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# Test 5a: Missing inputs/ directory logs message and exits with code 0
# ---------------------------------------------------------------------------

def test_missing_inputs_dir_exits_0(tmp_path, monkeypatch, caplog):
    """
    When inputs/ does not exist, main() must log an informative message and
    return exit code 0.
    Validates: Requirement 5.6
    """
    # Only create prompt.txt; do NOT create inputs/
    (tmp_path / "prompt.txt").write_text("OCR this page.")
    monkeypatch.chdir(tmp_path)

    with (
        patch("src.main.load_config", return_value=_make_config()),
        caplog.at_level(logging.INFO, logger="src.main"),
    ):
        exit_code = asyncio.run(main())

    assert exit_code == 0
    assert any("inputs" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Test 5b: Empty inputs/ directory logs message and exits with code 0
# ---------------------------------------------------------------------------

def test_empty_inputs_dir_exits_0(tmp_path, monkeypatch, caplog):
    """
    When inputs/ exists but contains no PDF files, main() must log an
    informative message and return exit code 0.
    Validates: Requirement 5.6
    """
    (tmp_path / "inputs").mkdir()
    (tmp_path / "prompt.txt").write_text("OCR this page.")
    monkeypatch.chdir(tmp_path)

    with (
        patch("src.main.load_config", return_value=_make_config()),
        caplog.at_level(logging.INFO, logger="src.main"),
    ):
        exit_code = asyncio.run(main())

    assert exit_code == 0
    assert any("no pdf" in msg.lower() or "nothing" in msg.lower() for msg in caplog.messages)
