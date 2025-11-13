"""Tests for semantic quality checks (BDD/PBT/DbC alignment).

This module tests:
- E9014: pytest-test-no-assert (Assertion-Free tests)
- W9015: pytest-mock-only-verify (Interaction-Only tests)
- W9016: pytest-bdd-missing-scenario (BDD traceability)
- W9017: pytest-no-property-test-hint (PBT suggestions)
- W9018: pytest-no-contract-hint (DbC suggestions)
"""

from tests.test_harness.base import PytestDeepAnalysisTestCase, msg


class TestE9014_AssertionFree(PytestDeepAnalysisTestCase):
    """Tests for E9014: pytest-test-no-assert."""

    def test_no_assert_triggers_error(self):
        """Test without assertions should trigger E9014."""
        code = """
        def test_example():
            x = 1 + 1
            print(x)
        """
        self.assert_adds_messages(
            code,
            msg("pytest-test-no-assert", line=2),
            msg("pytest-bdd-missing-scenario", line=2),  # Also triggers BDD warning
        )

    def test_with_assert_no_error(self):
        """Test with assertion should not trigger E9014."""
        code = """
        def test_example():
            x = 1 + 1
            assert x == 2
        """
        # Triggers magic-assert (2 is magic) and BDD warning, but not assertion-free
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=4),
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_pytest_raises_no_error(self):
        """Test using pytest.raises should not trigger E9014."""
        code = """
        import pytest

        def test_example():
            with pytest.raises(ValueError):
                raise ValueError("test")
        """
        # pytest.raises is valid, no assertion-free error
        self.assert_adds_messages(
            code,
            msg("pytest-bdd-missing-scenario", line=4),
        )

    def test_raises_shorthand_no_error(self):
        """Test using raises shorthand should not trigger E9014."""
        code = """
        from pytest import raises

        def test_example():
            with raises(ValueError):
                raise ValueError("test")
        """
        self.assert_adds_messages(
            code,
            msg("pytest-bdd-missing-scenario", line=4),
        )

    def test_multiple_asserts(self):
        """Test with multiple assertions should not trigger E9014."""
        code = """
        def test_example():
            x = 1
            assert x > 0
            assert x < 10
            assert isinstance(x, int)
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=5),  # 10 is magic
            msg("pytest-bdd-missing-scenario", line=2),
        )


class TestW9015_MockOnlyVerify(PytestDeepAnalysisTestCase):
    """Tests for W9015: pytest-mock-only-verify."""

    def test_only_mock_verify_triggers_warning(self):
        """Test with only mock.assert_called should trigger both E9014 and W9015.

        Mock verification methods are not Python assert statements, so tests
        with only mock verifications have no real assertions.
        """
        code = """
        def test_example(mock_service):
            mock_service.do_something()
            mock_service.assert_called_once()
        """
        self.assert_adds_messages(
            code,
            msg("pytest-test-no-assert", line=2),  # No Python assertions
            msg("pytest-mock-only-verify", line=2),  # Only mock verifications
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_mock_verify_with_state_assert_no_warning(self):
        """Test with both mock verify and state assert should not trigger W9015."""
        code = """
        def test_example(mock_service):
            result = mock_service.do_something()
            mock_service.assert_called_once()
            assert result == 42
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=5),  # 42 is magic
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_assert_called_with(self):
        """Test with assert_called_with triggers E9014 and W9015."""
        code = """
        def test_example(mock_api):
            mock_api.post("/endpoint", data={"key": "value"})
            mock_api.post.assert_called_with("/endpoint", data={"key": "value"})
        """
        self.assert_adds_messages(
            code,
            msg("pytest-test-no-assert", line=2),  # No Python assertions
            msg("pytest-mock-only-verify", line=2),  # Only mock verifications
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_assert_called_once_with(self):
        """Test with assert_called_once_with triggers E9014 and W9015."""
        code = """
        def test_example(mock_logger):
            mock_logger.log("message")
            mock_logger.log.assert_called_once_with("message")
        """
        self.assert_adds_messages(
            code,
            msg("pytest-test-no-assert", line=2),
            msg("pytest-mock-only-verify", line=2),
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_multiple_mock_verifications(self):
        """Test with multiple mock verifications triggers E9014 and W9015."""
        code = """
        def test_example(mock_service):
            mock_service.start()
            mock_service.process()
            mock_service.stop()
            mock_service.start.assert_called_once()
            mock_service.process.assert_called()
            mock_service.stop.assert_called()
        """
        self.assert_adds_messages(
            code,
            msg("pytest-test-no-assert", line=2),
            msg("pytest-mock-only-verify", line=2),
            msg("pytest-bdd-missing-scenario", line=2),
        )


class TestW9016_BDDTraceability(PytestDeepAnalysisTestCase):
    """Tests for W9016: pytest-bdd-missing-scenario."""

    def test_no_bdd_marker_triggers_warning(self):
        """Test without BDD marker should trigger W9016."""
        code = """
        def test_user_login():
            assert True
        """
        self.assert_adds_messages(
            code,
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_scenario_marker_no_warning(self):
        """Test with @pytest.mark.scenario should not trigger W9016."""
        code = """
        import pytest

        @pytest.mark.scenario("user_login.feature", "Successful login")
        def test_user_login():
            assert True
        """
        # No BDD warning with scenario marker
        self.assert_no_messages(code)

    def test_gherkin_in_docstring_no_warning(self):
        """Test with Gherkin keywords in docstring should not trigger W9016."""
        code = '''
        def test_user_login():
            """
            Scenario: Successful user login
            Given a registered user
            When the user logs in with valid credentials
            Then the user should see the dashboard
            """
            assert True
        '''
        # No BDD warning with Gherkin docstring
        self.assert_no_messages(code)

    def test_feature_marker_no_warning(self):
        """Test with feature marker should not trigger W9016."""
        code = """
        import pytest

        @pytest.mark.feature("authentication")
        def test_user_login():
            assert True
        """
        self.assert_no_messages(code)

    def test_given_when_then_docstring(self):
        """Test with Given/When/Then in docstring should not trigger W9016."""
        code = '''
        def test_calculation():
            """
            Given two numbers
            When I add them
            Then I get the sum
            """
            assert 1 + 1 == 2
        '''
        # Has Gherkin docstring (no BDD warning) but triggers magic-assert for 2
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=8),
        )


class TestW9017_PropertyBasedTestingHint(PytestDeepAnalysisTestCase):
    """Tests for W9017: pytest-no-property-test-hint."""

    def test_parametrize_with_many_params_triggers_hint(self):
        """Test with many parametrize values should trigger W9017."""
        code = """
        import pytest

        @pytest.mark.parametrize("x", [1, 2, 3, 4, 5, 6, 7, 8])
        def test_positive_numbers(x):
            assert x > 0
        """
        self.assert_adds_messages(
            code,
            msg("pytest-no-property-test-hint", line=4),
            msg("pytest-bdd-missing-scenario", line=4),
        )

    def test_parametrize_with_few_params_no_hint(self):
        """Test with few parametrize values should not trigger W9017."""
        code = """
        import pytest

        @pytest.mark.parametrize("x", [1, 2, 3])
        def test_small_numbers(x):
            assert x > 0
        """
        # Only BDD warning, no PBT hint
        self.assert_adds_messages(
            code,
            msg("pytest-bdd-missing-scenario", line=4),
        )

    def test_hypothesis_already_used_no_hint(self):
        """Test already using Hypothesis should not trigger W9017."""
        code = """
        import pytest
        from hypothesis import given
        from hypothesis.strategies import integers

        @pytest.mark.parametrize("category", ["A", "B", "C", "D", "E"])
        @given(value=integers())
        def test_with_hypothesis(category, value):
            assert value is not None
        """
        # No PBT hint when already using hypothesis
        # Note: decorators are visited in order, line 6 is @pytest.mark.parametrize
        self.assert_adds_messages(
            code,
            msg("pytest-bdd-missing-scenario", line=6),
        )

    def test_no_parametrize_no_hint(self):
        """Test without parametrize should not trigger W9017."""
        code = """
        def test_simple():
            assert 1 + 1 == 2
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=3),  # 2 is magic
            msg("pytest-bdd-missing-scenario", line=2),
        )


class TestW9018_DesignByContractHint(PytestDeepAnalysisTestCase):
    """Tests for W9018: pytest-no-contract-hint.

    Note: W9018 is checked in the close() method and requires the full
    fixture graph to be built. These tests verify the detection logic works.
    """

    def test_simple_fixture_no_hint(self):
        """Simple fixture should not trigger W9018."""
        code = """
        import pytest

        @pytest.fixture
        def simple_value():
            return 42
        """
        # No contract hint for simple fixtures
        self.assert_no_messages(code)

    def test_fixture_with_icontract_no_hint(self):
        """Fixture with icontract should not trigger W9018."""
        code = """
        import pytest
        from icontract import require, ensure

        @pytest.fixture
        @require(lambda: True)
        @ensure(lambda result: result is not None)
        def database_connection():
            connection = create_connection()
            connection.execute("BEGIN")
            cursor = connection.cursor()
            connection.commit()
            yield connection
            connection.rollback()
            connection.close()
        """
        # No hint when contract decorators present
        self.assert_no_messages(code)


class TestSemanticQualityCombinations(PytestDeepAnalysisTestCase):
    """Test combinations of semantic quality checks."""

    def test_perfect_test_no_warnings(self):
        """Test following all best practices should have minimal warnings."""
        code = '''
        import pytest
        from hypothesis import given
        from hypothesis.strategies import integers

        @pytest.mark.scenario("calculator.feature", "Addition")
        @given(a=integers(), b=integers())
        def test_addition_commutative(a, b):
            """
            Given two integers a and b
            When we add them in either order
            Then the result should be the same
            """
            assert a + b == b + a
        '''
        # Perfect test: has BDD marker, uses PBT, has assertions
        self.assert_no_messages(code)

    def test_multiple_violations(self):
        """Test with multiple violations should trigger multiple messages."""
        code = """
        def test_bad_example():
            x = 1 + 1
            print(x)
        """
        self.assert_adds_messages(
            code,
            msg("pytest-test-no-assert", line=2),
            msg("pytest-bdd-missing-scenario", line=2),
        )

    def test_mock_with_raises_acceptable(self):
        """Mock verification with pytest.raises is acceptable but still warns.

        Even though pytest.raises makes the test valid (not assertion-free),
        having ONLY mock verifications without state assertions still triggers
        the mock-only-verify warning, which is working as designed.
        """
        code = """
        import pytest

        @pytest.mark.scenario("error_handling.feature", "Invalid input")
        def test_error_handling(mock_validator):
            with pytest.raises(ValueError):
                mock_validator.validate("bad")
            mock_validator.validate.assert_called_once_with("bad")
        """
        # Has BDD marker and pytest.raises (no E9014), but still has mock-only verify (W9015)
        # Line 4 is where @pytest.mark.scenario starts (decorator), which is where visit_functiondef reports
        self.assert_adds_messages(
            code,
            msg("pytest-mock-only-verify", line=4),
        )
