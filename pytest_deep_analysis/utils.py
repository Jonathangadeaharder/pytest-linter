"""
Utility functions for pytest-deep-analysis checker.
"""

import ast
from typing import Optional, Set, List, Any, Tuple

from astroid import nodes


def is_test_function(node: nodes.FunctionDef) -> bool:
    """Check if a function is a pytest test function.

    Args:
        node: The function definition node

    Returns:
        True if the function is a test function (name starts with 'test_')
    """
    return bool(node.name.startswith("test_"))


def is_pytest_fixture(node: nodes.FunctionDef) -> bool:
    """Check if a function is decorated with @pytest.fixture.

    Args:
        node: The function definition node

    Returns:
        True if the function has a pytest.fixture decorator
    """
    if not node.decorators:
        return False

    for decorator in node.decorators.nodes:
        # Handle both @pytest.fixture and @pytest.fixture(...)
        if isinstance(decorator, nodes.Name):
            if decorator.name == "fixture":
                return True
        elif isinstance(decorator, nodes.Attribute):
            if decorator.attrname == "fixture":
                return True
        elif isinstance(decorator, nodes.Call):
            func = decorator.func
            if isinstance(func, nodes.Name) and func.name == "fixture":
                return True
            elif isinstance(func, nodes.Attribute) and func.attrname == "fixture":
                return True

    return False


def get_fixture_decorator_args(
    node: nodes.FunctionDef,
) -> Tuple[str, bool]:
    """Extract scope and autouse parameters from a @pytest.fixture decorator.

    Args:
        node: The fixture function definition node

    Returns:
        Tuple of (scope, autouse) with defaults ('function', False)
    """
    scope = "function"
    autouse = False

    if not node.decorators:
        return scope, autouse

    for decorator in node.decorators.nodes:
        # Only process Call nodes (e.g., @pytest.fixture(...))
        if not isinstance(decorator, nodes.Call):
            continue

        # Check if it's a pytest.fixture call
        func = decorator.func
        is_fixture_call = False
        if isinstance(func, nodes.Name) and func.name == "fixture":
            is_fixture_call = True
        elif isinstance(func, nodes.Attribute) and func.attrname == "fixture":
            is_fixture_call = True

        if not is_fixture_call:
            continue

        # Extract keyword arguments
        if decorator.keywords:
            for keyword in decorator.keywords:
                if keyword.arg == "scope":
                    try:
                        # Get the scope value
                        if isinstance(keyword.value, nodes.Const):
                            scope = keyword.value.value
                    except Exception:
                        pass
                elif keyword.arg == "autouse":
                    try:
                        if isinstance(keyword.value, nodes.Const):
                            autouse = keyword.value.value
                    except Exception:
                        pass

    return scope, autouse


def get_fixture_dependencies(node: nodes.FunctionDef) -> List[str]:
    """Extract the list of fixture dependencies from a fixture's arguments.

    Args:
        node: The fixture function definition node

    Returns:
        List of fixture names that this fixture depends on
    """
    dependencies = []

    if node.args and node.args.args:
        for arg in node.args.args:
            # Skip special pytest fixtures
            if arg.name not in {"request", "self", "cls"}:
                dependencies.append(arg.name)

    return dependencies


def is_in_context_manager(node: nodes.NodeNG, context_name: str) -> bool:
    """Check if a node is inside a specific context manager.

    Args:
        node: The node to check
        context_name: The name of the context manager (e.g., 'pytest.raises')

    Returns:
        True if the node is inside the specified context manager
    """
    current = node.parent
    while current:
        if isinstance(current, nodes.With):
            for item in current.items:
                context_expr = item[0]
                # Check if it's pytest.raises or similar
                if isinstance(context_expr, nodes.Call):
                    func = context_expr.func
                    if isinstance(func, nodes.Attribute):
                        if func.attrname in context_name:
                            return True
        current = current.parent
    return False


def is_in_comprehension(node: nodes.NodeNG) -> bool:
    """Check if a node is inside a list/dict/set comprehension.

    Args:
        node: The node to check

    Returns:
        True if the node is inside a comprehension
    """
    current = node.parent
    while current:
        if isinstance(current, (nodes.ListComp, nodes.DictComp, nodes.SetComp)):
            return True
        current = current.parent
    return False


def is_magic_constant(value: Any) -> bool:
    """Check if a constant value is a 'magic' value that should be extracted.

    This function uses the global configuration to determine which values
    are considered "non-magic" (allowed in assertions without extraction).

    Args:
        value: The constant value to check

    Returns:
        True if the value is a magic constant
    """
    from pytest_deep_analysis.config import get_config

    config = get_config()
    return config.is_magic_constant(value)


def get_call_qualname(node: nodes.Call) -> Optional[str]:
    """Get the fully qualified name of a function call.

    Args:
        node: The call node

    Returns:
        The qualified name (e.g., 'time.sleep') or None
    """
    func = node.func

    if isinstance(func, nodes.Name):
        return str(func.name) if func.name else None
    elif isinstance(func, nodes.Attribute):
        # Try to build the qualified name
        parts = [str(func.attrname)]
        current = func.expr
        while current:
            if isinstance(current, nodes.Name):
                parts.append(str(current.name))
                break
            elif isinstance(current, nodes.Attribute):
                parts.append(str(current.attrname))
                current = current.expr
            else:
                break
        return ".".join(reversed(parts))

    return None


SCOPE_ORDER = {
    "function": 1,
    "class": 2,
    "module": 3,
    "package": 4,
    "session": 5,
}


def compare_fixture_scopes(scope1: str, scope2: str) -> int:
    """Compare two fixture scopes.

    Args:
        scope1: First scope
        scope2: Second scope

    Returns:
        Negative if scope1 < scope2, 0 if equal, positive if scope1 > scope2
    """
    val1 = SCOPE_ORDER.get(scope1, 1)
    val2 = SCOPE_ORDER.get(scope2, 1)
    return val1 - val2
