"""
PDF Converter module for OCR PDF to Markdown.

Converts PDF pages to PNG images using pdf2image (poppler backend).
Supports resume: skips pages whose output PNG already exists on disk.

Memory optimization: converts one page at a time using first_page/last_page
parameters to avoid loading the entire PDF into memory at once.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PdfConversionError(Exception):
    """Raised when a PDF file cannot be converted (corrupted or unreadable)."""
    pass


def _get_page_count(pdf_path: Path) -> int:
    """Return the total number of pages in a PDF using pdfinfo."""
    from pdf2image.exceptions import PDFInfoNotInstalledError
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(str(pdf_path))
        return info["Pages"]
    except Exception as exc:
        raise PdfConversionError(
            f"Could not read page count from '{pdf_path}': {exc}"
        ) from exc


def convert_pdf_to_images(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 300,
) -> list[Path]:
    """
    Convert each page of a PDF to a PNG image.

    Processes one page at a time to keep memory usage low — safe for large
    PDFs even in memory-constrained environments (e.g. Docker containers).

    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory to save images (e.g., images/{pdf_name}/).
        dpi: Resolution for image conversion. Defaults to 300.

    Returns:
        Sorted list of paths to all page PNG files (existing + newly created),
        ordered by page number.

    Raises:
        PdfConversionError: If the PDF is corrupted or unreadable.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from pdf2image import convert_from_path
        logger.info("pdf2image imported OK")
        logger.info("PDF path: %s (exists=%s, size=%s bytes)",
                    pdf_path, pdf_path.exists(),
                    pdf_path.stat().st_size if pdf_path.exists() else "N/A")
        page_count = _get_page_count(pdf_path)
    except PdfConversionError:
        raise
    except Exception as exc:
        logger.error("Failed to read PDF '%s': %s", pdf_path, exc)
        raise PdfConversionError(
            f"Could not convert PDF '{pdf_path}': {exc}"
        ) from exc

    logger.info("PDF has %d page(s): %s", page_count, pdf_path.name)

    page_paths: list[Path] = []

    for page_number in range(1, page_count + 1):
        filename = f"page_{page_number:03d}.png"
        page_path = output_dir / filename

        if page_path.exists():
            # Resume support: skip pages already on disk.
            logger.debug("Skipping existing page image: %s", page_path)
            page_paths.append(page_path)
            continue

        try:
            # Convert one page at a time — avoids loading entire PDF into RAM
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_number,
                last_page=page_number,
            )
            images[0].save(page_path, format="PNG")
            # Explicitly delete to free memory before next page
            del images
            logger.info(
                "Saved page %d/%d: %s", page_number, page_count, page_path
            )
        except Exception as exc:
            logger.error(
                "Failed to convert page %d of '%s': %s",
                page_number, pdf_path, exc,
            )
            raise PdfConversionError(
                f"Could not convert page {page_number} of '{pdf_path}': {exc}"
            ) from exc

        page_paths.append(page_path)

    return sorted(page_paths)
