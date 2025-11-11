"""
Test cases for Category 1: Test Body Smells (Flakiness checks).

These tests demonstrate anti-patterns that the linter should catch.
"""

import time
import os
import requests
import socket
from pathlib import Path


def test_with_time_sleep():
    """BAD: Using time.sleep() in a test (PYTEST-FLK-001)."""
    result = do_something()
    time.sleep(2)  # Should trigger warning
    assert result is not None


def test_with_open_file():
    """BAD: Using open() directly in a test (PYTEST-FLK-002)."""
    with open("test_file.txt", "w") as f:  # Should trigger warning
        f.write("test data")
    assert True


def test_with_network_call():
    """BAD: Making network calls in a test (PYTEST-FLK-003).

    This file imports requests, which should trigger a warning.
    """
    response = requests.get("http://example.com")
    assert response.status_code == 200


def test_with_cwd_dependency():
    """BAD: Using CWD-sensitive functions (PYTEST-FLK-004)."""
    current_dir = os.getcwd()  # Should trigger warning
    assert current_dir is not None


def test_with_path_cwd():
    """BAD: Using Path.cwd() (PYTEST-FLK-004)."""
    current_path = Path.cwd()  # Should trigger warning
    assert current_path is not None


# ============================================================================
# GOOD: Examples that should NOT trigger warnings
# ============================================================================


def test_with_tmp_path(tmp_path):
    """GOOD: Using tmp_path fixture for file I/O."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test data")
    assert test_file.read_text() == "test data"


def test_with_mocked_network(mocker):
    """GOOD: Mocking network calls instead of making real ones."""
    # Assuming we have pytest-mock installed
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200

    response = requests.get("http://example.com")
    assert response.status_code == 200


def test_with_explicit_wait():
    """GOOD: Using explicit polling instead of sleep."""
    max_attempts = 10
    for _ in range(max_attempts):
        result = check_condition()
        if result:
            break
    assert result


# Helper functions
def do_something():
    return True


def check_condition():
    return True
