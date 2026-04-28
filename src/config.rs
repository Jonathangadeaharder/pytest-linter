use std::collections::HashMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

use crate::models::Severity;

/// Per-rule configuration options for pytest-linter
#[derive(Debug, Deserialize, Clone, Default)]
pub struct RuleConfig {
    /// None means use the default (true). Some(false) disables the rule.
    pub enabled: Option<bool>,
    /// Optional severity override for this rule
    pub severity: Option<Severity>,
}

/// TOML section [tool.pytest-linter] in a pyproject.toml
#[derive(Debug, Deserialize, Clone, Default)]
pub struct ToolConfig {
    /// Per-rule overrides. Key is the rule ID (e.g., "PYTEST-FLK-001")
    pub rules: Option<HashMap<String, RuleConfig>>,
    /// Optional output format override
    pub format: Option<String>,
    /// Optional output path override
    pub output: Option<PathBuf>,
}

/// Final, merged configuration used by the linter
#[derive(Debug, Clone)]
pub struct Config {
    /// Resolved rule configurations. Each rule has its own enabled flag (defaults applied)
    pub rules: HashMap<String, RuleConfig>,
    /// Optional global output format override
    pub format: Option<String>,
    /// Optional global output path override
    pub output: Option<PathBuf>,
}

impl Default for Config {
    fn default() -> Self {
        let mut rules = HashMap::new();
        for rid in Self::default_rule_ids() {
            rules.insert(
                rid.to_string(),
                RuleConfig {
                    enabled: Some(true),
                    severity: None,
                },
            );
        }
        Config {
            rules,
            format: None,
            output: None,
        }
    }
}

impl Config {
    // 30 rule IDs to be enabled by default
    fn default_rule_ids() -> Vec<&'static str> {
        vec![
            "PYTEST-FLK-001",
            "PYTEST-FLK-002",
            "PYTEST-FLK-003",
            "PYTEST-FLK-004",
            "PYTEST-FLK-005",
            "PYTEST-FLK-008",
            "PYTEST-FLK-009",
            "PYTEST-XDIST-001",
            "PYTEST-XDIST-002",
            "PYTEST-MNT-001",
            "PYTEST-MNT-002",
            "PYTEST-MNT-003",
            "PYTEST-MNT-004",
            "PYTEST-MNT-005",
            "PYTEST-MNT-006",
            "PYTEST-MNT-007",
            "PYTEST-BDD-001",
            "PYTEST-PBT-001",
            "PYTEST-PARAM-001",
            "PYTEST-PARAM-002",
            "PYTEST-PARAM-003",
            "PYTEST-DBC-001",
            "PYTEST-FIX-001",
            "PYTEST-FIX-003",
            "PYTEST-FIX-004",
            "PYTEST-FIX-005",
            "PYTEST-FIX-006",
            "PYTEST-FIX-007",
            "PYTEST-FIX-008",
            "PYTEST-FIX-009",
        ]
    }

    /// Check if a specific rule is enabled. Unknown rules are treated as enabled.
    pub fn is_rule_enabled(&self, rule_id: &str) -> bool {
        match self.rules.get(rule_id) {
            Some(rc) => rc.enabled.unwrap_or(true), // None means default (true)
            None => true,                           // Unknown rules default to enabled per spec
        }
    }

    /// Determine the severity for a given rule, using an override if present, otherwise the provided default
    pub fn rule_severity(&self, rule_id: &str, default: Severity) -> Severity {
        if let Some(rc) = self.rules.get(rule_id) {
            rc.severity.unwrap_or(default)
        } else {
            default
        }
    }

    /// Load configuration by walking up from `dir` to find pyproject.toml and the [tool.pytest-linter] section
    pub fn from_pyproject(dir: &Path) -> Result<Option<Self>> {
        // Start at dir and walk up until filesystem root
        let mut current = dir;
        loop {
            let candidate = current.join("pyproject.toml");
            if candidate.exists() {
                // Read and parse TOML
                let contents = std::fs::read_to_string(&candidate)
                    .with_context(|| format!("read {}", candidate.display()))?;
                // Deserialize the [tool.pytest-linter] section by deserializing the whole TOML and pulling the nested table
                let full: toml::Value = toml::from_str(&contents)
                    .with_context(|| format!("parse TOML in {}", candidate.display()))?;

                // Convert the nested [tool.pytest-linter] into ToolConfig via intermediate path
                let tool_table = full
                    .get("tool")
                    .and_then(|t| t.as_table())
                    .and_then(|t| t.get("pytest-linter"))
                    .cloned()
                    .unwrap_or_else(|| toml::Value::Table(toml::map::Map::new()));

                // If there is no real section, return None per contract
                let table = match tool_table.as_table() {
                    Some(t) => t,
                    None => return Ok(None),
                };
                if table.is_empty() {
                    return Ok(None);
                }

                // Direct deserialization from the toml::Value instead of roundtrip
                let tool_config: ToolConfig = tool_table.try_into().with_context(|| {
                    format!(
                        "deserialize tool.pytest-linter from {}",
                        candidate.display()
                    )
                })?;

                // Start from defaults and apply overrides from the TOML
                let mut cfg = Config::default();
                if let Some(rules) = tool_config.rules {
                    for (id, override_rc) in rules.into_iter() {
                        cfg.rules
                            .entry(id)
                            .and_modify(|existing| {
                                if let Some(e) = override_rc.enabled {
                                    existing.enabled = Some(e);
                                }
                                if let Some(sev) = override_rc.severity {
                                    existing.severity = Some(sev);
                                }
                            })
                            .or_insert(RuleConfig {
                                enabled: override_rc.enabled,
                                severity: override_rc.severity,
                            });
                    }
                }
                if tool_config.format.is_some() {
                    cfg.format = tool_config.format;
                }
                // Resolve relative output paths against the config file location
                if let Some(output_path) = tool_config.output {
                    if output_path.is_absolute() {
                        cfg.output = Some(output_path);
                    } else {
                        cfg.output = Some(
                            candidate
                                .parent()
                                .unwrap_or(Path::new("."))
                                .join(output_path),
                        );
                    }
                }

                return Ok(Some(cfg));
            }

            // If we reached filesystem root, stop
            match current.parent() {
                Some(parent) => current = parent,
                None => break,
            }
        }
        Ok(None)
    }

    /// Apply CLI overrides on top of existing config. If value is None, keep current value
    pub fn merge_cli(mut self, format: Option<String>, output: Option<PathBuf>) -> Self {
        if format.is_some() {
            self.format = format;
        }
        if output.is_some() {
            self.output = output;
        }
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_has_30_rules_enabled() {
        let cfg = Config::default();
        assert_eq!(cfg.rules.len(), 30);
        for rid in Config::default_rule_ids() {
            assert!(
                cfg.is_rule_enabled(rid),
                "rule {} should be enabled by default",
                rid
            );
        }
    }

    #[test]
    fn test_is_rule_enabled_variants() {
        let mut cfg = Config::default();
        cfg.rules.insert(
            "UNKNOWN-001".to_string(),
            RuleConfig {
                enabled: Some(false),
                severity: None,
            },
        );
        assert_eq!(cfg.is_rule_enabled("UNKNOWN-001"), false);
        assert_eq!(cfg.is_rule_enabled("PYTEST-FLK-001"), true);
        // Unknown rule (not present) should default to enabled
        assert_eq!(cfg.is_rule_enabled("SOME-NONEXISTENT"), true);
    }

    #[test]
    fn test_rule_severity_override_and_default() {
        let mut cfg = Config::default();
        // Override severity for a known rule
        cfg.rules.insert(
            "PYTEST-FLK-001".to_string(),
            RuleConfig {
                enabled: Some(true),
                severity: Some(Severity::Info),
            },
        );
        assert_eq!(
            cfg.rule_severity("PYTEST-FLK-001", Severity::Warning),
            Severity::Info
        );
        // Unknown rule should return the provided default
        assert_eq!(
            cfg.rule_severity("UNKNOWN-001", Severity::Error),
            Severity::Error
        );
    }

    #[test]
    fn test_from_pyproject_none_when_missing() {
        let dir = std::env::temp_dir();
        let res = Config::from_pyproject(&dir).unwrap();
        assert!(res.is_none());
    }

    #[test]
    fn test_from_pyproject_parses_valid_toml() {
        // Create a temporary directory and pyproject.toml with overrides
        let dir = tempfile::tempdir().unwrap();
        let toml_content = r#"
[tool.pytest-linter]
format = "json"
output = "report.json"

[tool.pytest-linter.rules.PYTEST-FLK-001]
enabled = false
severity = "warning"

[tool.pytest-linter.rules.PYTEST-MNT-001]
severity = "info"
"#;
        std::fs::write(dir.path().join("pyproject.toml"), toml_content).unwrap();

        let cfg = Config::from_pyproject(dir.path()).unwrap().unwrap();
        // format/output overrides
        assert_eq!(cfg.format, Some("json".to_string()));
        // Output should be resolved relative to the config file location
        assert_eq!(cfg.output, Some(dir.path().join("report.json")));
        // overrides applied for PYTEST-FLK-001
        let rc = cfg.rules.get("PYTEST-FLK-001").unwrap();
        assert_eq!(rc.enabled, Some(false));
        assert_eq!(rc.severity, Some(Severity::Warning));
        // PYTEST-MNT-001 severity override
        let rc2 = cfg.rules.get("PYTEST-MNT-001").unwrap();
        assert_eq!(rc2.severity, Some(Severity::Info));
    }

    #[test]
    fn test_merge_cli_overrides() {
        let cfg = Config::default();
        let merged = cfg.merge_cli(Some("json".to_string()), Some(PathBuf::from("out.log")));
        assert_eq!(merged.format, Some("json".to_string()));
        assert_eq!(merged.output, Some(PathBuf::from("out.log")));
    }
}
