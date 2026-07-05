use std::sync::{Arc, RwLock};
use std::time::Duration;

use pytest_linter::config::Config;
use tokio::sync::Mutex;
use tokio::task::JoinHandle;
use tower_lsp::lsp_types::*;
use tower_lsp::Client;

struct Backend {
    client: Client,
    config: Arc<RwLock<Config>>,
    pending_lint: Mutex<Option<JoinHandle<()>>>,
}

const DEBOUNCE_MS: u64 = 300;

#[tower_lsp::async_trait]
impl tower_lsp::LanguageServer for Backend {
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

#[tokio::main]
async fn main() {
    let (service, socket) = tower_lsp::LspService::new(|client| Backend {
        client,
        config: Arc::new(RwLock::new(Config::default())),
        pending_lint: Mutex::new(None),
    });

    tower_lsp::Server::new(tokio::io::stdin(), tokio::io::stdout(), socket)
        .serve(service)
        .await;
}
