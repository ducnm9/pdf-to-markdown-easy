"""
Property-based tests for the PDF Converter module (src/pdf_to_images.py).

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs.
"""

import itertools
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import HealthCheck, given, settings, strategies as st


# ---------------------------------------------------------------------------
# Stub out pdf2image before importing the module under test, so that the
# tests work even when poppler / pdf2image is not installed in the
# current environment.
# ---------------------------------------------------------------------------

_pdf2image_stub = MagicMock()
_pdf2image_exceptions_stub = MagicMock()
sys.modules.setdefault("pdf2image", _pdf2image_stub)
sys.modules.setdefault("pdf2image.exceptions", _pdf2image_exceptions_stub)

from src.pdf_to_images import convert_pdf_to_images  # noqa: E402


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# PDF names: ASCII alphanumeric with underscores/hyphens, no leading/trailing
# hyphens or underscores to keep names realistic and filesystem-safe.
_pdf_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=32,
).filter(lambda s: s[0].isalnum() and s[-1].isalnum())

# Page counts: 1 to 999 as required by the property spec
_page_count = st.integers(min_value=1, max_value=999)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Counter to generate unique subdirectories per Hypothesis example, avoiding
# state leakage between examples when tmp_path is reused across iterations.
_example_counter = itertools.count()


def _make_mock_images(count: int) -> list[MagicMock]:
    """Return a list of fresh mock PIL Image objects."""
    images = []
    for _ in range(count):
        img = MagicMock()
        img.save = MagicMock()
        images.append(img)
    return images


# ---------------------------------------------------------------------------
# Property 3: Image output naming convention
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 3: Image output naming convention
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    pdf_name=_pdf_name,
    page_count=_page_count,
)
def test_image_output_naming_convention(
    tmp_path: Path,
    pdf_name: str,
    page_count: int,
):
    """
    **Validates: Requirements 2.2**

    For any PDF name (alphanumeric with underscores/hyphens) and any page
    count (1 to 999), the generated image paths follow the pattern
    `images/{pdf_name}/page_NNN.png` where NNN is a zero-padded 3-digit
    page number starting from 001.
    """
    # Use a unique subdirectory per example to avoid state leakage between
    # Hypothesis examples that share the same tmp_path fixture.
    example_id = next(_example_counter)
    run_dir = tmp_path / f"run_{example_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    output_dir = run_dir / "images" / pdf_name
    fake_pdf_path = run_dir / f"{pdf_name}.pdf"
    fake_pdf_path.touch()

    mock_images = _make_mock_images(page_count)

    with patch("pdf2image.convert_from_path", return_value=mock_images, create=True):
        result_paths = convert_pdf_to_images(
            pdf_path=fake_pdf_path,
            output_dir=output_dir,
            dpi=300,
        )

    # Must return exactly page_count paths
    assert len(result_paths) == page_count

    # Each path must match the expected naming convention
    _page_pattern = re.compile(r"^page_(\d{3})\.png$")
    for i, path in enumerate(result_paths):
        expected_page_num = i + 1  # 1-based

        # Path must be inside output_dir
        assert path.parent == output_dir, (
            f"Expected parent {output_dir}, got {path.parent}"
        )

        # Filename must match page_NNN.png pattern
        match = _page_pattern.match(path.name)
        assert match is not None, (
            f"Filename '{path.name}' does not match 'page_NNN.png' pattern"
        )

        # Page number must be correct (1-based, zero-padded to 3 digits)
        actual_page_num = int(match.group(1))
        assert actual_page_num == expected_page_num, (
            f"Expected page number {expected_page_num:03d}, got {actual_page_num:03d}"
        )

    # Verify paths are sorted by page number
    assert result_paths == sorted(result_paths), (
        "Result paths are not sorted by page number"
    )


# ---------------------------------------------------------------------------
# Property 4: Image conversion resume skips existing files
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 4: Image conversion resume skips existing files
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    pdf_name=_pdf_name,
    page_count=st.integers(min_value=1, max_value=50),
    existing_page_indices=st.data(),
)
def test_resume_skips_existing_files(
    tmp_path: Path,
    pdf_name: str,
    page_count: int,
    existing_page_indices: st.DataObject,
):
    """
    **Validates: Requirements 2.3**

    For any set of page numbers and any subset of those pages that already
    have corresponding PNG files on disk, the PDF converter only converts
    pages whose output files do not yet exist.
    """
    # Draw a subset of page indices (0-based) that already exist on disk
    existing_indices = existing_page_indices.draw(
        st.frozensets(
            st.integers(min_value=0, max_value=page_count - 1),
            max_size=page_count,
        )
    )

    # Use a unique subdirectory per example to avoid state leakage between
    # Hypothesis examples that share the same tmp_path fixture.
    example_id = next(_example_counter)
    run_dir = tmp_path / f"run_{example_id}"

    output_dir = run_dir / "images" / pdf_name
    output_dir.mkdir(parents=True, exist_ok=True)
    fake_pdf_path = run_dir / f"{pdf_name}.pdf"
    fake_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    fake_pdf_path.touch()

    # Pre-create the "existing" PNG files on disk
    for idx in existing_indices:
        page_num = idx + 1  # 1-based
        existing_file = output_dir / f"page_{page_num:03d}.png"
        existing_file.touch()

    # Create fresh mock images for all pages
    mock_images = _make_mock_images(page_count)

    with patch("pdf2image.convert_from_path", return_value=mock_images, create=True):
        result_paths = convert_pdf_to_images(
            pdf_path=fake_pdf_path,
            output_dir=output_dir,
            dpi=300,
        )

    # Verify: image.save() was called only for pages that did NOT already exist
    for idx, mock_image in enumerate(mock_images):
        page_num = idx + 1
        if idx in existing_indices:
            # This page already existed — save() must NOT have been called
            mock_image.save.assert_not_called(), (
                f"page_{page_num:03d}.png already existed but save() was called"
            )
        else:
            # This page did not exist — save() must have been called exactly once
            mock_image.save.assert_called_once(), (
                f"page_{page_num:03d}.png did not exist but save() was not called"
            )

    # All page paths (existing + newly created) must be returned
    assert len(result_paths) == page_count


# ---------------------------------------------------------------------------
# Unit Tests for PDF Converter
# ---------------------------------------------------------------------------

import pytest
import logging


# ---------------------------------------------------------------------------
# Unit Test 1: Output directory is created when it doesn't exist
# ---------------------------------------------------------------------------

def test_output_directory_is_created(tmp_path: Path):
    """
    Validates: Requirements 2.4

    When the output directory does not exist, convert_pdf_to_images should
    create it before saving images.
    """
    output_dir = tmp_path / "images" / "my_pdf"
    fake_pdf_path = tmp_path / "my_pdf.pdf"
    fake_pdf_path.touch()

    assert not output_dir.exists(), "Pre-condition: output_dir should not exist yet"

    mock_images = _make_mock_images(2)

    with patch("pdf2image.convert_from_path", return_value=mock_images, create=True):
        result_paths = convert_pdf_to_images(
            pdf_path=fake_pdf_path,
            output_dir=output_dir,
            dpi=300,
        )

    assert output_dir.exists(), "Output directory should have been created"
    assert output_dir.is_dir(), "Output directory should be a directory"
    assert len(result_paths) == 2


# ---------------------------------------------------------------------------
# Unit Test 2: Corrupted PDF logs error and raises PdfConversionError
# ---------------------------------------------------------------------------

def test_corrupted_pdf_raises_pdf_conversion_error(tmp_path: Path, caplog):
    """
    Validates: Requirements 2.5

    When pdf2image raises an exception (e.g., corrupted PDF), the converter
    should log an error and raise PdfConversionError.
    """
    from src.pdf_to_images import PdfConversionError

    output_dir = tmp_path / "images" / "bad_pdf"
    fake_pdf_path = tmp_path / "bad_pdf.pdf"
    fake_pdf_path.touch()

    with caplog.at_level(logging.ERROR, logger="src.pdf_to_images"):
        with patch(
            "pdf2image.convert_from_path",
            side_effect=Exception("PDF is corrupted"),
            create=True,
        ):
            with pytest.raises(PdfConversionError) as exc_info:
                convert_pdf_to_images(
                    pdf_path=fake_pdf_path,
                    output_dir=output_dir,
                    dpi=300,
                )

    assert "PDF is corrupted" in str(exc_info.value)
    # Verify an error was logged
    assert any("bad_pdf" in record.message for record in caplog.records), (
        "Expected an error log message identifying the problematic file"
    )


# ---------------------------------------------------------------------------
# Unit Test 3: Resume skips pages that already have PNG files on disk
# ---------------------------------------------------------------------------

def test_resume_skips_existing_pages(tmp_path: Path):
    """
    Validates: Requirements 2.3

    When some page PNG files already exist on disk, convert_pdf_to_images
    should skip those pages (not call image.save() for them).
    """
    output_dir = tmp_path / "images" / "resume_pdf"
    output_dir.mkdir(parents=True)
    fake_pdf_path = tmp_path / "resume_pdf.pdf"
    fake_pdf_path.touch()

    # Pre-create page_001.png and page_003.png — these should be skipped
    (output_dir / "page_001.png").touch()
    (output_dir / "page_003.png").touch()

    mock_images = _make_mock_images(3)

    with patch("pdf2image.convert_from_path", return_value=mock_images, create=True):
        result_paths = convert_pdf_to_images(
            pdf_path=fake_pdf_path,
            output_dir=output_dir,
            dpi=300,
        )

    # page_001 (index 0) already existed — save() must NOT have been called
    mock_images[0].save.assert_not_called()
    # page_002 (index 1) did not exist — save() must have been called
    mock_images[1].save.assert_called_once()
    # page_003 (index 2) already existed — save() must NOT have been called
    mock_images[2].save.assert_not_called()

    # All 3 paths should still be returned
    assert len(result_paths) == 3


# ---------------------------------------------------------------------------
# Unit Test 4: Correct page count and file naming for a multi-page PDF
# ---------------------------------------------------------------------------

def test_multipage_pdf_correct_count_and_naming(tmp_path: Path):
    """
    Validates: Requirements 2.1, 2.2

    For a 3-page PDF, convert_pdf_to_images should return 3 paths with
    filenames page_001.png, page_002.png, page_003.png in the output directory.
    """
    output_dir = tmp_path / "images" / "multipage"
    fake_pdf_path = tmp_path / "multipage.pdf"
    fake_pdf_path.touch()

    mock_images = _make_mock_images(3)

    with patch("pdf2image.convert_from_path", return_value=mock_images, create=True):
        result_paths = convert_pdf_to_images(
            pdf_path=fake_pdf_path,
            output_dir=output_dir,
            dpi=300,
        )

    assert len(result_paths) == 3

    expected_names = ["page_001.png", "page_002.png", "page_003.png"]
    actual_names = [p.name for p in result_paths]
    assert actual_names == expected_names, (
        f"Expected filenames {expected_names}, got {actual_names}"
    )

    # All paths should be inside the output directory
    for path in result_paths:
        assert path.parent == output_dir, (
            f"Expected path inside {output_dir}, got {path.parent}"
        )

    # Paths should be sorted
    assert result_paths == sorted(result_paths)
