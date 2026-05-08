use crate::engine::make_violation;
use crate::models::{Category, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};

const NETWORK_MODULES: &[&str] = &[
    "requests", "httpx", "aiohttp", "urllib", "urllib3", "socket", "pycurl", "grpc", "aiogrpc",
];

pub struct NetworkBanMissingRule;

impl Rule for NetworkBanMissingRule {
    fn id(&self) -> &'static str {
        "PYTEST-INF-001"
    }
    fn name(&self) -> &'static str {
        "NetworkBanMissingRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let has_network = module
            .imports
            .iter()
            .any(|imp| NETWORK_MODULES.iter().any(|nm| imp.contains(nm)));
        if !has_network {
            return vec![];
        }
        let has_network_mark = module.source.contains("@pytest.mark.network")
            || module.source.contains("pytest.mark.network");
        let is_conftest = module.file_path.ends_with("conftest.py");
        if has_network_mark || is_conftest {
            return vec![];
        }
        let mock_layer_libs = [
            "pytest_httpx",
            "respx",
            "aioresponses",
            "responses",
            "requests_mock",
            "pytest_mock",
            "vcrpy",
            "betamax",
            "httmock",
        ];
        let has_mock_layer = module
            .imports
            .iter()
            .any(|imp| mock_layer_libs.iter().any(|ml| imp.contains(ml)));
        if has_network_mark || has_mock_layer {
            return vec![];
        }
        vec![make_violation(
            self.id(),
            self.name(),
            self.severity(),
            self.category(),
            "File imports network libraries without @pytest.mark.network or mock layer".to_string(),
            module.file_path.clone(),
            1,
            Some(
                "Add @pytest.mark.network or use a mock layer (respx, responses, etc.)".to_string(),
            ),
            None,
        )]
    }
}

pub struct LiveSuiteUnmarkedRule;

impl Rule for LiveSuiteUnmarkedRule {
    fn id(&self) -> &'static str {
        "PYTEST-INF-002"
    }
    fn name(&self) -> &'static str {
        "LiveSuiteUnmarkedRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let has_network = module
            .imports
            .iter()
            .any(|imp| NETWORK_MODULES.iter().any(|nm| imp.contains(nm)));
        if !has_network {
            return vec![];
        }
        let mock_layer_libs = [
            "pytest_httpx",
            "respx",
            "aioresponses",
            "responses",
            "requests_mock",
            "vcrpy",
            "betamax",
            "httmock",
        ];
        let has_mock_layer = module
            .imports
            .iter()
            .any(|imp| mock_layer_libs.iter().any(|ml| imp.contains(ml)));
        if has_mock_layer {
            return vec![];
        }
        for test in &module.test_functions {
            if test.uses_network {
                let has_live = module.source.contains("@pytest.mark.live")
                    || module.source.contains("pytest.mark.live");
                if !has_live {
                    return vec![make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        "File has live network calls without @pytest.mark.live".to_string(),
                        module.file_path.clone(),
                        1,
                        Some("Mark live network tests with @pytest.mark.live for selective CI filtering".to_string()),
                        None,
                    )];
                }
            }
        }
        vec![]
    }
}

pub struct NonIdiomaticMonkeyPatchRule;

impl Rule for NonIdiomaticMonkeyPatchRule {
    fn id(&self) -> &'static str {
        "PYTEST-INF-003"
    }
    fn name(&self) -> &'static str {
        "NonIdiomaticMonkeyPatchRule"
    }
    fn severity(&self) -> Severity {
        Severity::Info
    }
    fn category(&self) -> Category {
        Category::Enhancement
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.fixture_deps.iter().any(|d| d == "monkeypatch") {
                let source_lines: Vec<&str> = module.source.lines().collect();
                let test_body: String = source_lines
                    .iter()
                    .skip(test.line.saturating_sub(1))
                    .take(test.end_line.saturating_sub(test.line).max(1))
                    .copied()
                    .collect::<Vec<&str>>()
                    .join("\n");
                let non_idiomatic_patterns = [
                    "monkeypatch.setattr(",
                    "monkeypatch.setenv(",
                    "monkeypatch.delenv(",
                    "monkeypatch.chdir(",
                    "monkeypatch.syspath_prepend(",
                ];
                let has_monkeypatch_call =
                    non_idiomatic_patterns.iter().any(|p| test_body.contains(p));
                if has_monkeypatch_call {
                    let has_context = test_body.contains("with monkeypatch.context()")
                        || test_body.contains("monkeypatch.undo()");
                    if !has_context {
                        violations.push(make_violation(
                            self.id(),
                            self.name(),
                            self.severity(),
                            self.category(),
                            format!(
                                "Test '{}' uses monkeypatch without context manager — changes may leak",
                                test.name
                            ),
                            module.file_path.clone(),
                            test.line,
                            Some("Use `with monkeypatch.context() as m:` for automatic cleanup".to_string()),
                            Some(test.name.clone()),
                        ));
                    }
                }
            }
        }
        violations
    }
}

pub struct MacOsCopyArtefactRule;

impl Rule for MacOsCopyArtefactRule {
    fn id(&self) -> &'static str {
        "PYTEST-INF-004"
    }
    fn name(&self) -> &'static str {
        "MacOsCopyArtefactRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.uses_shutil_copy {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Test '{}' uses shutil.copy/copy2/copyfile — may copy macOS metadata artefacts",
                        test.name
                    ),
                    module.file_path.clone(),
                    test.line,
                    Some("Use tmp_path.joinpath().write_bytes() or shutil.copy without preserving metadata".to_string()),
                    Some(test.name.clone()),
                ));
            }
            let source_lines: Vec<&str> = module.source.lines().collect();
            let start = test.line.saturating_sub(1);
            let len = test.end_line.saturating_sub(test.line).max(1);
            for line in source_lines.iter().skip(start).take(len) {
                let trimmed = line.trim();
                if let Some(artifact) = detect_macos_copy_artefact(trimmed) {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Test '{}' uses macOS Finder copy artefact filename '{}' — normalize or remove",
                            test.name, artifact
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some("Rename file to remove trailing ' N' copy suffix or use tmp_path fixtures".to_string()),
                        Some(test.name.clone()),
                    ));
                    break;
                }
            }
        }
        violations
    }
}

fn detect_macos_copy_artefact(line: &str) -> Option<&str> {
    line.split('"')
        .skip(1)
        .step_by(2)
        .find(|token| is_macos_finder_copy(token))
}

fn is_macos_finder_copy(filename: &str) -> bool {
    if filename.is_empty() {
        return false;
    }
    let last_space = match filename.rfind(' ') {
        Some(i) => i,
        None => return false,
    };
    let suffix = &filename[last_space + 1..];
    if suffix.is_empty() || !suffix.chars().all(|c| c.is_ascii_digit()) {
        return false;
    }
    let base = &filename[..last_space];
    !base.is_empty() && !base.ends_with('.')
}
