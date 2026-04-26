use crate::models::{Fixture, FixtureScope, ParsedModule, TestFunction};
use anyhow::Result;
use std::path::Path;
use tree_sitter::Parser;

pub struct PythonParser {
    parser: Parser,
}

impl PythonParser {
    pub fn new() -> Result<Self> {
        let mut parser = Parser::new();
        parser.set_language(&tree_sitter_python::LANGUAGE.into())?;
        Ok(Self { parser })
    }

    pub fn parse_file(&mut self, path: &Path) -> Result<ParsedModule> {
        let source = std::fs::read_to_string(path)?;
        let tree = self.parser.parse(&source, None);
        let file_path = path.to_path_buf();

        match tree {
            Some(tree) => {
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
            }
            None => Ok(ParsedModule {
                file_path,
                imports: vec![],
                test_functions: vec![],
                fixtures: vec![],
            }),
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
        file_path: &std::path::PathBuf,
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
        file_path: &std::path::PathBuf,
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
        let assertion_count = Self::count_assertions(&body);
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
        let has_conditional_logic = Self::detect_conditionals(&body);
        let has_try_except = Self::detect_try_except(&body);
        let docstring = Self::extract_docstring(func_node, source);

        TestFunction {
            name: name.to_string(),
            file_path: file_path.clone(),
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
        }
    }

    fn get_decorators(func_node: &tree_sitter::Node, source: &[u8]) -> Vec<String> {
        let mut decs = Vec::new();
        let parent = func_node.parent();
        let container = if parent.map_or(false, |p| p.kind() == "decorated_definition") {
            parent.unwrap()
        } else {
            *func_node
        };
        let mut cursor = container.walk();
        for child in container.children(&mut cursor) {
            if child.kind() == "decorator" {
                decs.push(Self::node_text(child, source));
            }
        }
        decs
    }

    fn detect_parametrize(decorators: &[String]) -> (bool, Option<usize>) {
        for dec in decorators {
            if dec.contains("parametrize") || dec.contains("pytest.mark.parametrize") {
                let count = Self::count_parametrize_args(dec);
                return (true, Some(count));
            }
        }
        (false, None)
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
        let mut in_str = false;
        let mut escape = false;
        let mut current_empty = true;

        for ch in inner.chars() {
            if escape {
                escape = false;
                current_empty = false;
                continue;
            }
            if ch == '\\' {
                escape = true;
                current_empty = false;
                continue;
            }
            if ch == '"' || ch == '\'' {
                in_str = !in_str;
                current_empty = false;
                continue;
            }
            if in_str {
                current_empty = false;
                continue;
            }
            match ch {
                '(' | '[' | '{' => {
                    depth += 1;
                    current_empty = false;
                }
                ')' | ']' | '}' => {
                    depth -= 1;
                    current_empty = false;
                }
                ',' => {
                    if depth == 0 {
                        if !current_empty {
                            count += 1;
                        }
                        current_empty = true;
                    }
                }
                _ => {
                    if !ch.is_whitespace() {
                        current_empty = false;
                    }
                }
            }
        }
        if !current_empty {
            count += 1;
        }
        count.max(1)
    }

    fn count_assertions(body: &Option<tree_sitter::Node>) -> usize {
        match body {
            Some(b) => {
                let mut count = 0;
                Self::count_assertions_recursive(*b, &mut count);
                count
            }
            None => 0,
        }
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

    fn detect_conditionals(body: &Option<tree_sitter::Node>) -> bool {
        match body {
            Some(b) => Self::has_node_kind(*b, "if_statement"),
            None => false,
        }
    }

    fn detect_try_except(body: &Option<tree_sitter::Node>) -> bool {
        match body {
            Some(b) => Self::has_node_kind(*b, "try_statement"),
            None => false,
        }
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
        file_path: &std::path::PathBuf,
    ) -> Vec<Fixture> {
        let mut fixtures = Vec::new();

        for func_node in Self::collect_function_nodes(root) {
            let decorators = Self::get_decorators(&func_node, source);
            let is_fixture = decorators.iter().any(|d| {
                d.contains("pytest.fixture") || d.contains("@fixture")
            });

            if is_fixture {
                let name_node = func_node.child_by_field_name("name");
                if let Some(nn) = name_node {
                    let name = Self::node_text(nn, source);
                    fixtures.push(Self::build_fixture(
                        &func_node, source, file_path, &name, &decorators,
                    ));
                }
            }
        }
        fixtures
    }

    fn build_fixture(
        func_node: &tree_sitter::Node,
        source: &[u8],
        file_path: &std::path::PathBuf,
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
        let returns_mutable = body_text.contains("return []")
            || body_text.contains("return {}")
            || body_text.contains("return dict(")
            || body_text.contains("return list(")
            || body_text.contains("dict()")
            || body_text.contains("list()");
        let has_yield = body_text.contains("yield");
        let has_db_commit = body_text.contains("commit()")
            || body_text.contains(".commit")
            || body_text.contains("COMMIT");
        let has_db_rollback = body_text.contains("rollback()")
            || body_text.contains(".rollback")
            || body_text.contains("ROLLBACK");

        Fixture {
            name: name.to_string(),
            file_path: file_path.clone(),
            line,
            scope,
            is_autouse,
            dependencies,
            returns_mutable,
            has_yield,
            has_db_commit,
            has_db_rollback,
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
}
