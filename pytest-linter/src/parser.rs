use crate::models::{Fixture, FixtureScope, ParsedModule, TestFunction};
use anyhow::Result;
use std::path::Path;
use tree_sitter::Parser;

struct DecoratorInfo<'a> {
    text: String,
    node: Option<tree_sitter::Node<'a>>,
}

pub struct PythonParser {
    parser: Parser,
}

impl PythonParser {
    #[allow(clippy::missing_errors_doc)]
    pub fn new() -> Result<Self> {
        let mut parser = Parser::new();
        parser.set_language(&tree_sitter_python::LANGUAGE.into())?;
        Ok(Self { parser })
    }

    #[allow(clippy::missing_errors_doc)]
    pub fn parse_file(&mut self, path: &Path) -> Result<ParsedModule> {
        let source = std::fs::read_to_string(path)?;
        let tree = self.parser.parse(&source, None);
        let file_path = path.to_path_buf();

        if let Some(tree) = tree {
            let root = tree.root_node();
            let source_bytes = source.as_bytes();
            let imports = Self::extract_imports(&root, source_bytes);
            let test_functions = Self::extract_test_functions(&root, source_bytes, &file_path);
            let fixtures = Self::extract_fixtures(&root, source_bytes, &file_path);
            Ok(ParsedModule {
                file_path,
                imports,
                test_functions,
                fixtures,
            })
        } else {
            eprintln!("Warning: tree-sitter failed to parse {}", file_path.display());
            Ok(ParsedModule {
                file_path,
                imports: vec![],
                test_functions: vec![],
                fixtures: vec![],
            })
        }
    }

    fn node_text(node: tree_sitter::Node, source: &[u8]) -> String {
        node.utf8_text(source).unwrap_or_default().to_string()
    }

    fn extract_imports(root: &tree_sitter::Node, source: &[u8]) -> Vec<String> {
        let mut imports = Vec::new();
        let mut cursor = root.walk();

        for child in root.children(&mut cursor) {
            match child.kind() {
                "import_statement" | "import_from_statement" => {
                    imports.push(Self::node_text(child, source));
                }
                _ => {}
            }
        }
        imports
    }

    fn collect_function_nodes<'a>(
        root: &'a tree_sitter::Node<'a>,
    ) -> Vec<tree_sitter::Node<'a>> {
        let mut nodes = Vec::new();
        let mut cursor = root.walk();
        for child in root.children(&mut cursor) {
            match child.kind() {
                "function_definition" => {
                    nodes.push(child);
                }
                "decorated_definition" => {
                    let mut inner = child.walk();
                    for c in child.children(&mut inner) {
                        if c.kind() == "function_definition" {
                            nodes.push(c);
                        }
                    }
                }
                _ => {}
            }
        }
        nodes
    }

    fn extract_test_functions(
        root: &tree_sitter::Node,
        source: &[u8],
        file_path: &Path,
    ) -> Vec<TestFunction> {
        let mut tests = Vec::new();
        for func_node in Self::collect_function_nodes(root) {
            let name_node = func_node.child_by_field_name("name");
            if let Some(nn) = name_node {
                let name = Self::node_text(nn, source);
                if name.starts_with("test_") {
                    tests.push(Self::build_test_function(
                        &func_node,
                        source,
                        file_path,
                        &name,
                    ));
                }
            }
        }
        tests
    }

    fn build_test_function(
        func_node: &tree_sitter::Node,
        source: &[u8],
        file_path: &Path,
        name: &str,
    ) -> TestFunction {
        let line = func_node.start_position().row + 1;
        let body = func_node.child_by_field_name("body");
        let body_text = body
            .map(|b| Self::node_text(b, source))
            .unwrap_or_default();

        let decorators = Self::get_decorators(func_node, source);

        let is_async = {
            let mut cur = func_node.walk();
            let has_async = func_node
                .children(&mut cur)
                .any(|c| c.kind() == "async");
            drop(cur);
            has_async
        };
        let (is_parametrized, parametrize_count) = Self::detect_parametrize(&decorators);
        let has_assertions = body_text.contains("assert ") || body_text.contains("assert(");
        let assertion_count = Self::count_assertions(body.as_ref());
        let has_mock_verifications = body_text.contains(".assert_called")
            || body_text.contains(".called")
            || body_text.contains(".call_count");
        let has_state_assertions = has_assertions && !has_mock_verifications_only(&body_text);
        let fixture_deps = Self::extract_fixture_deps(func_node, source);
        let uses_time_sleep = body_text.contains("time.sleep") || body_text.contains("sleep(");
        let uses_file_io = body_text.contains("open(")
            || body_text.contains("open (")
            || body_text.contains(".read()")
            || body_text.contains(".write(")
            || body_text.contains(".open(");
        let uses_network = body_text.contains("requests.")
            || body_text.contains("socket.")
            || body_text.contains("httpx.")
            || body_text.contains("aiohttp.")
            || body_text.contains("urllib");
        let has_conditional_logic = Self::detect_conditionals(body.as_ref());
        let has_try_except = Self::detect_try_except(body.as_ref());
        let docstring = Self::extract_docstring(func_node, source);
        let assertions = Self::extract_assertions(body.as_ref(), source);

        TestFunction {
            name: name.to_string(),
            file_path: file_path.to_path_buf(),
            line,
            is_async,
            is_parametrized,
            parametrize_count,
            has_assertions,
            assertion_count,
            has_mock_verifications,
            has_state_assertions,
            fixture_deps,
            uses_time_sleep,
            uses_file_io,
            uses_network,
            has_conditional_logic,
            has_try_except,
            docstring,
            assertions,
            parametrize_values: vec![],
            uses_cwd_dependency: false,
            uses_pytest_raises: false,
            mutates_fixture_deps: vec![],
        }
    }

    fn get_decorators<'a>(func_node: &tree_sitter::Node<'a>, source: &[u8]) -> Vec<DecoratorInfo<'a>> {
        let mut decs = Vec::new();
        let parent = func_node.parent();
        let container = if parent.is_some_and(|p| p.kind() == "decorated_definition") {
            parent.unwrap()
        } else {
            *func_node
        };
        let mut cursor = container.walk();
        for child in container.children(&mut cursor) {
            if child.kind() == "decorator" {
                decs.push(DecoratorInfo {
                    text: Self::node_text(child, source),
                    node: Some(child),
                });
            }
        }
        decs
    }

    fn detect_parametrize(decorators: &[DecoratorInfo]) -> (bool, Option<usize>) {
        for dec in decorators {
            if dec.text.contains("parametrize") || dec.text.contains("pytest.mark.parametrize") {
                let count = dec.node.map_or_else(
                    || Self::count_parametrize_args(&dec.text),
                    |node| {
                        Self::count_parametrize_args_ast(node)
                            .unwrap_or_else(|| Self::count_parametrize_args(&dec.text))
                    },
                );
                return (true, Some(count));
            }
        }
        (false, None)
    }

    fn count_parametrize_args_ast(decorator_node: tree_sitter::Node) -> Option<usize> {
        let mut cursor = decorator_node.walk();
        for child in decorator_node.children(&mut cursor) {
            if child.kind() == "call" {
                let mut call_cursor = child.walk();
                for call_child in child.children(&mut call_cursor) {
                    if call_child.kind() == "argument_list" {
                        let mut args_cursor = call_child.walk();
                        for arg in call_child.children(&mut args_cursor) {
                            if arg.kind() == "list" || arg.kind() == "tuple" {
                                let mut elem_count = 0;
                                let mut elem_cursor = arg.walk();
                                let mut found_comma = false;
                                for elem in arg.children(&mut elem_cursor) {
                                    match elem.kind() {
                                        "," => { found_comma = true; }
                                        "(" | ")" | "[" | "]" | "comment" => {}
                                        _ if !elem.is_extra() => { elem_count += 1; }
                                        _ => {}
                                    }
                                }
                                if elem_count == 0 && !found_comma {
                                    return Some(0);
                                }
                                return Some(elem_count.max(1));
                            }
                        }
                    }
                }
            }
        }
        None
    }

    fn count_parametrize_args(dec: &str) -> usize {
        if let Some(start) = dec.rfind('[') {
            if let Some(end) = dec.rfind(']') {
                if end > start {
                    let inner = &dec[start + 1..end];
                    let depth_brace = Self::count_top_level_entries(inner);
                    return depth_brace;
                }
            }
        }
        let open = dec.matches('(').count();
        if open > 1 {
            return 2;
        }
        1
    }

    fn count_top_level_entries(inner: &str) -> usize {
        let mut count = 0;
        let mut depth = 0;
        let mut quote_char: Option<char> = None;
        let mut escape = false;
        let mut has_content_since_last_comma = false;

        for c in inner.chars() {
            if escape {
                escape = false;
                has_content_since_last_comma = true;
                continue;
            }
            if c == '\\' {
                escape = true;
                has_content_since_last_comma = true;
                continue;
            }
            if let Some(qc) = quote_char {
                if c == qc {
                    quote_char = None;
                }
                has_content_since_last_comma = true;
                continue;
            }
            match c {
                '"' | '\'' => {
                    quote_char = Some(c);
                    has_content_since_last_comma = true;
                }
                '(' | '[' | '{' => {
                    depth += 1;
                    has_content_since_last_comma = true;
                }
                ')' | ']' | '}' if depth > 0 => {
                    depth -= 1;
                    has_content_since_last_comma = true;
                }
                ',' if depth == 0 => {
                    if has_content_since_last_comma {
                        count += 1;
                    }
                    has_content_since_last_comma = false;
                }
                _ => {
                    if !c.is_whitespace() {
                        has_content_since_last_comma = true;
                    }
                }
            }
        }
        if has_content_since_last_comma {
            count += 1;
        }
        count
    }

    fn count_assertions(body: Option<&tree_sitter::Node>) -> usize {
        body.map_or(0, |b| {
            let mut count = 0;
            Self::count_assertions_recursive(*b, &mut count);
            count
        })
    }

    fn count_assertions_recursive(node: tree_sitter::Node, count: &mut usize) {
        if node.kind() == "assert_statement" {
            *count += 1;
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            Self::count_assertions_recursive(child, count);
        }
    }

    fn detect_conditionals(body: Option<&tree_sitter::Node>) -> bool {
        body.is_some_and(|b| Self::has_node_kind(*b, "if_statement"))
    }

    fn detect_try_except(body: Option<&tree_sitter::Node>) -> bool {
        body.is_some_and(|b| Self::has_node_kind(*b, "try_statement"))
    }

    fn has_node_kind(node: tree_sitter::Node, kind: &str) -> bool {
        if node.kind() == kind {
            return true;
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_node_kind(child, kind) {
                return true;
            }
        }
        false
    }

    fn extract_assertions(body: Option<&tree_sitter::Node>, source: &[u8]) -> Vec<crate::models::AssertionInfo> {
        body.map_or(vec![], |b| {
            let mut infos = Vec::new();
            Self::collect_assertion_info(*b, source, &mut infos);
            infos
        })
    }

    fn collect_assertion_info(
        node: tree_sitter::Node,
        source: &[u8],
        infos: &mut Vec<crate::models::AssertionInfo>,
    ) {
        if node.kind() == "assert_statement" {
            let line = node.start_position().row + 1;
            let mut cursor = node.walk();
            let children: Vec<_> = node.children(&mut cursor).collect();
            let expr_node = children.into_iter().find(|c| {
                let k = c.kind();
                !k.starts_with(',') && k != "comment" && k != "assert"
            });
            let expression_text = expr_node
                .map(|n| Self::node_text(n, source))
                .unwrap_or_default();
            let has_comparison = expr_node.is_some_and(|n| {
                Self::has_node_kind_recursive(n, "comparison_operator")
            });
            let is_magic = expr_node.is_some_and(|n| {
                let kind = n.kind();
                if kind == "true" || kind == "false" {
                    return true;
                }
                if kind == "integer" {
                    let text = Self::node_text(n, source);
                    return text == "0" || text == "1";
                }
                !has_comparison && kind == "identifier"
            });
            let is_suboptimal = expr_node.is_some_and(|n| {
                Self::is_suboptimal_assertion(n, source)
            });
            infos.push(crate::models::AssertionInfo {
                is_magic,
                is_suboptimal,
                has_comparison,
                expression_text,
                line,
            });
            return;
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            Self::collect_assertion_info(child, source, infos);
        }
    }

    fn has_node_kind_recursive(node: tree_sitter::Node, kind: &str) -> bool {
        if node.kind() == kind {
            return true;
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_node_kind_recursive(child, kind) {
                return true;
            }
        }
        false
    }

    fn is_suboptimal_assertion(expr: tree_sitter::Node, source: &[u8]) -> bool {
        if expr.kind() == "comparison_operator" {
            let mut cursor = expr.walk();
            for child in expr.children(&mut cursor) {
                if child.kind() == "call" {
                    let func = child.child_by_field_name("function");
                    if let Some(f) = func {
                        let name = Self::node_text(f, source);
                        if name == "len" || name == "type" {
                            return true;
                        }
                    }
                }
                if child.kind() == "not" {
                    let mut nc = child.walk();
                    for inner in child.children(&mut nc) {
                        if inner.kind() == "none" {
                            return true;
                        }
                    }
                }
                if child.kind() == "none" {
                    let text = Self::node_text(expr, source);
                    if text.contains("not") {
                        return true;
                    }
                }
            }
        }
        false
    }

    fn extract_docstring(
        func_node: &tree_sitter::Node,
        source: &[u8],
    ) -> Option<String> {
        let body = func_node.child_by_field_name("body")?;
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            if child.kind() == "expression_statement" {
                let mut inner_cursor = child.walk();
                for expr in child.children(&mut inner_cursor) {
                    if expr.kind() == "string" {
                        return Some(Self::node_text(expr, source));
                    }
                }
            }
        }
        None
    }

    fn extract_fixture_deps(
        func_node: &tree_sitter::Node,
        source: &[u8],
    ) -> Vec<String> {
        let mut deps = Vec::new();
        let params = func_node.child_by_field_name("parameters");
        if let Some(p) = params {
            let mut cursor = p.walk();
            for child in p.children(&mut cursor) {
                if child.kind() == "identifier" {
                    let name = Self::node_text(child, source);
                    if !["self", "cls"].contains(&name.as_str()) {
                        deps.push(name);
                    }
                }
            }
        }
        deps
    }

    fn extract_fixtures(
        root: &tree_sitter::Node,
        source: &[u8],
        file_path: &Path,
    ) -> Vec<Fixture> {
        let mut fixtures = Vec::new();

        for func_node in Self::collect_function_nodes(root) {
            let decorators = Self::get_decorators(&func_node, source);
            let is_fixture = decorators.iter().any(|d| {
                d.text.contains("pytest.fixture") || d.text.contains("@fixture")
            });

            if is_fixture {
                let name_node = func_node.child_by_field_name("name");
                if let Some(nn) = name_node {
                    let name = Self::node_text(nn, source);
                    let dec_texts: Vec<String> = decorators.iter().map(|d| d.text.clone()).collect();
                    fixtures.push(Self::build_fixture(
                        &func_node, source, file_path, &name, &dec_texts,
                    ));
                }
            }
        }
        fixtures
    }

    fn build_fixture(
        func_node: &tree_sitter::Node,
        source: &[u8],
        file_path: &Path,
        name: &str,
        decorators: &[String],
    ) -> Fixture {
        let line = func_node.start_position().row + 1;
        let body = func_node.child_by_field_name("body");
        let body_text = body
            .map(|b| Self::node_text(b, source))
            .unwrap_or_default();

        let scope = Self::extract_fixture_scope(decorators);
        let is_autouse = decorators.iter().any(|d| d.contains("autouse") && d.contains("True"));
        let dependencies = Self::extract_fixture_deps(func_node, source);
        let returns_mutable = Self::detect_mutable_return(body.as_ref(), source);
        let has_yield = body_text.contains("yield");
        let has_db_commit = body_text.contains("commit()")
            || body_text.contains(".commit")
            || body_text.contains("COMMIT");
        let has_db_rollback = body_text.contains("rollback()")
            || body_text.contains(".rollback")
            || body_text.contains("ROLLBACK");
        let uses_file_io = Self::detect_file_io(body.as_ref(), source);

        Fixture {
            name: name.to_string(),
            file_path: file_path.to_path_buf(),
            line,
            scope,
            is_autouse,
            dependencies,
            returns_mutable,
            has_yield,
            has_db_commit,
            has_db_rollback,
            uses_file_io,
            used_by: vec![],
        }
    }

    fn extract_fixture_scope(decorators: &[String]) -> FixtureScope {
        for dec in decorators {
            if dec.contains("scope") {
                if dec.contains("\"session\"") || dec.contains("'session'") {
                    return FixtureScope::Session;
                }
                if dec.contains("\"package\"") || dec.contains("'package'") {
                    return FixtureScope::Package;
                }
                if dec.contains("\"module\"") || dec.contains("'module'") {
                    return FixtureScope::Module;
                }
                if dec.contains("\"class\"") || dec.contains("'class'") {
                    return FixtureScope::Class;
                }
            }
        }
        FixtureScope::Function
    }

    fn detect_file_io(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_file_io_call(*b, source))
    }

    fn has_file_io_call(node: tree_sitter::Node, source: &[u8]) -> bool {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                let name = Self::node_text(f, source);
                if ["open", "read", "write"].contains(&name.as_str()) {
                    return true;
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if child.kind() == "call" {
                let func = child.child_by_field_name("function");
                if let Some(f) = func {
                    let text = Self::node_text(f, source);
                    if text == "open" {
                        return true;
                    }
                }
                let mut args_cursor = child.walk();
                for arg in child.children(&mut args_cursor) {
                    if arg.kind() == "attribute" {
                        let arg_text = Self::node_text(arg, source);
                        if ["read", "write", "open"].iter().any(|ext| {
                            std::path::Path::new(&arg_text)
                                .extension()
                                .is_some_and(|e| e.eq_ignore_ascii_case(ext))
                        }) {
                            return true;
                        }
                    }
                }
            }
            if Self::has_file_io_call(child, source) {
                return true;
            }
        }
        false
    }

    fn detect_mutable_return(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_mutable_return_in_body(*b, source))
    }

    fn has_mutable_return_in_body(node: tree_sitter::Node, source: &[u8]) -> bool {
        if node.kind() == "return_statement" {
            let mut cursor = node.walk();
            for child in node.children(&mut cursor) {
                if Self::is_mutable_node(child, source) {
                    return true;
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_mutable_return_in_body(child, source) {
                return true;
            }
        }
        false
    }

    fn is_mutable_node(node: tree_sitter::Node, source: &[u8]) -> bool {
        match node.kind() {
            "list" | "dictionary" => true,
            "call" => {
                let func = node.child_by_field_name("function");
                if let Some(f) = func {
                    let name = Self::node_text(f, source);
                    return name == "list" || name == "dict";
                }
                false
            }
            _ => false,
        }
    }
}

fn has_mock_verifications_only(body_text: &str) -> bool {
    let mock_kw = [".assert_called", ".called", ".call_count"];
    let has_mock = mock_kw.iter().any(|k| body_text.contains(k));
    let has_assert = body_text.contains("assert ");
    has_mock && !has_assert
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_simple_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_simple.py");
        std::fs::write(
            &path,
            r#"
import pytest

def test_example():
    assert 1 == 1
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert_eq!(module.file_path, path);
        assert!(module.imports.iter().any(|imp| imp.contains("pytest")));
        assert_eq!(module.test_functions.len(), 1);
        assert_eq!(module.test_functions[0].name, "test_example");
        assert!(module.test_functions[0].has_assertions);
        assert_eq!(module.test_functions[0].assertion_count, 1);
        assert!(!module.test_functions[0].uses_time_sleep);
        assert!(!module.test_functions[0].uses_file_io);
        assert!(!module.test_functions[0].uses_network);
        assert!(!module.test_functions[0].has_conditional_logic);
        assert!(!module.test_functions[0].has_try_except);
    }

    #[test]
    fn test_parse_empty_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_empty.py");
        std::fs::write(&path, "").unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert_eq!(module.test_functions.len(), 0);
        assert_eq!(module.fixtures.len(), 0);
        assert!(module.imports.is_empty());
    }

    #[test]
    fn test_parse_extracts_fixture_deps() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_deps.py");
        std::fs::write(
            &path,
            r#"
def test_with_deps(tmp_path, monkeypatch):
    assert True
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert_eq!(module.test_functions[0].fixture_deps.len(), 2);
        assert!(module.test_functions[0].fixture_deps.contains(&"tmp_path".to_string()));
        assert!(module.test_functions[0].fixture_deps.contains(&"monkeypatch".to_string()));
    }

    #[test]
    fn test_parse_detects_docstring() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_doc.py");
        std::fs::write(
            &path,
            r#"
def test_documented():
    """Given a state when something happens then something."""
    assert True
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.test_functions[0].docstring.is_some());
    }

    #[test]
    fn test_count_top_level_entries_empty() {
        assert_eq!(PythonParser::count_top_level_entries(""), 0);
    }

    #[test]
    fn test_count_top_level_entries_whitespace_only() {
        assert_eq!(PythonParser::count_top_level_entries("   "), 0);
    }

    #[test]
    fn test_count_top_level_entries_single_item() {
        assert_eq!(PythonParser::count_top_level_entries("1"), 1);
    }

    #[test]
    fn test_count_top_level_entries_comma_separated() {
        assert_eq!(PythonParser::count_top_level_entries("1, 2, 3"), 3);
    }

    #[test]
    fn test_count_top_level_entries_with_strings() {
        assert_eq!(PythonParser::count_top_level_entries("\"a\", \"b\""), 2);
    }

    #[test]
    fn test_count_top_level_entries_with_single_quotes() {
        assert_eq!(PythonParser::count_top_level_entries("'x', 'y'"), 2);
    }

    #[test]
    fn test_count_top_level_entries_with_escaped_chars() {
        assert_eq!(PythonParser::count_top_level_entries(r#""a\"b", "c""#), 2);
    }

    #[test]
    fn test_count_top_level_entries_with_nested_brackets() {
        assert_eq!(PythonParser::count_top_level_entries("[1, 2], [3, 4]"), 2);
    }

    #[test]
    fn test_count_top_level_entries_trailing_comma() {
        assert_eq!(PythonParser::count_top_level_entries("1, 2, "), 2);
    }

    #[test]
    fn test_count_top_level_entries_with_braces() {
        assert_eq!(PythonParser::count_top_level_entries("{1: 2}, {3: 4}"), 2);
    }

    #[test]
    fn test_count_top_level_entries_with_parens() {
        assert_eq!(PythonParser::count_top_level_entries("(1, 2), (3, 4)"), 2);
    }

    #[test]
    fn test_count_parametrize_args_bracket_format() {
        assert!(PythonParser::count_parametrize_args("parametrize('x', [1, 2])") >= 1);
    }

    #[test]
    fn test_count_parametrize_args_no_brackets() {
        assert_eq!(PythonParser::count_parametrize_args("parametrize('x')"), 1);
    }

    #[test]
    fn test_count_parametrize_args_multiple_parens() {
        assert_eq!(PythonParser::count_parametrize_args("parametrize('x', (1, 2))"), 2);
    }

    #[test]
    fn test_has_mock_verifications_only_true() {
        assert!(has_mock_verifications_only("mock.assert_called()"));
    }

    #[test]
    fn test_has_mock_verifications_only_false_no_mock() {
        assert!(!has_mock_verifications_only("assert True"));
    }

    #[test]
    fn test_has_mock_verifications_only_false_both() {
        assert!(!has_mock_verifications_only("mock.assert_called()\nassert True"));
    }

    #[test]
    fn test_has_mock_verifications_call_count() {
        assert!(has_mock_verifications_only("mock.call_count"));
    }

    #[test]
    fn test_parse_decorated_and_undecorated() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_mixed_dec.py");
        std::fs::write(
            &path,
            r#"
import pytest

def test_plain():
    assert True

@pytest.mark.parametrize("x", [1, 2])
def test_param(x):
    assert x > 0
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert_eq!(module.test_functions.len(), 2);
    }

    #[test]
    fn test_count_top_level_entries_with_mixed_quotes() {
        assert_eq!(PythonParser::count_top_level_entries("\"foo's bar\", 'baz\"qux'"), 2);
    }

    #[test]
    fn test_count_top_level_entries_mismatched_quotes_are_separate() {
        assert_eq!(PythonParser::count_top_level_entries("\"hello', 'world\""), 1);
    }

    #[test]
    fn test_parse_import_from_statement() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_imports.py");
        std::fs::write(
            &path,
            r#"
from os import path
from sys import argv

def test_ok():
    assert True
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.imports.iter().any(|imp| imp.contains("os")));
        assert!(module.imports.iter().any(|imp| imp.contains("sys")));
    }

    #[test]
    fn test_parse_fixture_with_no_params() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_no_params.py");
        std::fs::write(
            &path,
            r#"
import pytest

@pytest.fixture
def no_param_fix():
    return 42

def test_thing():
    assert True
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.fixtures[0].dependencies.is_empty());
    }

    #[test]
    fn test_parse_fixture_with_yield_and_commit() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_yield_commit.py");
        std::fs::write(
            &path,
            r#"
import pytest

@pytest.fixture
def yield_commit():
    conn = get_conn()
    conn.commit()
    yield conn
    conn.rollback()
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.fixtures[0].has_yield);
        assert!(module.fixtures[0].has_db_commit);
        assert!(module.fixtures[0].has_db_rollback);
    }

    #[test]
    fn test_parse_fixture_dot_commit() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_dot_commit.py");
        std::fs::write(
            &path,
            r#"
import pytest

@pytest.fixture
def dot_commit():
    session.commit()
    return session
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.fixtures[0].has_db_commit);
    }

    #[test]
    fn test_parse_fixture_dot_rollback() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_dot_rollback.py");
        std::fs::write(
            &path,
            r#"
import pytest

@pytest.fixture
def dot_rollback():
    session.rollback()
    return session
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.fixtures[0].has_db_rollback);
    }

    #[test]
    fn test_parse_test_with_open_paren_space() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test_open_space.py");
        std::fs::write(
            &path,
            r#"
def test_open():
    f = open ("data.txt")
    assert f
"#,
        )
        .unwrap();

        let mut parser = PythonParser::new().unwrap();
        let module = parser.parse_file(&path).unwrap();

        assert!(module.test_functions[0].uses_file_io);
    }
}
