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
