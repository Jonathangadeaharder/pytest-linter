"""
Pytest configuration for the automated test harness.
"""

import pytest


def pytest_configure(config):
    """Configure pytest for the test harness."""
    # Add custom markers if needed
    config.addinivalue_line("markers", "category1: Category 1 test body smell tests")
    config.addinivalue_line(
        "markers", "category2: Category 2 fixture definition smell tests"
    )
    config.addinivalue_line(
        "markers", "category3: Category 3 fixture interaction smell tests"
    )
