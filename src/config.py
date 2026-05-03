"""
Config Loader module for OCR PDF to Markdown.

Loads and validates application configuration from a .env file using
python-dotenv. Exposes an immutable AppConfig dataclass and a ConfigError
exception for missing or invalid configuration values.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration loaded from a .env file."""

    llm_base_url: str       # Required. Base URL for OpenAI-compatible API.
    llm_api_key: str        # Optional. API key for authentication. Defaults to "".
    llm_model: str          # Required. Model identifier.
    max_concurrency: int    # Max concurrent OCR requests. Default: 1.
    max_retries: int        # Max retry attempts per request. Default: 3.
    smart_merge: bool       # Use LLM-based smart merge. Default: False.
    image_dpi: int          # DPI for PDF-to-image conversion. Default: 300.


def load_config(env_path: str = ".env") -> AppConfig:
    """
    Load configuration from a .env file.

    Reads the file at *env_path* via python-dotenv, validates required fields,
    applies defaults for optional fields, and returns an immutable AppConfig.

    Args:
        env_path: Path to the .env file. Defaults to ".env" in the current
                  working directory.

    Returns:
        AppConfig with validated and defaulted values.

    Raises:
        ConfigError: If LLM_BASE_URL or LLM_MODEL is missing, or if any
                     integer/boolean field contains an invalid value.
    """
    # Load the .env file into the process environment.  override=False means
    # existing environment variables take precedence over the file, which is
    # the conventional dotenv behaviour.
    load_dotenv(dotenv_path=env_path, override=False)

    # ------------------------------------------------------------------ #
    # Required fields
    # ------------------------------------------------------------------ #
    missing: list[str] = []

    llm_base_url = os.environ.get("LLM_BASE_URL", "").strip()
    if not llm_base_url:
        missing.append("LLM_BASE_URL")

    llm_model = os.environ.get("LLM_MODEL", "").strip()
    if not llm_model:
        missing.append("LLM_MODEL")

    if missing:
        raise ConfigError(
            "Missing required configuration: " + ", ".join(missing)
        )

    # ------------------------------------------------------------------ #
    # Optional fields with defaults
    # ------------------------------------------------------------------ #
    llm_api_key = os.environ.get("LLM_API_KEY", "")

    max_concurrency = _parse_int("MAX_CONCURRENCY", os.environ.get("MAX_CONCURRENCY", "1"), min_value=1)
    max_retries = _parse_int("MAX_RETRIES", os.environ.get("MAX_RETRIES", "3"), min_value=0)
    image_dpi = _parse_int("IMAGE_DPI", os.environ.get("IMAGE_DPI", "300"), min_value=1)
    smart_merge = _parse_bool("SMART_MERGE", os.environ.get("SMART_MERGE", "false"))

    return AppConfig(
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        max_concurrency=max_concurrency,
        max_retries=max_retries,
        smart_merge=smart_merge,
        image_dpi=image_dpi,
    )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _parse_int(name: str, raw: str, *, min_value: int | None = None) -> int:
    """
    Parse *raw* as an integer for the configuration variable *name*.

    Raises:
        ConfigError: If *raw* is not a valid integer, or if the parsed value
                     is below *min_value*.
    """
    try:
        value = int(raw)
    except (ValueError, TypeError):
        raise ConfigError(
            f"Invalid value for {name}: {raw!r} is not a valid integer."
        )
    if min_value is not None and value < min_value:
        raise ConfigError(
            f"Invalid value for {name}: {value} must be >= {min_value}."
        )
    return value


def _parse_bool(name: str, raw: str) -> bool:
    """
    Parse *raw* as a boolean for the configuration variable *name*.

    Accepted truthy values (case-insensitive): "true", "1".
    Everything else is treated as False.

    Raises:
        ConfigError: If *raw* is not a recognised boolean string.
    """
    normalised = raw.strip().lower()
    if normalised in ("true", "1", "false", "0", "yes", "no", ""):
        return normalised in ("true", "1", "yes")
    raise ConfigError(
        f"Invalid value for {name}: {raw!r} is not a valid boolean "
        "(expected 'true', '1', 'false', or '0')."
    )
