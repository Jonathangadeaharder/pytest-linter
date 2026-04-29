use std::path::PathBuf;

use anyhow::Result;
use lsp_server::{Connection, Message, Notification};
use lsp_types::{
    Diagnostic, DiagnosticSeverity, DidChangeConfigurationParams, DidChangeTextDocumentParams,
    DidOpenTextDocumentParams, InitializeParams, InitializeResult, Position, Range,
    ServerCapabilities, TextDocumentSyncCapability, TextDocumentSyncKind, TextDocumentSyncOptions,
    Url,
};
use pytest_linter::config::Config;

struct LspState {
    config: Config,
    workspace_root: Option<PathBuf>,
}

impl LspState {
    fn reload_config(&mut self) {
        if let Some(ref root) = self.workspace_root {
            if let Ok(cfg) = Config::discover(root) {
                self.config = cfg;
            }
        }
    }
}

fn main() -> Result<()> {
    let (connection, io_threads) = Connection::stdio();

    let (id, init_params) = connection.initialize_start()?;
    let init_params: InitializeParams = serde_json::from_value(init_params)?;

    let workspace_root = init_params
        .workspace_folders
        .as_ref()
        .and_then(|folders| folders.first())
        .and_then(|f| f.uri.to_file_path().ok())
        .or_else(|| {
            init_params
                .root_uri
                .as_ref()
                .and_then(|uri| uri.to_file_path().ok())
        });

    let config = match workspace_root.as_ref() {
        Some(root) => Config::discover(root)?,
        None => Config::default(),
    };

    let state = LspState {
        config,
        workspace_root,
    };

    let server_caps = ServerCapabilities {
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
    };

    let init_result = InitializeResult {
        capabilities: server_caps,
        server_info: Some(lsp_types::ServerInfo {
            name: "pytest-linter".to_string(),
            version: Some(env!("CARGO_PKG_VERSION").to_string()),
        }),
    };

    connection.initialize_finish(id, serde_json::to_value(init_result)?)?;

    main_loop(connection, state)?;

    io_threads.join()?;
    Ok(())
}

fn main_loop(connection: Connection, mut state: LspState) -> Result<()> {
    for msg in &connection.receiver {
        match msg {
            Message::Request(req) => {
                if connection.handle_shutdown(&req)? {
                    return Ok(());
                }
            }
            Message::Notification(not) => match not.method.as_str() {
                "textDocument/didOpen" => {
                    let params: DidOpenTextDocumentParams =
                        serde_json::from_value(not.params.clone())?;
                    let uri = &params.text_document.uri;
                    let text = &params.text_document.text;
                    if let Some(diagnostics) = lint_document(uri, text, &state) {
                        publish_diagnostics(&connection, uri.clone(), diagnostics)?;
                    }
                }
                "textDocument/didChange" => {
                    let params: DidChangeTextDocumentParams =
                        serde_json::from_value(not.params.clone())?;
                    let uri = &params.text_document.uri;
                    let text = params
                        .content_changes
                        .last()
                        .map(|c| c.text.clone())
                        .unwrap_or_default();
                    if let Some(diagnostics) = lint_document(uri, &text, &state) {
                        publish_diagnostics(&connection, uri.clone(), diagnostics)?;
                    }
                }
                "workspace/didChangeConfiguration" => {
                    let _params: DidChangeConfigurationParams =
                        serde_json::from_value(not.params.clone())?;
                    state.reload_config();
                }
                _ => {}
            },
            Message::Response(_) => {}
        }
    }
    Ok(())
}

fn lint_document(uri: &Url, text: &str, state: &LspState) -> Option<Vec<Diagnostic>> {
    let file_path = uri.to_file_path().ok()?;

    let engine = pytest_linter::engine::LintEngine::new(state.config.clone()).ok()?;
    let violations = engine.lint_source(text, &file_path).ok()?;

    let diagnostics = violations
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
            code: Some(lsp_types::NumberOrString::String(v.rule_id.clone())),
            source: Some("pytest-linter".to_string()),
            message: v.message,
            ..Diagnostic::default()
        })
        .collect();

    Some(diagnostics)
}

fn publish_diagnostics(
    connection: &Connection,
    uri: Url,
    diagnostics: Vec<Diagnostic>,
) -> Result<()> {
    let params = lsp_types::PublishDiagnosticsParams {
        uri,
        diagnostics,
        version: None,
    };
    let not = Notification {
        method: "textDocument/publishDiagnostics".to_string(),
        params: serde_json::to_value(params)?,
    };
    connection.sender.send(Message::Notification(not))?;
    Ok(())
}
