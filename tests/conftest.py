"""
Shared pytest fixtures for the OCR PDF to Markdown test suite.
"""

import os
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Filesystem fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory that is cleaned up after each test."""
    return tmp_path


@pytest.fixture
def inputs_dir(tmp_path: Path) -> Path:
    """Return a temporary inputs/ directory (created, but empty)."""
    d = tmp_path / "inputs"
    d.mkdir()
    return d


@pytest.fixture
def images_dir(tmp_path: Path) -> Path:
    """Return a temporary images/ directory (created, but empty)."""
    d = tmp_path / "images"
    d.mkdir()
    return d


@pytest.fixture
def markdowns_dir(tmp_path: Path) -> Path:
    """Return a temporary markdowns/ directory (created, but empty)."""
    d = tmp_path / "markdowns"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Configuration fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_env_vars() -> dict:
    """Return the minimum required environment variables for AppConfig."""
    return {
        "LLM_BASE_URL": "http://localhost:1234",
        "LLM_MODEL": "test-model",
    }


@pytest.fixture
def full_env_vars() -> dict:
    """Return a complete set of environment variables for AppConfig."""
    return {
        "LLM_BASE_URL": "http://localhost:1234",
        "LLM_API_KEY": "test-api-key",
        "LLM_MODEL": "test-model",
        "MAX_CONCURRENCY": "4",
        "MAX_RETRIES": "5",
        "SMART_MERGE": "true",
        "IMAGE_DPI": "150",
    }


@pytest.fixture
def env_file(tmp_path: Path, full_env_vars: dict) -> Path:
    """Write a complete .env file to a temp directory and return its path."""
    env_path = tmp_path / ".env"
    lines = "\n".join(f"{k}={v}" for k, v in full_env_vars.items())
    env_path.write_text(lines + "\n")
    return env_path


@pytest.fixture
def minimal_env_file(tmp_path: Path, minimal_env_vars: dict) -> Path:
    """Write a minimal .env file (only required fields) and return its path."""
    env_path = tmp_path / ".env"
    lines = "\n".join(f"{k}={v}" for k, v in minimal_env_vars.items())
    env_path.write_text(lines + "\n")
    return env_path


# ---------------------------------------------------------------------------
# Mock config fixture (avoids loading from disk)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """
    Return an AppConfig-like object with sensible test defaults.

    Import is deferred so this fixture can be used even before src/config.py
    is fully implemented — tests that need the real AppConfig should import
    it directly.
    """
    try:
        from src.config import AppConfig
        return AppConfig(
            llm_base_url="http://localhost:1234",
            llm_api_key="test-key",
            llm_model="test-model",
            max_concurrency=1,
            max_retries=3,
            smart_merge=False,
            image_dpi=300,
        )
    except ImportError:
        # src.config not yet implemented; return a simple namespace
        import types
        cfg = types.SimpleNamespace(
            llm_base_url="http://localhost:1234",
            llm_api_key="test-key",
            llm_model="test-model",
            max_concurrency=1,
            max_retries=3,
            smart_merge=False,
            image_dpi=300,
        )
        return cfg
