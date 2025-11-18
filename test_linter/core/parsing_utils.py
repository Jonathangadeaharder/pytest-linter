"""Shared parsing utilities for language adapters."""

from typing import Optional


def extract_brace_delimited_body(
    content: str, start_pos: int, opening_char: str = "{", closing_char: str = "}"
) -> str:
    """Extract body delimited by braces with string-awareness.

    This function correctly handles:
    - String literals containing braces
    - Escaped characters within strings
    - Nested braces outside of strings

    Args:
        content: The source code content
        start_pos: Position to start searching (should be at or before opening brace)
        opening_char: Opening delimiter (default: '{')
        closing_char: Closing delimiter (default: '}')

    Returns:
        The extracted body including delimiters, or empty string if not found

    Example:
        >>> code = 'func test() { s := "{ not a brace }"; return s }'
        >>> extract_brace_delimited_body(code, code.find('{'))
        '{ s := "{ not a brace }"; return s }'
    """
    # Find the opening brace if we're not already at it
    if start_pos >= len(content):
        return ""

    brace_start = start_pos
    if content[start_pos] != opening_char:
        brace_start = content.find(opening_char, start_pos)
        if brace_start == -1:
            return ""

    depth = 0
    in_string = False
    in_char = False
    escape_next = False
    in_line_comment = False
    in_block_comment = False

    i = brace_start
    while i < len(content):
        char = content[i]

        # Handle escape sequences
        if escape_next:
            escape_next = False
            i += 1
            continue

        # Check for escape character (but only in strings/chars)
        if (in_string or in_char) and char == "\\":
            escape_next = True
            i += 1
            continue

        # Handle C-style line comments (// ...)
        if not in_string and not in_char and i + 1 < len(content):
            if content[i : i + 2] == "//":
                in_line_comment = True
                i += 2
                continue

        # End line comment
        if in_line_comment and char == "\n":
            in_line_comment = False
            i += 1
            continue

        # Handle C-style block comments (/* ... */)
        if (
            not in_string
            and not in_char
            and not in_line_comment
            and i + 1 < len(content)
        ):
            if content[i : i + 2] == "/*":
                in_block_comment = True
                i += 2
                continue
            if in_block_comment and content[i : i + 2] == "*/":
                in_block_comment = False
                i += 2
                continue

        # Skip if in comment
        if in_line_comment or in_block_comment:
            i += 1
            continue

        # Toggle string state (double quotes)
        if char == '"' and not in_char:
            in_string = not in_string
            i += 1
            continue

        # Toggle char state (single quotes) - for languages that distinguish
        if char == "'" and not in_string:
            in_char = not in_char
            i += 1
            continue

        # Only count braces outside of strings, chars, and comments
        if not in_string and not in_char:
            if char == opening_char:
                depth += 1
            elif char == closing_char:
                depth -= 1
                if depth == 0:
                    return content[brace_start : i + 1]

        i += 1

    return ""


def extract_indented_body_vbnet(content: str, start_pos: int, method_type: str) -> str:
    """Extract VB.NET function body (uses End Sub/End Function instead of braces).

    Args:
        content: The source code content
        start_pos: Position after the function signature
        method_type: "Sub" or "Function"

    Returns:
        The extracted body up to End Sub/End Function
    """
    import re

    # VB.NET functions end with "End Sub" or "End Function"
    end_pattern = rf"\bEnd\s+{method_type}\b"

    # Find the end of the function
    match = re.search(end_pattern, content[start_pos:], re.IGNORECASE)
    if match:
        return content[start_pos : start_pos + match.end()]

    return ""


def extract_until_keywords(
    content: str, start_pos: int, end_keywords: list[str], case_sensitive: bool = True
) -> str:
    """Extract content until one of the specified keywords is found.

    Useful for languages like Python that use indentation/keywords instead of braces.

    Args:
        content: The source code content
        start_pos: Position to start from
        end_keywords: List of keywords that mark the end (e.g., ['def', 'class'])
        case_sensitive: Whether keyword matching is case-sensitive

    Returns:
        Extracted content up to (but not including) the end keyword
    """
    import re

    flags = 0 if case_sensitive else re.IGNORECASE

    # Create pattern to match any of the keywords at the beginning of a line
    keyword_pattern = r"^\s*(" + "|".join(re.escape(k) for k in end_keywords) + r")\b"

    lines = content[start_pos:].split("\n")
    result_lines = []

    for line in lines:
        if re.match(keyword_pattern, line, flags):
            break
        result_lines.append(line)

    return "\n".join(result_lines)
