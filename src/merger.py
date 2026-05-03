"""
Merger module for OCR PDF to Markdown.

Combines individual page Markdown files into a single final.md.

Supports two merge modes:
- Simple merge: concatenates pages with <!-- Page X --> HTML comment separators
- Smart merge: sends concatenated content to the LLM API for intelligent cleanup
  and merging using the content of merge_prompt.txt as the prompt.

Falls back to simple merge when:
- merge_prompt_text is None and smart_merge is True (logs warning)
- The LLM API call fails during smart merge (logs warning)
"""

import logging
import re
from pathlib import Path

import httpx

from src.config import AppConfig

logger = logging.getLogger(__name__)


async def merge_pages(
    markdown_paths: list[Path],
    output_path: Path,
    config: AppConfig,
    merge_prompt_text: str | None = None,
) -> Path:
    """
    Merge individual page Markdown files into a single final.md.

    Args:
        markdown_paths:    Ordered list of page Markdown file paths.
        output_path:       Path for the merged output
                           (e.g., ``markdowns/{pdf_name}/final.md``).
        config:            Application configuration.
        merge_prompt_text: Content of ``merge_prompt.txt``.
                           ``None`` triggers fallback to simple merge.

    Returns:
        Path to the merged Markdown file.
    """
    if not markdown_paths:
        logger.warning(
            "No page Markdown files found; skipping merge for %s",
            output_path,
        )
        return output_path

    if config.smart_merge:
        if merge_prompt_text is None:
            logger.warning(
                "SMART_MERGE is enabled but merge_prompt.txt content was not "
                "provided; falling back to simple merge."
            )
            merged_content = _simple_merge(markdown_paths)
        else:
            # Attempt smart merge; fall back on any LLM failure.
            simple_content = _simple_merge(markdown_paths)
            try:
                merged_content = await _smart_merge(
                    simple_content, config, merge_prompt_text
                )
            except Exception as exc:
                logger.warning(
                    "Smart merge failed (%s); falling back to simple merge.",
                    exc,
                )
                merged_content = simple_content
    else:
        merged_content = _simple_merge(markdown_paths)

    # Ensure the parent directory exists before writing.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged_content, encoding="utf-8")
    logger.info("Merged output written to %s", output_path)

    return output_path


def _simple_merge(markdown_paths: list[Path]) -> str:
    """
    Concatenate page Markdown files with ``<!-- Page X -->`` separators.

    Pages are ordered by the numeric page number extracted from the filename
    (e.g., ``page_003.md`` → page 3).  Files whose names do not contain a
    recognisable page number are placed at the end in their original order.

    Args:
        markdown_paths: List of page Markdown file paths (any order).

    Returns:
        Merged Markdown content as a single string.
    """

    def _page_number(path: Path) -> int:
        """Extract the numeric page number from a filename like page_003.md."""
        match = re.search(r"(\d+)", path.stem)
        return int(match.group(1)) if match else 10 ** 9

    sorted_paths = sorted(markdown_paths, key=_page_number)

    parts: list[str] = []
    for path in sorted_paths:
        page_num = _page_number(path)
        content = path.read_text(encoding="utf-8")
        parts.append(f"<!-- Page {page_num} -->\n{content}")

    return "\n\n".join(parts)


async def _smart_merge(
    content: str,
    config: AppConfig,
    merge_prompt_text: str,
) -> str:
    """
    Send concatenated page content to the LLM API for intelligent merging.

    Uses the same OpenAI-compatible ``/v1/chat/completions`` endpoint as the
    OCR client.  The ``merge_prompt_text`` is sent as the user prompt, with
    the concatenated page content appended.

    Args:
        content:           Concatenated page Markdown (output of simple merge).
        config:            Application configuration.
        merge_prompt_text: Content of ``merge_prompt.txt``.

    Returns:
        LLM-processed merged Markdown content.

    Raises:
        Exception: Propagates any HTTP or parsing error so the caller can
                   decide whether to fall back to simple merge.
    """
    url = config.llm_base_url.rstrip("/") + "/v1/chat/completions"

    request_body = {
        "model": config.llm_model,
        "messages": [
            {
                "role": "user",
                "content": f"{merge_prompt_text}\n\n{content}",
            }
        ],
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.llm_api_key:
        headers["Authorization"] = f"Bearer {config.llm_api_key}"

    timeout = httpx.Timeout(120.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=request_body, headers=headers)

        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]
