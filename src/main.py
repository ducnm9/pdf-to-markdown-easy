"""
CLI Entry Point for OCR PDF to Markdown.

Orchestrates the full pipeline:
  1. Load configuration from .env
  2. Load OCR prompt from prompt.txt
  3. Optionally load merge prompt from merge_prompt.txt
  4. Discover PDF files in inputs/
  5. For each PDF: convert pages to images → OCR pages → merge Markdown
  6. Exit with code 0 if all succeeded, 1 if any failed
"""

import asyncio
import logging
import sys
from pathlib import Path

from src.config import ConfigError, load_config
from src.merger import merge_pages
from src.ocr import ocr_pages
from src.pdf_to_images import convert_pdf_to_images

logger = logging.getLogger(__name__)


def _log_startup_info() -> None:
    """Log môi trường và các dependency quan trọng khi khởi động."""
    import platform
    import sys
    import shutil

    logger.info("=== Startup diagnostics ===")
    logger.info("Python: %s", sys.version)
    logger.info("Platform: %s %s", platform.system(), platform.machine())

    # Kiểm tra poppler (pdftoppm / pdfinfo)
    for tool in ("pdftoppm", "pdfinfo"):
        path = shutil.which(tool)
        if path:
            logger.info("%-10s found: %s", tool, path)
        else:
            logger.error("%-10s NOT FOUND — poppler-utils chưa được cài!", tool)

    # Kiểm tra các Python package quan trọng
    for pkg in ("pdf2image", "httpx", "dotenv", "PIL"):
        try:
            mod = __import__(pkg)
            version = getattr(mod, "__version__", "unknown")
            logger.info("%-10s OK (version: %s)", pkg, version)
        except ImportError as e:
            logger.error("%-10s MISSING: %s", pkg, e)

    logger.info("=== End diagnostics ===")


def _discover_pdfs(inputs_dir: Path) -> list[Path]:
    """Return a sorted list of .pdf files in *inputs_dir*."""
    return sorted(inputs_dir.glob("*.pdf"))


async def main() -> int:
    """
    Main entry point. Discovers PDFs, runs the pipeline, returns exit code.

    Returns:
        0 if all PDFs processed successfully (or no PDFs found), 1 if any
        failures occurred.
    """
    # ------------------------------------------------------------------
    # 1. Configure logging to stderr at INFO level
    # ------------------------------------------------------------------
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    # ------------------------------------------------------------------
    # 1b. Startup diagnostics
    # ------------------------------------------------------------------
    _log_startup_info()

    # ------------------------------------------------------------------
    # 2. Load configuration
    # ------------------------------------------------------------------
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    # ------------------------------------------------------------------
    # 3. Load prompt.txt (required)
    # ------------------------------------------------------------------
    prompt_path = Path("prompt.txt")
    if not prompt_path.exists():
        logger.error("Required file 'prompt.txt' not found.")
        return 1
    prompt_text = prompt_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # 4. Load merge_prompt.txt (optional)
    # ------------------------------------------------------------------
    merge_prompt_path = Path("merge_prompt.txt")
    if merge_prompt_path.exists():
        merge_prompt_text: str | None = merge_prompt_path.read_text(encoding="utf-8")
    else:
        merge_prompt_text = None

    # ------------------------------------------------------------------
    # 5. Discover PDFs in inputs/
    # ------------------------------------------------------------------
    inputs_dir = Path("inputs")
    if not inputs_dir.exists():
        logger.info("'inputs/' directory does not exist. Nothing to process.")
        return 0

    pdf_files = _discover_pdfs(inputs_dir)
    if not pdf_files:
        logger.info("No PDF files found in 'inputs/'. Nothing to process.")
        return 0

    logger.info("Found %d PDF file(s) to process.", len(pdf_files))

    # ------------------------------------------------------------------
    # 6 & 7. Process each PDF through the full pipeline
    # ------------------------------------------------------------------
    any_failed = False

    for pdf_path in pdf_files:
        pdf_name = pdf_path.stem
        logger.info("Processing '%s'…", pdf_path.name)

        try:
            # ---- Stage 1: Convert PDF pages to images ----
            images_dir = Path("images") / pdf_name
            logger.info("[%s] Converting PDF to images…", pdf_path.name)
            image_paths = convert_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=images_dir,
                dpi=config.image_dpi,
            )
            logger.info(
                "[%s] Converted %d page(s) to images.",
                pdf_path.name,
                len(image_paths),
            )

            # ---- Stage 2: OCR each page image ----
            markdowns_dir = Path("markdowns") / pdf_name
            logger.info("[%s] Running OCR on %d page(s)…", pdf_path.name, len(image_paths))
            markdown_paths = await ocr_pages(
                image_paths=image_paths,
                output_dir=markdowns_dir,
                config=config,
                prompt_text=prompt_text,
            )
            logger.info(
                "[%s] OCR complete: %d page(s) processed.",
                pdf_path.name,
                len(markdown_paths),
            )

            # ---- Stage 3: Merge page Markdowns into final.md ----
            final_md_path = markdowns_dir / "final.md"
            logger.info("[%s] Merging pages into final.md…", pdf_path.name)
            await merge_pages(
                markdown_paths=markdown_paths,
                output_path=final_md_path,
                config=config,
                merge_prompt_text=merge_prompt_text,
            )
            logger.info(
                "[%s] Done. Final Markdown written to '%s'.",
                pdf_path.name,
                final_md_path,
            )

        except Exception as exc:
            logger.error(
                "[%s] Failed to process PDF: %s",
                pdf_path.name,
                exc,
            )
            any_failed = True

    # ------------------------------------------------------------------
    # 9. Return exit code
    # ------------------------------------------------------------------
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
