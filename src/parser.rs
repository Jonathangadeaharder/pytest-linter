use crate::models::{Fixture, FixtureScope, ParsedModule, TestFunction};
use anyhow::Result;
use std::hash::{Hash, Hasher};
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
        self.parse_source(&source, path)
    }

    #[allow(clippy::missing_errors_doc)]
    pub fn parse_source(&mut self, source: &str, path: &Path) -> Result<ParsedModule> {
        let tree = self.parser.parse(source, None);
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
            eprintln!(
                "Warning: tree-sitter failed to parse {}",
                file_path.display()
            );
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

    fn collect_function_nodes<'tree>(
        root: &'tree tree_sitter::Node<'tree>,
    ) -> Vec<tree_sitter::Node<'tree>> {
        let mut nodes = Vec::new();
        let mut to_visit = vec![*root];
        while let Some(node) = to_visit.pop() {
            let mut cursor = node.walk();
            for child in node.children(&mut cursor) {
                match child.kind() {
                    "function_definition" => {
                        nodes.push(child);
                    }
                    "decorated_definition" => {
                        let mut inner = child.walk();
                        for c in child.children(&mut inner) {
                            match c.kind() {
                                "function_definition" => nodes.push(c),
                                "class_definition" => to_visit.push(c),
                                _ => {}
                            }
                        }
                    }
                    "class_definition" => {
                        to_visit.push(child);
                    }
                    _ => {}
                }
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
                        &func_node, source, file_path, &name,
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
        let body_text = body.map(|b| Self::node_text(b, source)).unwrap_or_default();

        let decorators = Self::get_decorators(func_node, source);
        let parametrize_values = Self::extract_parametrize_values(&decorators, source);

        let is_async = {
            let mut cur = func_node.walk();
            let has_async = func_node.children(&mut cur).any(|c| c.kind() == "async");
            drop(cur);
            has_async
        };
        let (is_parametrized, parametrize_count) = Self::detect_parametrize(&decorators);
        let assertion_count = Self::count_assertions(body.as_ref());
        let has_assertions = assertion_count > 0;
        let has_mock_verifications = body_text.contains(".assert_called")
            || body_text.contains(".called")
            || body_text.contains(".call_count");
        let has_state_assertions = has_assertions && !has_mock_verifications_only(&body_text);
        let fixture_deps = Self::extract_fixture_deps(func_node, source);
        let uses_time_sleep = Self::detect_time_sleep(body.as_ref(), source);
        let sleep_value = Self::detect_sleep_value(body.as_ref(), source);
        let uses_file_io = Self::detect_file_io(body.as_ref(), source);
        let uses_network = Self::detect_network_usage(body.as_ref(), source);
        let has_conditional_logic = Self::detect_conditionals(body.as_ref());
        let has_try_except = Self::detect_try_except(body.as_ref());
        let docstring = Self::extract_docstring(func_node, source);
        let assertions = Self::extract_assertions(body.as_ref(), source);
        let uses_cwd_dependency = Self::detect_cwd_dependency(body.as_ref(), source);
        let uses_pytest_raises = Self::detect_pytest_raises(body.as_ref(), source);
        let mutates_fixture_deps =
            Self::detect_fixture_mutations(body.as_ref(), source, &fixture_deps);

        let body_hash = body.map(|b| {
            let text = Self::node_text(b, source);
            let mut hasher = std::collections::hash_map::DefaultHasher::new();
            text.hash(&mut hasher);
            hasher.finish()
        });

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
            sleep_value,
            uses_file_io,
            uses_network,
            has_conditional_logic,
            has_try_except,
            docstring,
            assertions,
            parametrize_values,
            uses_cwd_dependency,
            uses_pytest_raises,
            mutates_fixture_deps,
            body_hash,
        }
    }

    fn get_decorators<'a>(
        func_node: &tree_sitter::Node<'a>,
        source: &[u8],
    ) -> Vec<DecoratorInfo<'a>> {
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
            let name = dec
                .text
                .trim_start_matches('@')
                .split('(')
                .next()
                .unwrap_or("")
                .trim();
            if name == "pytest.mark.parametrize" || name == "parametrize" {
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
                        let mut comma_count = 0;
                        let mut args_cursor = call_child.walk();
                        for arg in call_child.children(&mut args_cursor) {
                            if arg.kind() == "," {
                                comma_count += 1;
                                continue;
                            }
                            if comma_count >= 1 && (arg.kind() == "list" || arg.kind() == "tuple") {
                                let mut elem_count = 0;
                                let mut elem_cursor = arg.walk();
                                let mut found_comma = false;
                                for elem in arg.children(&mut elem_cursor) {
                                    match elem.kind() {
                                        "," => {
                                            found_comma = true;
                                        }
                                        "(" | ")" | "[" | "]" | "comment" => {}
                                        _ if !elem.is_extra() => {
                                            elem_count += 1;
                                        }
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

    fn extract_assertions(
        body: Option<&tree_sitter::Node>,
        source: &[u8],
    ) -> Vec<crate::models::AssertionInfo> {
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
            let expr_node = node.children(&mut cursor).find(|c| {
                let k = c.kind();
                !k.starts_with(',') && k != "comment" && k != "assert"
            });
            let expression_text = expr_node
                .map(|n| Self::node_text(n, source))
                .unwrap_or_default();
            let has_comparison =
                expr_node.is_some_and(|n| Self::has_node_kind_recursive(n, "comparison_operator"));
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
            let is_suboptimal = expr_node.is_some_and(|n| Self::is_suboptimal_assertion(n, source));
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
                if child.kind() == "is" || child.kind() == "is not" {
                    return false;
                }
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
                    // only consider it suboptimal if it's '== None' or '!= None', which is caught here
                    // 'is not None' or 'is None' are returned false above.
                    if text.contains("==") || text.contains("!=") || text.contains("not") {
                        return true;
                    }
                }
            }
        }
        false
    }

    fn extract_parametrize_values(decorators: &[DecoratorInfo], source: &[u8]) -> Vec<Vec<String>> {
        let mut all_values = Vec::new();
        for dec in decorators {
            let name = dec
                .text
                .trim_start_matches('@')
                .split('(')
                .next()
                .unwrap_or("")
                .trim();
            if name != "pytest.mark.parametrize" && name != "parametrize" {
                continue;
            }
            if let Some(node) = dec.node {
                if let Some(values) = Self::extract_values_from_decorator_node(node, source) {
                    all_values.push(values);
                }
            }
        }
        all_values
    }

    fn extract_values_from_decorator_node(
        decorator_node: tree_sitter::Node,
        source: &[u8],
    ) -> Option<Vec<String>> {
        let mut cursor = decorator_node.walk();
        for child in decorator_node.children(&mut cursor) {
            if child.kind() == "call" {
                let mut call_cursor = child.walk();
                for call_child in child.children(&mut call_cursor) {
                    if call_child.kind() == "argument_list" {
                        let mut args_cursor = call_child.walk();
                        let mut target_arg = None;
                        let mut tuple_list_count = 0;
                        for arg in call_child.children(&mut args_cursor) {
                            if arg.kind() == "list" || arg.kind() == "tuple" {
                                tuple_list_count += 1;
                                target_arg = Some(arg);
                                if tuple_list_count == 2 {
                                    break;
                                }
                            }
                        }
                        if let Some(arg) = target_arg {
                            let mut values = Vec::new();
                            let mut elem_cursor = arg.walk();
                            for elem in arg.children(&mut elem_cursor) {
                                match elem.kind() {
                                    "," | "(" | ")" | "[" | "]" | "comment" => {}
                                    _ if !elem.is_extra() => {
                                        values
                                            .push(Self::node_text(elem, source).trim().to_string());
                                    }
                                    _ => {}
                                }
                            }
                            return Some(values);
                        }
                    }
                }
            }
        }
        None
    }

    fn detect_cwd_dependency(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_cwd_call(*b, source))
    }

    fn has_cwd_call(node: tree_sitter::Node, source: &[u8]) -> bool {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                let text = Self::node_text(f, source);
                if text == "os.getcwd" || text == "os.chdir" || text == "Path.cwd" {
                    return true;
                }
                if text.contains("getcwd") || text.contains("chdir") {
                    return true;
                }
                if f.kind() == "attribute" {
                    let attr = f.child_by_field_name("attribute");
                    if let Some(a) = attr {
                        let name = Self::node_text(a, source);
                        if name == "getcwd" || name == "chdir" {
                            return true;
                        }
                    }
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_cwd_call(child, source) {
                return true;
            }
        }
        false
    }

    fn detect_pytest_raises(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_pytest_raises(*b, source))
    }

    fn has_pytest_raises(node: tree_sitter::Node, source: &[u8]) -> bool {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                if f.kind() == "attribute" {
                    let text = Self::node_text(f, source);
                    if text == "pytest.raises" {
                        return true;
                    }
                    let attr = f.child_by_field_name("attribute");
                    let obj = f.child_by_field_name("object");
                    if let (Some(a), Some(o)) = (attr, obj) {
                        let name = Self::node_text(a, source);
                        let obj_name = Self::node_text(o, source);
                        if name == "raises" && obj_name == "pytest" {
                            return true;
                        }
                    }
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_pytest_raises(child, source) {
                return true;
            }
        }
        false
    }

    fn detect_fixture_mutations(
        body: Option<&tree_sitter::Node>,
        source: &[u8],
        fixture_deps: &[String],
    ) -> Vec<String> {
        let mut mutated = Vec::new();
        if let Some(b) = body {
            Self::find_mutations(*b, source, fixture_deps, &mut mutated);
        }
        mutated.sort();
        mutated.dedup();
        mutated
    }

    fn find_mutations(
        node: tree_sitter::Node,
        source: &[u8],
        fixture_deps: &[String],
        mutated: &mut Vec<String>,
    ) {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                if f.kind() == "attribute" {
                    let obj = f.child_by_field_name("object");
                    let attr = f.child_by_field_name("attribute");
                    if let (Some(obj), Some(attr)) = (obj, attr) {
                        let obj_name = Self::node_text(obj, source);
                        let method = Self::node_text(attr, source);
                        let mutating_methods = [
                            "append", "extend", "remove", "pop", "clear", "update", "insert",
                            "add", "discard",
                        ];
                        if mutating_methods.contains(&method.as_str())
                            && fixture_deps.contains(&obj_name)
                        {
                            mutated.push(obj_name);
                        }
                    }
                }
            }
        }
        if node.kind() == "assignment" {
            let target = node.child_by_field_name("left");
            if let Some(t) = target {
                Self::check_assignment_target(t, source, fixture_deps, mutated);
            }
        }
        if node.kind() == "delete_statement" {
            let mut cursor = node.walk();
            for child in node.children(&mut cursor) {
                let text = Self::node_text(child, source).trim().to_string();
                if fixture_deps.contains(&text) {
                    mutated.push(text);
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            Self::find_mutations(child, source, fixture_deps, mutated);
        }
    }

    fn check_assignment_target(
        target: tree_sitter::Node,
        source: &[u8],
        fixture_deps: &[String],
        mutated: &mut Vec<String>,
    ) {
        if target.kind() == "subscript" {
            let value = target.child_by_field_name("value");
            if let Some(v) = value {
                let name = Self::node_text(v, source);
                if fixture_deps.contains(&name) {
                    mutated.push(name);
                }
            }
        }
        if target.kind() == "attribute" {
            let obj = target.child_by_field_name("object");
            if let Some(o) = obj {
                let name = Self::node_text(o, source);
                if fixture_deps.contains(&name) {
                    mutated.push(name);
                }
            }
        }
    }

    fn extract_docstring(func_node: &tree_sitter::Node, source: &[u8]) -> Option<String> {
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

    fn extract_fixture_deps(func_node: &tree_sitter::Node, source: &[u8]) -> Vec<String> {
        let mut deps = Vec::new();
        let params = func_node.child_by_field_name("parameters");
        if let Some(p) = params {
            let mut cursor = p.walk();
            for child in p.children(&mut cursor) {
                let name = match child.kind() {
                    "identifier" => Some(Self::node_text(child, source)),
                    "typed_parameter" | "default_parameter" | "typed_default_parameter" => child
                        .child_by_field_name("name")
                        .map(|n| Self::node_text(n, source)),
                    _ => None,
                };
                if let Some(name) = name {
                    if !["self", "cls"].contains(&name.as_str()) {
                        deps.push(name);
                    }
                }
            }
        }
        deps
    }

    fn extract_fixtures(root: &tree_sitter::Node, source: &[u8], file_path: &Path) -> Vec<Fixture> {
        let mut fixtures = Vec::new();

        for func_node in Self::collect_function_nodes(root) {
            let decorators = Self::get_decorators(&func_node, source);
            let is_fixture = decorators.iter().any(|d| {
                let name = d
                    .text
                    .trim_start_matches('@')
                    .split('(')
                    .next()
                    .unwrap_or("")
                    .trim();
                name == "pytest.fixture" || name == "fixture"
            });

            if is_fixture {
                let name_node = func_node.child_by_field_name("name");
                if let Some(nn) = name_node {
                    let name = Self::node_text(nn, source);
                    let dec_texts: Vec<String> =
                        decorators.iter().map(|d| d.text.clone()).collect();
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

        let scope = Self::extract_fixture_scope(decorators);
        let is_autouse = decorators
            .iter()
            .any(|d| d.contains("autouse") && d.contains("True"));
        let dependencies = Self::extract_fixture_deps(func_node, source);
        let returns_mutable = Self::detect_mutable_return(body.as_ref(), source);
        let has_yield = Self::detect_yield(body.as_ref());
        let has_db_commit = Self::detect_db_commit(body.as_ref(), source);
        let has_db_rollback = Self::detect_db_rollback(body.as_ref(), source);
        let has_cleanup = has_db_rollback || Self::detect_cleanup_pattern(body.as_ref(), source);
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
            has_cleanup,
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
                if f.kind() == "attribute" {
                    let attr = f.child_by_field_name("attribute");
                    if let Some(a) = attr {
                        let attr_name = Self::node_text(a, source);
                        if ["read", "write", "open"].contains(&attr_name.as_str()) {
                            return true;
                        }
                    }
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_file_io_call(child, source) {
                return true;
            }
        }
        false
    }

    fn detect_time_sleep(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_time_sleep_call(*b, source))
    }

    fn has_time_sleep_call(node: tree_sitter::Node, source: &[u8]) -> bool {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                let text = Self::node_text(f, source);
                if text == "time.sleep" || text == "sleep" {
                    return true;
                }
                if f.kind() == "attribute" {
                    let attr = f.child_by_field_name("attribute");
                    if let Some(a) = attr {
                        let name = Self::node_text(a, source);
                        if name == "sleep" {
                            return true;
                        }
                    }
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_time_sleep_call(child, source) {
                return true;
            }
        }
        false
    }

    fn detect_sleep_value(body: Option<&tree_sitter::Node>, source: &[u8]) -> Option<f64> {
        body.and_then(|b| Self::find_sleep_value(*b, source))
    }

    fn extract_sleep_arg(node: tree_sitter::Node, source: &[u8]) -> Option<f64> {
        if let Some(arg) = node.child_by_field_name("arguments") {
            for child in arg.children(&mut arg.walk()) {
                if child.kind() == "integer" || child.kind() == "float" {
                    let val_str = Self::node_text(child, source);
                    if let Ok(val) = val_str.parse::<f64>() {
                        return Some(val);
                    }
                } else if child.kind() == "unary_operator" {
                    let op = child
                        .child_by_field_name("operator")
                        .map(|op| Self::node_text(op, source));
                    if op.as_deref() == Some("-") {
                        if let Some(operand) = child.child_by_field_name("operand") {
                            let val_str = Self::node_text(operand, source);
                            if let Ok(val) = val_str.parse::<f64>() {
                                return Some(-val);
                            }
                        }
                    }
                }
            }
        }
        None
    }

    fn is_sleep_call(func: tree_sitter::Node, source: &[u8]) -> bool {
        let text = Self::node_text(func, source);
        if text == "time.sleep" || text == "sleep" {
            return true;
        }
        if func.kind() == "attribute" {
            if let Some(attr) = func.child_by_field_name("attribute") {
                let name = Self::node_text(attr, source);
                if name == "sleep" {
                    return true;
                }
            }
        }
        false
    }

    fn find_sleep_value(node: tree_sitter::Node, source: &[u8]) -> Option<f64> {
        let mut max_val: Option<f64> = None;

        if node.kind() == "call" {
            if let Some(func) = node.child_by_field_name("function") {
                if Self::is_sleep_call(func, source) {
                    if let Some(val) = Self::extract_sleep_arg(node, source) {
                        max_val = Some(val);
                    }
                }
            }
        }

        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if let Some(val) = Self::find_sleep_value(child, source) {
                match max_val {
                    None => max_val = Some(val),
                    Some(current) if val > current => max_val = Some(val),
                    _ => {}
                }
            }
        }

        max_val
    }

    fn detect_cleanup_pattern(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        let cleanup_text_patterns = [
            ".close()",
            ".teardown_",
            "env_reset",
            ".restore()",
            ".cleanup()",
            ".remove()",
            ".unlink()",
        ];
        body.is_some_and(|b| {
            let text = String::from_utf8_lossy(&source[b.start_byte()..b.end_byte()]);

            if cleanup_text_patterns.iter().any(|p| text.contains(p)) {
                return true;
            }

            if text.contains("addfinalizer") || text.contains("request.addfinalizer") {
                return true;
            }

            if text.contains("mock.patch") || text.contains("patch(") {
                return true;
            }

            if text.contains("tmp_path") || text.contains("tmpdir") {
                return true;
            }

            if Self::has_try_wrapping_yield(*b, source) {
                return true;
            }

            if Self::has_with_wrapping_yield(*b, source) {
                return true;
            }

            false
        })
    }

    fn has_try_wrapping_yield(body: tree_sitter::Node, _source: &[u8]) -> bool {
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            if child.kind() == "try_statement" {
                let mut try_cursor = child.walk();
                for try_child in child.children(&mut try_cursor) {
                    if (try_child.kind() == "block" || try_child.kind() == "suite")
                        && Self::has_node_kind_recursive(try_child, "yield")
                    {
                        return true;
                    }
                }
            }
        }
        false
    }

    fn has_with_wrapping_yield(body: tree_sitter::Node, _source: &[u8]) -> bool {
        let mut cursor = body.walk();
        for child in body.children(&mut cursor) {
            if child.kind() == "with_statement" && Self::has_node_kind_recursive(child, "yield") {
                return true;
            }
        }
        false
    }

    fn detect_network_usage(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_network_call(*b, source))
    }

    fn has_network_call(node: tree_sitter::Node, source: &[u8]) -> bool {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                let text = Self::node_text(f, source);
                let network_libs = ["requests", "socket", "httpx", "aiohttp", "urllib"];
                if network_libs.iter().any(|lib| {
                    text.starts_with(&format!("{}.", lib))
                        || text.starts_with(&format!("{} (", lib))
                }) {
                    return true;
                }
                if f.kind() == "attribute" {
                    let obj = f.child_by_field_name("object");
                    if let Some(o) = obj {
                        let obj_name = Self::node_text(o, source);
                        if network_libs.contains(&obj_name.as_str()) {
                            return true;
                        }
                    }
                }
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_network_call(child, source) {
                return true;
            }
        }
        false
    }

    fn detect_yield(body: Option<&tree_sitter::Node>) -> bool {
        body.is_some_and(|b| Self::has_node_kind_recursive(*b, "yield"))
    }

    fn detect_db_commit(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_db_call(*b, source, "commit"))
    }

    fn detect_db_rollback(body: Option<&tree_sitter::Node>, source: &[u8]) -> bool {
        body.is_some_and(|b| Self::has_db_call(*b, source, "rollback"))
    }

    fn has_db_call(node: tree_sitter::Node, source: &[u8], method_name: &str) -> bool {
        if node.kind() == "call" {
            let func = node.child_by_field_name("function");
            if let Some(f) = func {
                let text = Self::node_text(f, source);
                if text.to_lowercase().contains(method_name) {
                    return true;
                }
                if f.kind() == "attribute" {
                    let attr = f.child_by_field_name("attribute");
                    if let Some(a) = attr {
                        let name = Self::node_text(a, source).to_lowercase();
                        if name == method_name {
                            return true;
                        }
                    }
                }
            }
        }
        if node.kind() == "identifier" {
            let name = Self::node_text(node, source).to_lowercase();
            if name == method_name {
                return true;
            }
        }
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if Self::has_db_call(child, source, method_name) {
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
    let has_assert = body_text.contains("assert ") || body_text.contains("assert(");
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
        assert!(module.test_functions[0]
            .fixture_deps
            .contains(&"tmp_path".to_string()));
        assert!(module.test_functions[0]
            .fixture_deps
            .contains(&"monkeypatch".to_string()));
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
        assert_eq!(
            PythonParser::count_parametrize_args("parametrize('x', (1, 2))"),
            2
        );
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
        assert!(!has_mock_verifications_only(
            "mock.assert_called()\nassert True"
        ));
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
        assert_eq!(
            PythonParser::count_top_level_entries("\"foo's bar\", 'baz\"qux'"),
            2
        );
    }

    #[test]
    fn test_count_top_level_entries_mismatched_quotes_are_separate() {
        assert_eq!(
            PythonParser::count_top_level_entries("\"hello', 'world\""),
            1
        );
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
