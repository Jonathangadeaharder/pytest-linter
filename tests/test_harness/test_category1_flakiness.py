"""
Automated tests for Category 1: Test Body Smells (Flakiness checks).

Tests for rules:
- W9001: pytest-flk-time-sleep
- W9002: pytest-flk-io-open
- W9003: pytest-flk-network-import
- W9004: pytest-flk-cwd-dependency
"""

import pytest
from pylint.testutils import MessageTest

from tests.test_harness.base import PytestDeepAnalysisTestCase, msg


class TestTimeSleep(PytestDeepAnalysisTestCase):
    """Tests for W9001: pytest-flk-time-sleep"""

    def test_time_sleep_in_test_function(self):
        """Should warn when time.sleep() is used in a test function."""
        code = """
        import time

        def test_with_sleep():
            result = do_something()
            time.sleep(2)  # Line 6
            assert result
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-time-sleep", line=6)
        )

    def test_sleep_direct_import(self):
        """Should warn when sleep is imported directly."""
        code = """
        from time import sleep

        def test_with_sleep():
            result = do_something()
            sleep(1)  # Line 6
            assert result
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-time-sleep", line=6)
        )

    def test_sleep_outside_test_function(self):
        """Should NOT warn when sleep is outside a test function."""
        code = """
        import time

        def helper_function():
            time.sleep(1)  # OK - not in a test function
            return True

        def test_something():
            assert helper_function()
        """
        self.assert_no_messages(code)


class TestFileIO(PytestDeepAnalysisTestCase):
    """Tests for W9002: pytest-flk-io-open"""

    def test_open_in_test_function(self):
        """Should warn when open() is used in a test function."""
        code = """
        def test_file_operation():
            with open("test.txt", "w") as f:  # Line 3
                f.write("data")
            assert True
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-io-open", line=3)
        )

    def test_open_with_tmp_path_fixture(self):
        """Should still warn even with tmp_path fixture (open itself is the issue)."""
        code = """
        def test_with_tmp_path(tmp_path):
            test_file = tmp_path / "test.txt"
            # While using tmp_path is good, we still detect open()
            with open(test_file, "w") as f:  # Line 5
                f.write("data")
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-io-open", line=5)
        )

    def test_open_outside_test(self):
        """Should NOT warn when open is outside a test function."""
        code = """
        def load_config():
            with open("config.txt", "r") as f:
                return f.read()

        def test_something():
            assert True
        """
        self.assert_no_messages(code)


class TestNetworkImports(PytestDeepAnalysisTestCase):
    """Tests for W9003: pytest-flk-network-import"""

    def test_requests_import(self):
        """Should warn when requests is imported."""
        code = """
        import requests  # Line 2

        def test_api_call():
            response = requests.get("http://example.com")
            assert response.status_code == 200
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-network-import", line=2)
        )

    def test_socket_import(self):
        """Should warn when socket is imported."""
        code = """
        import socket  # Line 2

        def test_connection():
            sock = socket.socket()
            assert sock
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-network-import", line=2)
        )

    def test_from_import_requests(self):
        """Should warn when importing from requests."""
        code = """
        from requests import get  # Line 2

        def test_api():
            response = get("http://example.com")
            assert response
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-network-import", line=2)
        )

    def test_httpx_import(self):
        """Should warn when httpx is imported."""
        code = """
        import httpx  # Line 2

        def test_async_api():
            client = httpx.Client()
            assert client
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-network-import", line=2)
        )

    def test_aiohttp_import(self):
        """Should warn when aiohttp is imported."""
        code = """
        import aiohttp  # Line 2

        def test_websocket():
            session = aiohttp.ClientSession()
            assert session
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-network-import", line=2)
        )

    def test_urllib3_import(self):
        """Should warn when urllib3 is imported."""
        code = """
        import urllib3  # Line 2

        def test_pool():
            http = urllib3.PoolManager()
            assert http
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-network-import", line=2)
        )

    def test_non_network_import(self):
        """Should NOT warn for non-network imports."""
        code = """
        import os
        import sys
        import json

        def test_something():
            assert os.path.exists("/")
        """
        self.assert_no_messages(code)


class TestCWDDependency(PytestDeepAnalysisTestCase):
    """Tests for W9004: pytest-flk-cwd-dependency"""

    def test_os_getcwd(self):
        """Should warn when os.getcwd() is used in a test."""
        code = """
        import os

        def test_current_directory():
            current_dir = os.getcwd()  # Line 5
            assert current_dir
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-cwd-dependency", line=5)
        )

    def test_os_chdir(self):
        """Should warn when os.chdir() is used in a test."""
        code = """
        import os

        def test_change_directory():
            os.chdir("/tmp")  # Line 5
            assert True
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-cwd-dependency", line=5)
        )

    def test_path_cwd(self):
        """Should warn when Path.cwd() is used in a test."""
        code = """
        from pathlib import Path

        def test_path_cwd():
            current = Path.cwd()  # Line 5
            assert current
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-cwd-dependency", line=5)
        )

    def test_getcwd_direct_import(self):
        """Should warn when getcwd is imported directly."""
        code = """
        from os import getcwd

        def test_cwd():
            cwd = getcwd()  # Line 5
            assert cwd
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-cwd-dependency", line=5)
        )

    def test_cwd_outside_test(self):
        """Should NOT warn when CWD functions are outside tests."""
        code = """
        import os

        def get_project_root():
            return os.getcwd()

        def test_something():
            assert True
        """
        self.assert_no_messages(code)


class TestMultipleIssues(PytestDeepAnalysisTestCase):
    """Tests for multiple flakiness issues in one file."""

    def test_multiple_warnings(self):
        """Should detect multiple issues in the same test function."""
        code = """
        import time
        import os

        def test_multiple_problems():
            time.sleep(1)  # Line 6
            cwd = os.getcwd()  # Line 7
            with open("file.txt", "w") as f:  # Line 8
                f.write("data")
            assert True
        """
        self.assert_adds_messages(
            code,
            msg("pytest-flk-time-sleep", line=6),
            msg("pytest-flk-cwd-dependency", line=7),
            msg("pytest-flk-io-open", line=8),
        )
