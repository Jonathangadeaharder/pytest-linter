use crate::engine::make_violation;
use crate::models::{Category, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};

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
        let network_modules = [
            "requests", "httpx", "aiohttp", "urllib", "urllib3", "socket", "pycurl", "grpc",
            "aiogrpc",
        ];
        let has_network = module
            .imports
            .iter()
            .any(|imp| network_modules.iter().any(|nm| imp.contains(nm)));
        if !has_network {
            return vec![];
        }
        let has_network_mark = module.source.contains("@pytest.mark.network")
            || module.source.contains("pytest.mark.network")
            || module.source.contains("conftest");
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
        let network_modules = ["requests", "httpx", "aiohttp", "urllib", "socket", "grpc"];
        let has_network = module
            .imports
            .iter()
            .any(|imp| network_modules.iter().any(|nm| imp.contains(nm)));
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
                let body = &module.source;
                let non_idiomatic_patterns = [
                    "monkeypatch.setattr(",
                    "monkeypatch.setenv(",
                    "monkeypatch.delenv(",
                    "monkeypatch.chdir(",
                    "monkeypatch.syspath_prepend(",
                ];
                let has_monkeypatch_call = non_idiomatic_patterns.iter().any(|p| body.contains(p));
                if has_monkeypatch_call {
                    let has_context = body.contains("with monkeypatch.context()")
                        || body.contains("monkeypatch.undo()");
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
        Severity::Info
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
        }
        violations
    }
}
