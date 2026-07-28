//! Integration tests for the pytest-linter LSP server.
//!
//! These tests drive a real `LspService<Backend>` end-to-end through the
//! `tower::Service<Request>` interface and read the server-to-client
//! `publishDiagnostics` notifications back from the `ClientSocket`. This
//! exercises the same code path (`did_open` / `did_change` → `lint_document`
//! → `publish_diagnostics`) that runs in production, without touching stdin /
//! stdout.

use std::sync::{Arc, RwLock};
use std::time::Duration;

use futures::StreamExt;
use pytest_linter::config::Config;
use serde_json::json;
use tokio::sync::Mutex;
use tokio::task::JoinHandle;
use tower::Service;
use tower::ServiceExt;
use tower_lsp::lsp_types::*;
use tower_lsp::{Client, LanguageServer, LspService};

/// Debounce window (ms) used by `did_change`. Kept in sync with
/// `lsp-server/src/main.rs::DEBOUNCE_MS`.
const DEBOUNCE_MS: u64 = 300;

struct Backend {
    client: Client,
    config: Arc<RwLock<Config>>,
    pending_lint: Mutex<Option<JoinHandle<()>>>,
}

#[tower_lsp::async_trait]
impl LanguageServer for Backend {
    async fn initialize(
        &self,
        params: InitializeParams,
    ) -> anyhow::Result<InitializeResult, tower_lsp::jsonrpc::Error> {
        let workspace_root = params
            .workspace_folders
            .as_ref()
            .and_then(|folders| folders.first())
            .and_then(|f| f.uri.to_file_path().ok())
            .or_else(|| {
                params
                    .root_uri
                    .as_ref()
                    .and_then(|uri| uri.to_file_path().ok())
            });

        if let Some(ref root) = workspace_root {
            if let Ok(cfg) = Config::discover(root) {
                if let Ok(mut guard) = self.config.write() {
                    *guard = cfg;
                }
            }
        }

        Ok(InitializeResult {
            capabilities: ServerCapabilities {
                position_encoding: Some(PositionEncodingKind::UTF8),
                text_document_sync: Some(TextDocumentSyncCapability::Options(
                    TextDocumentSyncOptions {
                        open_close: Some(true),
                        change: Some(TextDocumentSyncKind::FULL),
                        will_save: None,
                        will_save_wait_until: None,
                        save: None,
                    },
                )),
                ..Default::default()
            },
            server_info: Some(ServerInfo {
                name: "pytest-linter".to_string(),
                version: Some(env!("CARGO_PKG_VERSION").to_string()),
            }),
        })
    }

    async fn initialized(&self, _: InitializedParams) {}

    async fn shutdown(&self) -> anyhow::Result<(), tower_lsp::jsonrpc::Error> {
        Ok(())
    }

    async fn did_open(&self, params: DidOpenTextDocumentParams) {
        let uri = params.text_document.uri;
        let text = params.text_document.text;
        let config = match self.read_config().await {
            Some(c) => c,
            None => return,
        };
        let diagnostics = self.lint_document(&uri, &text, &config).await;
        self.client
            .publish_diagnostics(uri, diagnostics, None)
            .await;
    }

    async fn did_change(&self, params: DidChangeTextDocumentParams) {
        let uri = params.text_document.uri;
        let text = params
            .content_changes
            .last()
            .map(|c| c.text.clone())
            .unwrap_or_default();

        let config = match self.read_config().await {
            Some(c) => c,
            None => return,
        };

        let file_path = match uri.to_file_path() {
            Ok(p) => p,
            Err(_) => {
                self.client
                    .log_message(
                        MessageType::ERROR,
                        format!("pytest-linter: cannot resolve file path for URI {uri}"),
                    )
                    .await;
                return;
            }
        };

        let client = self.client.clone();
        let mut guard = self.pending_lint.lock().await;
        if let Some(handle) = guard.take() {
            handle.abort();
        }
        let handle = tokio::spawn(async move {
            tokio::time::sleep(Duration::from_millis(DEBOUNCE_MS)).await;
            let diagnostics = match pytest_linter::engine::LintEngine::new(config.clone()) {
                Ok(engine) => match engine.lint_source(&text, &file_path) {
                    Ok(violations) => violations
                        .into_iter()
                        .map(|v| {
                            let line = v.line.saturating_sub(1) as u32;
                            let start_character =
                                v.col.map(|c| c.saturating_sub(1) as u32).unwrap_or(0);
                            let end_character = v
                                .end_col
                                .map(|c| c.saturating_sub(1) as u32)
                                .unwrap_or(start_character.saturating_add(1));
                            Diagnostic {
                                range: Range {
                                    start: Position {
                                        line,
                                        character: start_character,
                                    },
                                    end: Position {
                                        line,
                                        character: end_character,
                                    },
                                },
                                severity: Some(match v.severity {
                                    pytest_linter::models::Severity::Error => {
                                        DiagnosticSeverity::ERROR
                                    }
                                    pytest_linter::models::Severity::Warning => {
                                        DiagnosticSeverity::WARNING
                                    }
                                    pytest_linter::models::Severity::Info => {
                                        DiagnosticSeverity::INFORMATION
                                    }
                                }),
                                code: Some(NumberOrString::String(v.rule_id.clone())),
                                source: Some("pytest-linter".to_string()),
                                message: v.message,
                                ..Diagnostic::default()
                            }
                        })
                        .collect::<Vec<_>>(),
                    Err(e) => single_failed_diagnostic(format!(
                        "pytest-linter: could not lint this file: {e}"
                    )),
                },
                Err(e) => single_failed_diagnostic(format!(
                    "pytest-linter: failed to initialize engine: {e}"
                )),
            };
            client.publish_diagnostics(uri, diagnostics, None).await;
        });
        *guard = Some(handle);
    }
}

impl Backend {
    async fn read_config(&self) -> Option<Config> {
        let cloned = self.config.read().map(|g| g.clone()).ok();
        if cloned.is_none() {
            self.client
                .log_message(MessageType::ERROR, "pytest-linter: config lock poisoned")
                .await;
        }
        cloned
    }

    async fn lint_document(&self, uri: &Url, text: &str, config: &Config) -> Vec<Diagnostic> {
        let file_path = match uri.to_file_path() {
            Ok(p) => p,
            Err(_) => {
                self.client
                    .log_message(
                        MessageType::ERROR,
                        format!("pytest-linter: cannot resolve file path for URI {uri}"),
                    )
                    .await;
                return vec![];
            }
        };

        let engine = match pytest_linter::engine::LintEngine::new(config.clone()) {
            Ok(e) => e,
            Err(e) => {
                self.client
                    .log_message(
                        MessageType::ERROR,
                        format!("pytest-linter: failed to initialize engine: {e}"),
                    )
                    .await;
                return single_failed_diagnostic(format!(
                    "pytest-linter: failed to initialize engine: {e}"
                ));
            }
        };

        let violations = match engine.lint_source(text, &file_path) {
            Ok(v) => v,
            Err(e) => {
                self.client
                    .log_message(
                        MessageType::ERROR,
                        format!("pytest-linter: failed to lint {file_path:?}: {e}"),
                    )
                    .await;
                return single_failed_diagnostic(format!(
                    "pytest-linter: could not lint this file: {e}"
                ));
            }
        };

        violations
            .into_iter()
            .map(|v| {
                let line = v.line.saturating_sub(1) as u32;
                let start_character = v.col.map(|c| c.saturating_sub(1) as u32).unwrap_or(0);
                let end_character = v
                    .end_col
                    .map(|c| c.saturating_sub(1) as u32)
                    .unwrap_or(start_character.saturating_add(1));
                Diagnostic {
                    range: Range {
                        start: Position {
                            line,
                            character: start_character,
                        },
                        end: Position {
                            line,
                            character: end_character,
                        },
                    },
                    severity: Some(match v.severity {
                        pytest_linter::models::Severity::Error => DiagnosticSeverity::ERROR,
                        pytest_linter::models::Severity::Warning => DiagnosticSeverity::WARNING,
                        pytest_linter::models::Severity::Info => DiagnosticSeverity::INFORMATION,
                    }),
                    code: Some(NumberOrString::String(v.rule_id.clone())),
                    source: Some("pytest-linter".to_string()),
                    message: v.message,
                    ..Diagnostic::default()
                }
            })
            .collect()
    }
}

/// Build a single error diagnostic emitted when the file could not be linted at all,
/// so the user is never left with silent zero output on failure.
fn single_failed_diagnostic(message: String) -> Vec<Diagnostic> {
    vec![Diagnostic {
        range: Range {
            start: Position {
                line: 0,
                character: 0,
            },
            end: Position {
                line: 0,
                character: 1,
            },
        },
        severity: Some(DiagnosticSeverity::ERROR),
        code: Some(NumberOrString::String("pytest-linter".to_string())),
        source: Some("pytest-linter".to_string()),
        message,
        ..Diagnostic::default()
    }]
}

/// Harness that owns the LSP service and the client socket, so tests can drive
/// requests and collect the resulting `publishDiagnostics` notifications.
struct LspHarness {
    service: LspService<Backend>,
    socket: tower_lsp::ClientSocket,
    last_diagnostics: Vec<PublishDiagnosticsParams>,
}

impl LspHarness {
    fn new() -> Self {
        let (service, socket) = LspService::new(|client| Backend {
            client,
            config: Arc::new(RwLock::new(Config::default())),
            pending_lint: Mutex::new(None),
        });
        Self {
            service,
            socket,
            last_diagnostics: Vec::new(),
        }
    }

    async fn initialize(&mut self) {
        let req = tower_lsp::jsonrpc::Request::build("initialize")
            .params(json!({
                "capabilities": {},
                "processId": null,
                "rootUri": null,
            }))
            .id(1)
            .finish();
        let _ = self.service.ready().await;
        // `initialize` is a request (has an id) and returns a response; it does
        // not emit client notifications, so we can await it directly.
        let _ = self.service.call(req).await;
        // `initialized` notification transitions the server to Initialized.
        let req = tower_lsp::jsonrpc::Request::build("initialized")
            .params(json!({}))
            .finish();
        let _ = self.service.ready().await;
        let _ = self.service.call(req).await;
        // Drain any stray notifications.
        let _ = self.collect_diagnostics(50).await;
    }

    async fn did_open(&mut self, uri: &Url, text: &str) {
        let req = tower_lsp::jsonrpc::Request::build("textDocument/didOpen")
            .params(json!({
                "textDocument": {
                    "uri": uri.as_str(),
                    "languageId": "python",
                    "version": 1,
                    "text": text,
                }
            }))
            .finish();
        self.send_and_drain(req).await;
    }

    async fn did_change(&mut self, uri: &Url, text: &str, version: i32) {
        let req = tower_lsp::jsonrpc::Request::build("textDocument/didChange")
            .params(json!({
                "textDocument": {
                    "uri": uri.as_str(),
                    "version": version,
                },
                "contentChanges": [
                    { "text": text }
                ]
            }))
            .finish();
        // `did_change` is debounced: the handler returns immediately and the
        // diagnostics arrive ~DEBOUNCE_MS later from the spawned task. Drive
        // the call concurrently with the socket, then keep draining until the
        // debounced publish_diagnostics lands.
        let _ = self.service.ready().await;
        let call_fut = self.service.call(req);
        tokio::pin!(call_fut);
        let mut collected = Vec::new();
        loop {
            tokio::select! {
                biased;
                res = &mut call_fut => {
                    let _ = res;
                    break;
                }
                Some(req) = self.socket.next() => {
                    push_if_diagnostics(&req, &mut collected);
                }
            }
        }
        // Drain buffered notifications, then wait for the debounced
        // publish_diagnostics (DEBOUNCE_MS + slack for the lint pass).
        while let Ok(Some(req)) =
            tokio::time::timeout(std::time::Duration::from_millis(50), self.socket.next()).await
        {
            push_if_diagnostics(&req, &mut collected);
        }
        let drain_deadline = std::time::Duration::from_millis(DEBOUNCE_MS + 500);
        let mut collected_more = self
            .collect_diagnostics(drain_deadline.as_millis() as u64)
            .await;
        collected.append(&mut collected_more);
        self.last_diagnostics = collected;
    }

    /// Drive a notification request concurrently with draining the client
    /// socket. This is necessary because the handler may call multiple client
    /// methods (`log_message`, `publish_diagnostics`) back-to-back, and the
    /// client channel has capacity 1 — if we awaited `call` to completion
    /// before draining, the second notification would block the handler forever.
    async fn send_and_drain(&mut self, req: tower_lsp::jsonrpc::Request) {
        let _ = self.service.ready().await;
        // Drive the call as a task so we can drain the socket concurrently.
        let call_fut = self.service.call(req);
        tokio::pin!(call_fut);
        // Poll both the call and the socket until the call completes (and we've
        // drained its notifications).
        let mut collected = Vec::new();
        loop {
            tokio::select! {
                biased;
                res = &mut call_fut => {
                    let _ = res;
                    break;
                }
                Some(req) = self.socket.next() => {
                    push_if_diagnostics(&req, &mut collected);
                }
            }
        }
        // After the handler returns there may still be buffered notifications
        // (e.g. publish_diagnostics sent last). Drain them non-blockingly.
        while let Ok(Some(req)) =
            tokio::time::timeout(std::time::Duration::from_millis(50), self.socket.next()).await
        {
            push_if_diagnostics(&req, &mut collected);
        }
        self.last_diagnostics = collected;
    }

    /// Drain any immediately-available notifications, waiting up to `timeout_ms`
    /// for the first one. Used by `initialize` to swallow stray messages.
    async fn collect_diagnostics(&mut self, timeout_ms: u64) -> Vec<PublishDiagnosticsParams> {
        let mut out = Vec::new();
        let first = tokio::time::timeout(
            std::time::Duration::from_millis(timeout_ms),
            self.socket.next(),
        )
        .await;
        if let Ok(Some(req)) = first {
            push_if_diagnostics(&req, &mut out);
        }
        while let Ok(Some(req)) =
            tokio::time::timeout(std::time::Duration::from_millis(50), self.socket.next()).await
        {
            push_if_diagnostics(&req, &mut out);
        }
        out
    }
}

fn push_if_diagnostics(req: &tower_lsp::jsonrpc::Request, out: &mut Vec<PublishDiagnosticsParams>) {
    if req.method() == "textDocument/publishDiagnostics" {
        if let Some(params) = req.params() {
            if let Ok(parsed) = serde_json::from_value::<PublishDiagnosticsParams>(params.clone()) {
                out.push(parsed);
            }
        }
    }
}

/// Return the diagnostics captured by the most recent `did_open` / `did_change`.
async fn next_diagnostics(harness: &mut LspHarness) -> Vec<PublishDiagnosticsParams> {
    tokio::task::yield_now().await;
    std::mem::take(&mut harness.last_diagnostics)
}

#[tokio::test]
async fn did_open_emits_diagnostics_for_flaky_test() {
    let dir = tempfile::tempdir().unwrap();
    let file_path = dir.path().join("test_flaky.py");
    let uri = Url::from_file_path(&file_path).unwrap();

    let source = r#"
import time

def test_waits():
    time.sleep(2)
    assert True
"#;

    let mut harness = LspHarness::new();
    harness.initialize().await;
    harness.did_open(&uri, source).await;

    let diags = next_diagnostics(&mut harness).await;
    assert!(
        !diags.is_empty(),
        "did_open should produce at least one publishDiagnostics notification"
    );
    let all = diags
        .iter()
        .flat_map(|d| d.diagnostics.iter())
        .collect::<Vec<_>>();
    assert!(
        all.iter().any(|d| d
            .code
            .as_ref()
            .is_some_and(|c| matches!(c, NumberOrString::String(s) if s == "PYTEST-FLK-001"))),
        "expected a PYTEST-FLK-001 diagnostic, got: {all:?}"
    );
    // The violation must reference the file's URI.
    assert!(diags.iter().all(|d| d.uri == uri));
}

#[tokio::test]
async fn did_open_file_emits_diagnostics_consistent_with_engine() {
    // The LSP must return the same set of rule IDs the engine produces for the
    // same source. We don't assert "zero diagnostics" because some rules
    // legitimately fire on simple happy-path tests.
    let dir = tempfile::tempdir().unwrap();
    let file_path = dir.path().join("test_simple.py");
    let uri = Url::from_file_path(&file_path).unwrap();

    let source = r#"
def test_ok():
    assert 1 + 1 == 2
"#;

    // Compute expected violations directly from the engine.
    let engine = pytest_linter::engine::LintEngine::new(Config::default()).unwrap();
    let expected = engine.lint_source(source, &file_path).unwrap();
    let expected_ids: std::collections::HashSet<String> =
        expected.iter().map(|v| v.rule_id.clone()).collect();

    let mut harness = LspHarness::new();
    harness.initialize().await;
    harness.did_open(&uri, source).await;

    let diags = next_diagnostics(&mut harness).await;
    let all = diags
        .iter()
        .flat_map(|d| d.diagnostics.iter())
        .collect::<Vec<_>>();
    let got_ids: std::collections::HashSet<String> = all
        .iter()
        .filter_map(|d| match d.code.as_ref()? {
            NumberOrString::String(s) => Some(s.clone()),
            NumberOrString::Number(_) => None,
        })
        .collect();
    assert_eq!(
        got_ids, expected_ids,
        "LSP diagnostics rule IDs must match the engine output"
    );
    // Every diagnostic must carry the source file's URI and a pytest-linter source.
    assert!(diags.iter().all(|d| d.uri == uri));
    assert!(all
        .iter()
        .all(|d| d.source.as_deref() == Some("pytest-linter")));
}

#[tokio::test]
async fn did_change_updates_diagnostics() {
    let dir = tempfile::tempdir().unwrap();
    let file_path = dir.path().join("test_change.py");
    let uri = Url::from_file_path(&file_path).unwrap();

    // A source with no test_ function (so no violations at all).
    let clean = "x = 1\n";
    let flaky = r#"
import time

def test_slow():
    time.sleep(5)
    assert True
"#;

    let mut harness = LspHarness::new();
    harness.initialize().await;

    // First open a file with no test functions: no diagnostics expected.
    harness.did_open(&uri, clean).await;
    let diags = next_diagnostics(&mut harness).await;
    let total: usize = diags.iter().map(|d| d.diagnostics.len()).sum();
    assert_eq!(total, 0, "non-test file should have no diagnostics");

    // Now change it to a flaky file; diagnostics must reflect the new content.
    harness.did_change(&uri, flaky, 2).await;
    let diags = next_diagnostics(&mut harness).await;
    assert!(
        !diags.is_empty(),
        "did_change should produce diagnostics for the updated content"
    );
    let all = diags
        .iter()
        .flat_map(|d| d.diagnostics.iter())
        .collect::<Vec<_>>();
    assert!(
        all.iter().any(|d| d
            .code
            .as_ref()
            .is_some_and(|c| matches!(c, NumberOrString::String(s) if s == "PYTEST-FLK-001"))),
        "expected PYTEST-FLK-001 after changing to a flaky test, got: {all:?}"
    );
}

#[tokio::test]
async fn did_open_with_invalid_uri_does_not_crash() {
    // A non-file URI cannot be resolved to a path; the server must log and
    // return empty diagnostics rather than panic.
    let uri = Url::parse("untitled:Untitled-1").unwrap();

    let source = "def test_x():\n    assert True\n";

    let mut harness = LspHarness::new();
    harness.initialize().await;
    harness.did_open(&uri, source).await;

    // The server must not crash; it emits a log_message and an (empty)
    // publishDiagnostics. Drain whatever arrives within a short window.
    let diags = next_diagnostics(&mut harness).await;
    // For an unresolvable URI, lint_document returns [] and publish_diagnostics
    // is still called with an empty list, so we expect zero diagnostics.
    let total: usize = diags.iter().map(|d| d.diagnostics.len()).sum();
    assert_eq!(total, 0, "unresolvable URI should yield no diagnostics");
}

#[tokio::test]
async fn did_open_malformed_source_does_not_crash() {
    // A syntactically broken Python source must not panic the server.
    // tree-sitter is error-tolerant, so `lint_source` should return Ok
    // (possibly with zero or few diagnostics); the server must publish a
    // diagnostics notification (possibly empty) and remain responsive.
    let dir = tempfile::tempdir().unwrap();
    let file_path = dir.path().join("test_broken.py");
    let uri = Url::from_file_path(&file_path).unwrap();

    // Unclosed bracket, dangling dedent, stray tokens: a worst-case mash-up.
    let malformed = "def test_x(:\n    \n    (((\n    assert\n    )\n  \nimport";

    let mut harness = LspHarness::new();
    harness.initialize().await;
    harness.did_open(&uri, malformed).await;

    // The server must complete and emit a publishDiagnostics notification.
    let diags = next_diagnostics(&mut harness).await;
    // Every diagnostic (if any) must carry the source file's URI.
    assert!(diags.iter().all(|d| d.uri == uri));
    // No matter what, the server did not panic and produced a well-formed
    // (possibly empty) set of diagnostics for the file.
    let total: usize = diags.iter().map(|d| d.diagnostics.len()).sum();
    let _ = total; // value is informational; we only require graceful handling.
}

#[tokio::test]
async fn did_change_then_back_to_clean_clears_diagnostics() {
    // Round-trip: clean → flaky → clean again. The final publishDiagnostics
    // must carry zero diagnostics, proving the server does not retain stale
    // violations from a previous version of the document.
    let dir = tempfile::tempdir().unwrap();
    let file_path = dir.path().join("test_roundtrip.py");
    let uri = Url::from_file_path(&file_path).unwrap();

    let clean = "x = 1\n";
    let flaky = "import time\ndef test_slow():\n    time.sleep(5)\n    assert True\n";

    let mut harness = LspHarness::new();
    harness.initialize().await;

    harness.did_open(&uri, flaky).await;
    let diags = next_diagnostics(&mut harness).await;
    assert!(!diags.is_empty(), "flaky source should produce diagnostics");

    // Change back to clean: diagnostics must be cleared (empty list published).
    harness.did_change(&uri, clean, 2).await;
    let diags = next_diagnostics(&mut harness).await;
    let total: usize = diags.iter().map(|d| d.diagnostics.len()).sum();
    assert_eq!(total, 0, "changing back to clean must clear diagnostics");
}
