"""
Execution trace collectors for runtime semantic validation.

This module provides low-level tracing capabilities to capture test execution
details that cannot be determined statically.
"""

import sys
import inspect
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
import threading


@dataclass
class FunctionCallTrace:
    """Trace of a single function call."""
    function_name: str
    module: str
    args: tuple
    kwargs: dict
    return_value: Any = None
    exception: Optional[Exception] = None
    lineno: int = 0


class ExecutionTraceCollector:
    """
    Collects execution traces during test runs using sys.settrace().

    This provides the runtime data needed for semantic validation:
    - Which functions were called (for BDD step matching)
    - What assertions executed (for coverage analysis)
    - Which exceptions were raised (for pytest.raises validation)
    """

    def __init__(self):
        self.active = False
        self.traces: List[FunctionCallTrace] = []
        self.current_context = None
        self.original_trace = None

        # Thread-local storage for nested calls
        self._local = threading.local()

    def start_trace(self, context):
        """Start collecting execution traces for a test."""
        self.current_context = context
        self.traces = []
        self.active = True

        # Install trace function
        self.original_trace = sys.gettrace()
        sys.settrace(self._trace_calls)

    def stop_trace(self):
        """Stop collecting execution traces."""
        self.active = False
        sys.settrace(self.original_trace)

        # Store traces in context
        if self.current_context:
            self.current_context.function_calls = [
                {
                    "name": t.function_name,
                    "module": t.module,
                    "line": t.lineno
                }
                for t in self.traces
            ]

    def _trace_calls(self, frame, event, arg):
        """Trace function called by sys.settrace()."""
        if not self.active:
            return None

        # Only trace events we care about
        if event not in ("call", "return", "exception"):
            return self._trace_calls

        code = frame.f_code
        func_name = code.co_name
        module = frame.f_globals.get("__name__", "")
        lineno = frame.f_lineno

        # Skip internal pytest/plugin code
        if any(skip in module for skip in ["pytest", "_pytest", "pluggy", "pytest_deep_analysis.runtime"]):
            return self._trace_calls

        # Capture call events
        if event == "call":
            trace = FunctionCallTrace(
                function_name=func_name,
                module=module,
                args=(),  # Simplified for now
                kwargs={},
                lineno=lineno
            )
            self.traces.append(trace)

        # Capture assertions (look for assert statement execution)
        # Note: Python doesn't have a direct "assert" event, but we can infer from AssertionError
        elif event == "exception":
            exc_type, exc_value, exc_tb = arg
            if self.current_context:
                self.current_context.exceptions_raised.append(exc_value)

                # Track assertion failures
                if isinstance(exc_value, AssertionError):
                    if not hasattr(self._local, "assertion_count"):
                        self._local.assertion_count = 0
                    self._local.assertion_count += 1

        return self._trace_calls


class AssertionCounter:
    """
    Lightweight assertion counter using bytecode inspection.

    Alternative to sys.settrace() for counting assertions without
    the performance overhead of full tracing.
    """

    @staticmethod
    def count_assertions_in_function(func: Callable) -> int:
        """
        Count assert statements in a function's bytecode.

        This provides a static count, complementing runtime detection.
        """
        import dis

        count = 0
        try:
            instructions = list(dis.get_instructions(func))
            for instr in instructions:
                # LOAD_ASSERTION_ERROR indicates an assert statement
                if instr.opname == "LOAD_ASSERTION_ERROR":
                    count += 1
        except (AttributeError, TypeError):
            pass

        return count

    @staticmethod
    def detect_pytest_raises(func: Callable) -> bool:
        """
        Detect if a function uses pytest.raises() by inspecting bytecode.
        """
        import dis

        try:
            instructions = list(dis.get_instructions(func))
            for instr in instructions:
                # Look for LOAD_ATTR 'raises' followed by CALL
                if instr.opname == "LOAD_ATTR" and instr.argval == "raises":
                    return True
        except (AttributeError, TypeError):
            pass

        return False


class MockVerificationDetector:
    """
    Detects mock verification calls at runtime.

    Complements static W9015 (pytest-mock-only-verify) by actually
    tracking which mock methods were called during test execution.
    """

    MOCK_VERIFY_METHODS = {
        "assert_called",
        "assert_called_once",
        "assert_called_with",
        "assert_called_once_with",
        "assert_any_call",
        "assert_has_calls",
        "assert_not_called"
    }

    def __init__(self):
        self.mock_calls_detected = []

    def detect_in_trace(self, traces: List[FunctionCallTrace]) -> List[str]:
        """Detect mock verification calls in execution traces."""
        mock_verifications = []

        for trace in traces:
            if trace.function_name in self.MOCK_VERIFY_METHODS:
                mock_verifications.append(f"{trace.module}.{trace.function_name}")

        return mock_verifications
