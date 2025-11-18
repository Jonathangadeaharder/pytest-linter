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


def _is_fixture_decorator(decorator: nodes.NodeNG) -> bool:
    """Check if decorator is a pytest.fixture call.

    Args:
        decorator: The decorator node

    Returns:
        True if it's a pytest.fixture decorator
    """
    if not isinstance(decorator, nodes.Call):
        return False

    func = decorator.func
    if isinstance(func, nodes.Name):
        return func.name == "fixture"
    if isinstance(func, nodes.Attribute):
        return func.attrname == "fixture"
    return False


def _extract_scope_from_keyword(keyword: nodes.Keyword) -> Optional[str]:
    """Extract scope value from keyword argument.

    Args:
        keyword: The keyword node

    Returns:
        Scope value or None
    """
    if keyword.arg != "scope":
        return None
    try:
        if isinstance(keyword.value, nodes.Const):
            return keyword.value.value
    except Exception:
        # If keyword.value is not a constant or cannot be evaluated, ignore and return None.
        pass
    return None


def _extract_autouse_from_keyword(keyword: nodes.Keyword) -> Optional[bool]:
    """Extract autouse value from keyword argument.

    Args:
        keyword: The keyword node

    Returns:
        Autouse value or None
    """
    if keyword.arg != "autouse":
        return None
    try:
        if isinstance(keyword.value, nodes.Const):
            return keyword.value.value
    except Exception:
        # If keyword.value is not a constant or cannot be evaluated, ignore and return None.
        pass
    return None


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
        if not _is_fixture_decorator(decorator):
            continue

        # Extract keyword arguments
        if decorator.keywords:
            for keyword in decorator.keywords:
                extracted_scope = _extract_scope_from_keyword(keyword)
                if extracted_scope is not None:
                    scope = extracted_scope

                extracted_autouse = _extract_autouse_from_keyword(keyword)
                if extracted_autouse is not None:
                    autouse = extracted_autouse

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


def has_parametrize_decorator(node: nodes.FunctionDef) -> bool:
    """Check if a function has @pytest.mark.parametrize decorator.

    Args:
        node: The function definition node

    Returns:
        True if the function has a parametrize decorator
    """
    if not node.decorators:
        return False

    for decorator in node.decorators.nodes:
        if isinstance(decorator, nodes.Call):
            func = decorator.func
            # Check for pytest.mark.parametrize
            if isinstance(func, nodes.Attribute):
                if func.attrname == "parametrize":
                    # Check if it's pytest.mark.parametrize
                    if isinstance(func.expr, nodes.Attribute) and func.expr.attrname == "mark":
                        return True
    return False


def get_parametrize_decorators(node: nodes.FunctionDef) -> List[nodes.Call]:
    """Get all parametrize decorators from a function.

    Args:
        node: The function definition node

    Returns:
        List of parametrize decorator call nodes
    """
    parametrize_decorators = []

    if not node.decorators:
        return parametrize_decorators

    for decorator in node.decorators.nodes:
        if isinstance(decorator, nodes.Call):
            func = decorator.func
            if isinstance(func, nodes.Attribute):
                if func.attrname == "parametrize":
                    if isinstance(func.expr, nodes.Attribute) and func.expr.attrname == "mark":
                        parametrize_decorators.append(decorator)

    return parametrize_decorators


def is_mutation_operation(node: nodes.NodeNG) -> bool:
    """Check if a node represents a mutation operation.

    Args:
        node: The node to check

    Returns:
        True if the node is a mutation operation
    """
    # Check for augmented assignments (+=, -=, etc.)
    if isinstance(node, nodes.AugAssign):
        return True

    # Check for direct attribute/subscript assignments
    if isinstance(node, nodes.Assign):
        for target in node.targets:
            if isinstance(target, (nodes.Attribute, nodes.Subscript)):
                return True

    # Check for mutating method calls (append, extend, pop, etc.)
    if isinstance(node, nodes.Call):
        func = node.func
        if isinstance(func, nodes.Attribute):
            mutating_methods = {
                'append', 'extend', 'insert', 'remove', 'pop', 'clear',
                'update', 'add', 'discard', 'setdefault'
            }
            if func.attrname in mutating_methods:
                return True

    return False


def has_database_operations(node: nodes.NodeNG) -> bool:
    """Check if a node contains database operations.

    Args:
        node: The node to check

    Returns:
        True if database operations are detected
    """
    # Database-related method calls
    db_methods = {
        'commit', 'execute', 'executemany', 'bulk_create',
        'bulk_update', 'save', 'delete', 'create', 'update_or_create'
    }

    if isinstance(node, nodes.Call):
        qualname = get_call_qualname(node)
        if qualname:
            # Check if it's a database method
            method_name = qualname.split('.')[-1]
            if method_name in db_methods:
                return True

    return False
