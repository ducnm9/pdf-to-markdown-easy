"""
Property-based tests for the Config Loader module (src/config.py).

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs.
"""

import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.config import AppConfig, ConfigError, load_config


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty strings that are safe to use as URL / model identifiers
_nonempty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_.:/@",
    ),
    min_size=1,
    max_size=64,
)

# Strings for API key: printable ASCII, no leading/trailing whitespace,
# no newlines — these survive dotenv parsing unchanged.
_api_key_text = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_.:/@+",
        ),
        min_size=1,
        max_size=64,
    ),
)

# Valid integer ranges per the config validation rules
_max_concurrency = st.integers(min_value=1, max_value=32)
_max_retries = st.integers(min_value=0, max_value=20)
_image_dpi = st.integers(min_value=1, max_value=600)

# Boolean represented as the canonical string values accepted by _parse_bool
_smart_merge_str = st.sampled_from(["true", "false"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_CONFIG_KEYS = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "MAX_CONCURRENCY",
    "MAX_RETRIES",
    "SMART_MERGE",
    "IMAGE_DPI",
]


def _clear_config_env(monkeypatch):
    """Remove all config-related env vars so dotenv values are used."""
    for key in _CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Property 1: Configuration round-trip
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 1: Configuration round-trip
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    llm_base_url=_nonempty_text,
    llm_model=_nonempty_text,
    llm_api_key=_api_key_text,
    max_concurrency=_max_concurrency,
    max_retries=_max_retries,
    smart_merge_str=_smart_merge_str,
    image_dpi=_image_dpi,
)
def test_config_round_trip(
    monkeypatch,
    llm_base_url: str,
    llm_model: str,
    llm_api_key: str,
    max_concurrency: int,
    max_retries: int,
    smart_merge_str: str,
    image_dpi: int,
):
    """
    **Validates: Requirements 1.2**

    For any valid set of config values, writing them to a .env file and
    loading via load_config produces an AppConfig with fields matching
    the original values.
    """
    _clear_config_env(monkeypatch)

    with tempfile.TemporaryDirectory() as tmp_dir:
        env_path = Path(tmp_dir) / ".env"
        env_path.write_text(
            f"LLM_BASE_URL={llm_base_url}\n"
            f"LLM_MODEL={llm_model}\n"
            f"LLM_API_KEY={llm_api_key}\n"
            f"MAX_CONCURRENCY={max_concurrency}\n"
            f"MAX_RETRIES={max_retries}\n"
            f"SMART_MERGE={smart_merge_str}\n"
            f"IMAGE_DPI={image_dpi}\n"
        )

        config = load_config(env_path=str(env_path))

    assert isinstance(config, AppConfig)
    assert config.llm_base_url == llm_base_url.strip()
    assert config.llm_model == llm_model.strip()
    assert config.llm_api_key == llm_api_key
    assert config.max_concurrency == max_concurrency
    assert config.max_retries == max_retries
    assert config.smart_merge == (smart_merge_str == "true")
    assert config.image_dpi == image_dpi


# ---------------------------------------------------------------------------
# Property 2: Missing required config raises error
# ---------------------------------------------------------------------------

# Feature: ocr-pdf-to-markdown, Property 2: Missing required config raises error
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    missing=st.frozensets(
        st.sampled_from(["LLM_BASE_URL", "LLM_MODEL"]),
        min_size=1,
    ),
    llm_base_url=_nonempty_text,
    llm_model=_nonempty_text,
)
def test_missing_required_config_raises_error(
    monkeypatch,
    missing: frozenset,
    llm_base_url: str,
    llm_model: str,
):
    """
    **Validates: Requirements 1.7**

    For any .env file content that is missing LLM_BASE_URL, LLM_MODEL,
    or both, calling load_config raises ConfigError whose message contains
    the name of each missing variable.
    """
    _clear_config_env(monkeypatch)

    lines = []
    if "LLM_BASE_URL" not in missing:
        lines.append(f"LLM_BASE_URL={llm_base_url}")
    if "LLM_MODEL" not in missing:
        lines.append(f"LLM_MODEL={llm_model}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        env_path = Path(tmp_dir) / ".env"
        env_path.write_text("\n".join(lines) + "\n")

        with pytest.raises(ConfigError) as exc_info:
            load_config(env_path=str(env_path))

    error_message = str(exc_info.value)
    for var in missing:
        assert var in error_message, (
            f"Expected '{var}' to appear in ConfigError message, got: {error_message!r}"
        )


# ===========================================================================
# Unit Tests for Config Loader
# ===========================================================================

_ALL_CONFIG_KEYS = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "MAX_CONCURRENCY",
    "MAX_RETRIES",
    "SMART_MERGE",
    "IMAGE_DPI",
]


def _clear_env(monkeypatch):
    """Remove all config-related env vars to prevent interference."""
    for key in _ALL_CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# 1. Load all values from a complete .env file
# ---------------------------------------------------------------------------

def test_load_all_values_from_complete_env_file(tmp_path, monkeypatch):
    """Test that all values are correctly loaded from a complete .env file.

    Validates: Requirements 1.1, 1.2
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_API_KEY=my-secret-key\n"
        "LLM_MODEL=deepseek-chat\n"
        "MAX_CONCURRENCY=4\n"
        "MAX_RETRIES=5\n"
        "SMART_MERGE=true\n"
        "IMAGE_DPI=150\n"
    )

    config = load_config(env_path=str(env_path))

    assert config.llm_base_url == "http://localhost:1234"
    assert config.llm_api_key == "my-secret-key"
    assert config.llm_model == "deepseek-chat"
    assert config.max_concurrency == 4
    assert config.max_retries == 5
    assert config.smart_merge is True
    assert config.image_dpi == 150


# ---------------------------------------------------------------------------
# 2. Default value for MAX_CONCURRENCY=1
# ---------------------------------------------------------------------------

def test_default_max_concurrency(tmp_path, monkeypatch):
    """Test that MAX_CONCURRENCY defaults to 1 when not specified.

    Validates: Requirement 1.3
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
    )

    config = load_config(env_path=str(env_path))

    assert config.max_concurrency == 1


# ---------------------------------------------------------------------------
# 3. Default value for MAX_RETRIES=3
# ---------------------------------------------------------------------------

def test_default_max_retries(tmp_path, monkeypatch):
    """Test that MAX_RETRIES defaults to 3 when not specified.

    Validates: Requirement 1.4
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
    )

    config = load_config(env_path=str(env_path))

    assert config.max_retries == 3


# ---------------------------------------------------------------------------
# 4. Default value for SMART_MERGE=False
# ---------------------------------------------------------------------------

def test_default_smart_merge(tmp_path, monkeypatch):
    """Test that SMART_MERGE defaults to False when not specified.

    Validates: Requirement 1.5
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
    )

    config = load_config(env_path=str(env_path))

    assert config.smart_merge is False


# ---------------------------------------------------------------------------
# 5. Default value for IMAGE_DPI=300
# ---------------------------------------------------------------------------

def test_default_image_dpi(tmp_path, monkeypatch):
    """Test that IMAGE_DPI defaults to 300 when not specified.

    Validates: Requirement 1.6
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
    )

    config = load_config(env_path=str(env_path))

    assert config.image_dpi == 300


# ---------------------------------------------------------------------------
# 6. ConfigError raised for missing LLM_BASE_URL
# ---------------------------------------------------------------------------

def test_config_error_missing_llm_base_url(tmp_path, monkeypatch):
    """Test that ConfigError is raised when LLM_BASE_URL is missing.

    Validates: Requirement 1.7
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text("LLM_MODEL=test-model\n")

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=str(env_path))

    assert "LLM_BASE_URL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7. ConfigError raised for missing LLM_MODEL
# ---------------------------------------------------------------------------

def test_config_error_missing_llm_model(tmp_path, monkeypatch):
    """Test that ConfigError is raised when LLM_MODEL is missing.

    Validates: Requirement 1.7
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text("LLM_BASE_URL=http://localhost:1234\n")

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=str(env_path))

    assert "LLM_MODEL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 8. Invalid integer values raise ConfigError
# ---------------------------------------------------------------------------

def test_config_error_invalid_max_concurrency(tmp_path, monkeypatch):
    """Test that a non-integer MAX_CONCURRENCY raises ConfigError.

    Validates: Requirement 1.7
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
        "MAX_CONCURRENCY=not-a-number\n"
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=str(env_path))

    assert "MAX_CONCURRENCY" in str(exc_info.value)


def test_config_error_invalid_max_retries(tmp_path, monkeypatch):
    """Test that a non-integer MAX_RETRIES raises ConfigError.

    Validates: Requirement 1.7
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
        "MAX_RETRIES=abc\n"
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=str(env_path))

    assert "MAX_RETRIES" in str(exc_info.value)


def test_config_error_invalid_image_dpi(tmp_path, monkeypatch):
    """Test that a non-integer IMAGE_DPI raises ConfigError.

    Validates: Requirement 1.7
    """
    _clear_env(monkeypatch)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=http://localhost:1234\n"
        "LLM_MODEL=test-model\n"
        "IMAGE_DPI=high\n"
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(env_path=str(env_path))

    assert "IMAGE_DPI" in str(exc_info.value)
