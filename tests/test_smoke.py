"""
Smoke tests for project structure and entry points.

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 7.5
"""

import importlib
from pathlib import Path


# Project root is one level up from the tests/ directory
PROJECT_ROOT = Path(__file__).parent.parent


def test_src_main_is_importable():
    """Test that src.main can be imported without errors. Validates: Requirement 6.1"""
    module = importlib.import_module("src.main")
    assert module is not None


def test_src_config_is_importable():
    """Test that src.config can be imported without errors. Validates: Requirement 6.1"""
    module = importlib.import_module("src.config")
    assert module is not None


def test_env_example_exists():
    """Test that .env.example file exists. Validates: Requirement 6.2"""
    env_example = PROJECT_ROOT / ".env.example"
    assert env_example.exists(), ".env.example file does not exist"


def test_env_example_contains_all_expected_variables():
    """
    Test that .env.example contains all expected configuration variable names.
    Validates: Requirement 6.2
    """
    env_example = PROJECT_ROOT / ".env.example"
    content = env_example.read_text()

    expected_variables = [
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "MAX_CONCURRENCY",
        "MAX_RETRIES",
        "SMART_MERGE",
        "IMAGE_DPI",
    ]

    for var in expected_variables:
        assert var in content, f"Expected variable '{var}' not found in .env.example"


def test_prompt_txt_exists():
    """Test that prompt.txt file exists. Validates: Requirement 6.3"""
    prompt_file = PROJECT_ROOT / "prompt.txt"
    assert prompt_file.exists(), "prompt.txt file does not exist"


def test_prompt_txt_contains_ocr_instructions():
    """
    Test that prompt.txt contains relevant OCR-related content.
    Validates: Requirement 6.3
    """
    prompt_file = PROJECT_ROOT / "prompt.txt"
    content = prompt_file.read_text().lower()

    # Check for OCR-related keywords indicating the file contains OCR instructions
    ocr_keywords = ["ocr", "extract", "text", "markdown", "image"]
    found_keywords = [kw for kw in ocr_keywords if kw in content]
    assert len(found_keywords) > 0, (
        f"prompt.txt does not appear to contain OCR instructions. "
        f"Expected at least one of: {ocr_keywords}"
    )


def test_merge_prompt_txt_exists():
    """Test that merge_prompt.txt file exists. Validates: Requirement 6.4"""
    merge_prompt_file = PROJECT_ROOT / "merge_prompt.txt"
    assert merge_prompt_file.exists(), "merge_prompt.txt file does not exist"


def test_requirements_txt_exists():
    """Test that requirements.txt file exists. Validates: Requirement 7.5"""
    requirements_file = PROJECT_ROOT / "requirements.txt"
    assert requirements_file.exists(), "requirements.txt file does not exist"


def test_requirements_txt_has_pinned_versions():
    """
    Test that requirements.txt uses pinned versions (== operator) for all dependencies.
    Validates: Requirement 7.5
    """
    requirements_file = PROJECT_ROOT / "requirements.txt"
    content = requirements_file.read_text()

    # Collect non-empty, non-comment dependency lines
    dependency_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert len(dependency_lines) > 0, "requirements.txt contains no dependency lines"

    for line in dependency_lines:
        assert "==" in line, (
            f"Dependency line '{line}' does not use pinned version (==). "
            "All dependencies must have pinned versions."
        )
