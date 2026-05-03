"""
OCR Client module for OCR PDF to Markdown.

Sends base64-encoded page images to an OpenAI-compatible LLM API
(/v1/chat/completions) and saves the extracted Markdown text to disk.

Supports:
- Async concurrent processing bounded by asyncio.Semaphore
- Resume: skips pages whose output .md file already exists
- Retry with exponential backoff on HTTP / timeout / connection errors
- Optional Bearer token authentication
"""

import asyncio
import base64
import logging
from pathlib import Path

import httpx

from src.config import AppConfig

logger = logging.getLogger(__name__)


class OcrError(Exception):
    """Raised when OCR processing fails after all retries are exhausted."""
    pass


async def ocr_pages(
    image_paths: list[Path],
    output_dir: Path,
    config: AppConfig,
    prompt_text: str,
) -> list[Path]:
    """
    Send page images to the LLM API for OCR and save results as Markdown.

    Args:
        image_paths: Ordered list of page image paths.
        output_dir:  Directory to save Markdown files
                     (e.g., ``markdowns/{pdf_name}/``).
        config:      Application configuration.
        prompt_text: OCR prompt loaded from ``prompt.txt``.

    Returns:
        List of paths to generated/existing Markdown files, in the same
        order as *image_paths*.  Pages whose ``.md`` file already existed
        are included without re-processing (resume support).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(config.max_concurrency)
    timeout = httpx.Timeout(120.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = []
        for image_path in image_paths:
            # Derive output path: page_001.png → page_001.md
            stem = image_path.stem  # e.g. "page_001"
            output_path = output_dir / f"{stem}.md"
            tasks.append(
                _ocr_single_page(
                    image_path=image_path,
                    output_path=output_path,
                    config=config,
                    prompt_text=prompt_text,
                    semaphore=semaphore,
                    client=client,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect output paths; propagate OcrErrors so callers can decide how to
    # handle them, but keep processing the remaining pages (gather already
    # does this via return_exceptions=True).
    md_paths: list[Path] = []
    for result in results:
        if isinstance(result, Exception):
            # OcrError was already logged inside _ocr_single_page; re-raise
            # so the caller (main.py) can mark this PDF as failed.
            raise result
        md_paths.append(result)

    return md_paths


async def _ocr_single_page(
    image_path: Path,
    output_path: Path,
    config: AppConfig,
    prompt_text: str,
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
) -> Path:
    """
    Process a single page: encode image, call LLM API, save result.

    Retries up to ``config.max_retries`` times with exponential backoff
    (``2^attempt`` seconds) on HTTP errors (status >= 400),
    ``httpx.TimeoutException``, or ``httpx.RequestError``.

    Args:
        image_path:  Path to the source PNG image.
        output_path: Destination ``.md`` file path.
        config:      Application configuration.
        prompt_text: OCR prompt text.
        semaphore:   Shared concurrency limiter.
        client:      Shared async HTTP client.

    Returns:
        Path to the saved Markdown file.

    Raises:
        OcrError: If all retry attempts are exhausted.
    """
    # Resume support: skip if output already exists
    if output_path.exists():
        logger.info("Skipping %s (already exists)", output_path)
        return output_path

    # Base64-encode the image
    image_bytes = image_path.read_bytes()
    b64_image = base64.b64encode(image_bytes).decode("ascii")

    # Build the OpenAI-compatible request body
    request_body = {
        "model": config.llm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}"
                        },
                    },
                ],
            }
        ],
    }

    # Build headers
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.llm_api_key:
        headers["Authorization"] = f"Bearer {config.llm_api_key}"

    url = config.llm_base_url.rstrip("/") + "/v1/chat/completions"

    last_exception: Exception | None = None

    async with semaphore:
        for attempt in range(config.max_retries + 1):
            try:
                response = await client.post(url, json=request_body, headers=headers)

                if response.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Ensure parent directory exists (output_dir was already
                # created by ocr_pages, but be defensive)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")

                logger.info("Saved OCR result to %s", output_path)
                return output_path

            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
                last_exception = exc
                if attempt < config.max_retries:
                    wait_seconds = 2 ** attempt
                    logger.warning(
                        "OCR attempt %d/%d failed for %s (%s). "
                        "Retrying in %ds…",
                        attempt + 1,
                        config.max_retries + 1,
                        image_path.name,
                        exc,
                        wait_seconds,
                    )
                    await asyncio.sleep(wait_seconds)

    # All retries exhausted
    logger.error(
        "OCR failed for page %s after %d attempt(s): %s",
        image_path.name,
        config.max_retries + 1,
        last_exception,
    )
    raise OcrError(
        f"OCR failed for {image_path.name} after {config.max_retries + 1} "
        f"attempt(s): {last_exception}"
    )
