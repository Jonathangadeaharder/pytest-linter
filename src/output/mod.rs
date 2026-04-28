use crate::models::Violation;
use anyhow::Result;

// Re-export SARIF formatter module
pub mod sarif;

/// Public API: Format violations as SARIF.
pub fn format_sarif(violations: &[Violation]) -> Result<String> {
    sarif::format_sarif(violations)
}

/// Public API: Format violations as pretty JSON (raw violations).
pub fn format_json(violations: &[Violation]) -> Result<String> {
    // Move simple JSON wrapping from engine into output layer.
    serde_json::to_string_pretty(violations).map_err(|e| e.into())
}

/// Public API: Terminal formatter signature (not implemented in this module yet).
pub fn format_terminal(_violations: &[Violation], _no_color: bool) -> Result<String> {
    // Signature provided for compatibility; actual terminal formatting remains in engine.rs for now.
    unimplemented!("Terminal formatter is not implemented in output::mod yet")
}
