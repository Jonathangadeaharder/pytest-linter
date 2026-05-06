use std::sync::{Arc, RwLock};

use pytest_linter::config::Config;
use tower_lsp::lsp_types::*;
use tower_lsp::Client;

struct Backend {
    client: Client,
    config: Arc<RwLock<Config>>,
}

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
                #[allow(deprecated)]
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
        let config = self.config.read().unwrap().clone();
        let diagnostics = Self::lint_document(&uri, &text, &config);
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
        let config = self.config.read().unwrap().clone();
        let diagnostics = Self::lint_document(&uri, &text, &config);
        self.client
            .publish_diagnostics(uri, diagnostics, None)
            .await;
    }
}

impl Backend {
    fn lint_document(uri: &Url, text: &str, config: &Config) -> Vec<Diagnostic> {
        let file_path = match uri.to_file_path() {
            Ok(p) => p,
            Err(_) => return vec![],
        };

        let engine = match pytest_linter::engine::LintEngine::new(config.clone()) {
            Ok(e) => e,
            Err(_) => return vec![],
        };

        let violations = match engine.lint_source(text, &file_path) {
            Ok(v) => v,
            Err(_) => return vec![],
        };

        violations
            .into_iter()
            .map(|v| Diagnostic {
                range: Range {
                    start: Position {
                        line: v.line.saturating_sub(1) as u32,
                        character: v.col.map(|c| c.saturating_sub(1) as u32).unwrap_or(0),
                    },
                    end: Position {
                        line: v.line.saturating_sub(1) as u32,
                        character: v.col.map(|c| c.saturating_sub(1) as u32).unwrap_or(0),
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
            })
            .collect()
    }
}

#[tokio::main]
async fn main() {
    let (service, socket) = tower_lsp::LspService::new(|client| Backend {
        client,
        config: Arc::new(RwLock::new(Config::default())),
    });

    tower_lsp::Server::new(tokio::io::stdin(), tokio::io::stdout(), socket)
        .serve(service)
        .await;
}
