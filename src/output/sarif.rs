use crate::models::{Severity, Violation};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use serde_json;

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SarifLog {
    #[serde(rename = "$schema")]
    pub schema: String,
    pub version: String,
    pub runs: Vec<Run>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Run {
    pub tool: Tool,
    pub results: Vec<SarifResult>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Tool {
    pub driver: ToolComponent,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolComponent {
    pub name: String,
    pub version: String,
    pub rules: Vec<Rule>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Rule {
    pub id: String,
    pub name: String,
    pub short_description: Message,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub help_uri: Option<String>,
    pub default_configuration: ReportingConfiguration,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Message {
    pub text: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReportingConfiguration {
    pub level: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SarifResult {
    #[serde(rename = "ruleId")]
    pub rule_id: String,
    pub level: String,
    pub message: Message,
    pub locations: Vec<Location>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Location {
    #[serde(rename = "physicalLocation")]
    pub physical_location: PhysicalLocation,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PhysicalLocation {
    #[serde(rename = "artifactLocation")]
    pub artifact_location: ArtifactLocation,
    pub region: Region,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ArtifactLocation {
    pub uri: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Region {
    #[serde(rename = "startLine")]
    pub start_line: usize,
    #[serde(rename = "startColumn")]
    pub start_column: Option<usize>,
}

/// Convert a file path to an RFC 3986 file URI.
fn path_to_file_uri(path: &std::path::Path) -> String {
    let path_str = path.display().to_string();
    // On Windows, convert backslashes to forward slashes
    let normalized = path_str.replace('\\', "/");
    if normalized.starts_with('/') {
        format!("file://{}", normalized)
    } else {
        // Relative path - use as-is
        normalized
    }
}

/// Convert violations into a SARIF log structure.
pub fn violations_to_sarif(violations: &[Violation]) -> SarifLog {
    // Collect unique rules for the driver
    let mut rules_map: HashMap<String, Rule> = HashMap::new();
    let mut results: Vec<SarifResult> = Vec::new();

    for v in violations {
        let level = match v.severity {
            Severity::Error => "error",
            Severity::Warning => "warning",
            Severity::Info => "note",
        }
        .to_string();

        // Ensure the rule exists in the driver metadata
        rules_map.entry(v.rule_id.clone()).or_insert_with(|| Rule {
            id: v.rule_id.clone(),
            name: v.rule_name.clone(),
            short_description: Message {
                text: v.rule_name.clone(),
            },
            help_uri: Some(format!(
                "https://github.com/Jonathangadeaharder/pytest-linter/blob/main/docs/rules/{}.md",
                v.rule_id
            )),
            default_configuration: ReportingConfiguration {
                level: level.clone(),
            },
        });

        let result = SarifResult {
            rule_id: v.rule_id.clone(),
            level,
            message: Message {
                text: v.message.clone(),
            },
            locations: vec![Location {
                physical_location: PhysicalLocation {
                    artifact_location: ArtifactLocation {
                        uri: path_to_file_uri(&v.file_path),
                    },
                    region: Region {
                        start_line: v.line,
                        start_column: v.col,
                    },
                },
            }],
        };
        results.push(result);
    }

    // Sort rules by ID for deterministic output
    let mut rules: Vec<Rule> = rules_map.into_values().collect();
    rules.sort_by(|a, b| a.id.cmp(&b.id));

    let run = Run {
        tool: Tool {
            driver: ToolComponent {
                name: "pytest-linter".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
                rules,
            },
        },
        results,
    };

    SarifLog {
        schema: "https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-2.1.0.json".to_string(),
        version: "2.1.0".to_string(),
        runs: vec![run],
    }
}

/// Public API: format violations as SARIF JSON string.
pub fn format_sarif(violations: &[Violation]) -> anyhow::Result<String> {
    let log = violations_to_sarif(violations);
    let json = serde_json::to_string_pretty(&log)?;
    Ok(json)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Category, Severity};
    use std::path::PathBuf;

    #[test]
    fn test_sarif_json_fields_present() {
        let v = Violation {
            rule_id: "R1".to_string(),
            rule_name: "Rule One".to_string(),
            severity: Severity::Error,
            category: Category::Flakiness,
            message: "boom".to_string(),
            file_path: PathBuf::from("a.py"),
            line: 10,
            col: Some(2),
            suggestion: None,
            test_name: None,
        };
        let log = violations_to_sarif(&[v]);
        assert_eq!(log.version, "2.1.0");
        assert_eq!(log.runs.len(), 1);
        let run = &log.runs[0];
        assert_eq!(run.results.len(), 1);
        assert_eq!(run.results[0].rule_id, "R1");
        assert_eq!(run.results[0].level, "error");
    }

    #[test]
    fn test_sarif_rules_sorted() {
        let violations = vec![
            Violation {
                rule_id: "R2".to_string(),
                rule_name: "Rule Two".to_string(),
                severity: Severity::Warning,
                category: Category::Flakiness,
                message: "test".to_string(),
                file_path: PathBuf::from("b.py"),
                line: 5,
                col: None,
                suggestion: None,
                test_name: None,
            },
            Violation {
                rule_id: "R1".to_string(),
                rule_name: "Rule One".to_string(),
                severity: Severity::Error,
                category: Category::Flakiness,
                message: "test".to_string(),
                file_path: PathBuf::from("a.py"),
                line: 1,
                col: None,
                suggestion: None,
                test_name: None,
            },
        ];
        let log = violations_to_sarif(&violations);
        let rules = &log.runs[0].tool.driver.rules;
        assert_eq!(rules[0].id, "R1");
        assert_eq!(rules[1].id, "R2");
    }

    #[test]
    fn test_sarif_file_uri() {
        assert_eq!(
            path_to_file_uri(&PathBuf::from("/tmp/test.py")),
            "file:///tmp/test.py"
        );
        assert_eq!(
            path_to_file_uri(&PathBuf::from("relative.py")),
            "relative.py"
        );
    }
}
