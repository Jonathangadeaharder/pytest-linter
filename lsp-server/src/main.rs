use pytest_linter::config::Config;
use pytest_linter::engine::collect_violations;
use std::path::PathBuf;
use tower_lsp::jsonrpc::Result;
use tower_lsp::lsp_types::*;
use tower_lsp::{Client, LanguageServer, LspService, Server};

#[derive(Debug)]
struct Backend {
    client: Client,
}

#[tower_lsp::async_trait]
impl LanguageServer for Backend {
    async fn initialize(&self, _: InitializeParams) -> Result<InitializeResult> {
        Ok(InitializeResult {
            capabilities: ServerCapabilities {
                text_document_sync: Some(TextDocumentSyncCapability::Kind(
                    TextDocumentSyncKind::FULL,
                )),
                diagnostic_provider: Some(DiagnosticServerCapabilities::Options(
                    DiagnosticOptions {
                        identifier: Some("pytest-linter".to_string()),
                        inter_file_dependencies: true,
                        workspace_diagnostics: false,
                        work_done_progress_options: WorkDoneProgressOptions::default(),
                    },
                )),
                ..Default::default()
            },
            ..Default::default()
        })
    }

    async fn initialized(&self, _: InitializedParams) {
        self.client
            .log_message(MessageType::INFO, "pytest-linter LSP server initialized")
            .await;
    }

    async fn shutdown(&self) -> Result<()> {
        Ok(())
    }

    async fn did_open(&self, params: DidOpenTextDocumentParams) {
        let uri = params.text_document.uri;
        let text = params.text_document.text;
        self.publish_diagnostics(uri, text).await;
    }

    async fn did_change(&self, params: DidChangeTextDocumentParams) {
        let uri = params.text_document.uri;
        if let Some(change) = params.content_changes.into_iter().last() {
            self.publish_diagnostics(uri, change.text).await;
        }
    }

    async fn did_save(&self, params: DidSaveTextDocumentParams) {
        let uri = params.text_document.uri;
        if let Some(text) = params.text {
            self.publish_diagnostics(uri, text).await;
        }
    }
}

impl Backend {
    async fn publish_diagnostics(&self, uri: Url, _text: String) {
        let path = uri.to_file_path().unwrap_or_else(|_| PathBuf::from(uri.as_str()));
        let config = Config::default();
        let violations = collect_violations(&[path.clone()], config).unwrap_or_default();

        let diagnostics: Vec<Diagnostic> = violations
            .into_iter()
            .map(|v| {
                let severity = match v.severity {
                    pytest_linter::models::Severity::Error => DiagnosticSeverity::ERROR,
                    pytest_linter::models::Severity::Warning => DiagnosticSeverity::WARNING,
                    pytest_linter::models::Severity::Info => DiagnosticSeverity::INFORMATION,
                };
                Diagnostic {
                    range: Range {
                        start: Position {
                            line: (v.line as u32).saturating_sub(1),
                            character: v.col.map_or(0, |c| (c as u32).saturating_sub(1)),
                        },
                        end: Position {
                            line: (v.line as u32).saturating_sub(1),
                            character: v.col.map_or(0, |c| (c as u32).saturating_sub(1)) + 1,
                        },
                    },
                    severity: Some(severity),
                    code: Some(NumberOrString::String(v.rule_id)),
                    source: Some("pytest-linter".to_string()),
                    message: v.message,
                    ..Default::default()
                }
            })
            .collect();

        self.client
            .publish_diagnostics(uri, diagnostics, None)
            .await;
    }
}

#[tokio::main]
async fn main() {
    let stdin = tokio::io::stdin();
    let stdout = tokio::io::stdout();

    let (service, socket) = LspService::new(|client| Backend { client });
    Server::new(stdin, stdout, socket).serve(service).await;
}
