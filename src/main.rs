//! pytest-linter: detect test smells in Python/pytest test files.

use anyhow::Result;
use clap::Parser;
use pytest_linter::config::Config;
use std::path::PathBuf;
use std::process;

#[derive(Parser)]
#[command(name = "pytest-linter")]
#[command(about = "Detect test smells in Python/pytest test files")]
struct Cli {
    #[arg(required = true)]
    paths: Vec<PathBuf>,

    #[arg(long, value_parser = ["terminal", "json", "sarif"])]
    format: Option<String>,

    #[arg(long)]
    output: Option<PathBuf>,

    #[arg(long)]
    no_color: bool,

    #[arg(long)]
    incremental: bool,

    #[arg(long, default_value = "HEAD")]
    base: String,

    #[arg(long, conflicts_with = "check_baseline")]
    baseline: Option<PathBuf>,

    #[arg(long, conflicts_with = "baseline")]
    check_baseline: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    let mut config = Config::default();
    if let Some(loaded) = Config::from_pyproject(&cli.paths[0])? {
        config = loaded;
    }
    config = config.merge_cli(cli.format.clone(), cli.output.clone());

    let format_str = config
        .format
        .clone()
        .unwrap_or_else(|| "terminal".to_string());
    let output_path = config.output.clone();

    let paths = if cli.incremental {
        let changed = pytest_linter::engine::get_changed_files(&cli.base)?;
        if changed.is_empty() {
            eprintln!("No changed Python test files found.");
            process::exit(0);
        }
        changed
    } else {
        cli.paths.clone()
    };

    if let Some(ref baseline_path) = cli.baseline {
        let violations = pytest_linter::engine::collect_violations(&paths, config.clone())?;
        pytest_linter::engine::save_baseline(&violations, baseline_path)?;
        eprintln!("Baseline saved to {}", baseline_path.display());
        process::exit(0);
    }

    if let Some(ref baseline_path) = cli.check_baseline {
        let violations = pytest_linter::engine::collect_violations(&paths, config.clone())?;
        let baseline = pytest_linter::engine::load_baseline(baseline_path)?;
        let new_violations = pytest_linter::engine::filter_new_violations(&violations, &baseline);
        if new_violations.is_empty() {
            eprintln!(
                "No new violations found (baseline: {} violations)",
                baseline.len()
            );
            process::exit(0);
        }
        eprintln!(
            "{} new violations found (not in baseline)",
            new_violations.len()
        );
        match format_str.as_str() {
            "json" => {
                pytest_linter::engine::format_json_output(&new_violations, output_path.as_deref())?
            }
            "sarif" => {
                pytest_linter::engine::format_sarif_output(&new_violations, output_path.as_deref())?
            }
            _ => pytest_linter::engine::format_terminal_output(
                &new_violations,
                output_path.as_deref(),
                cli.no_color,
            )?,
        }
        process::exit(1);
    }

    let has_errors = pytest_linter::engine::run_linter(
        &paths,
        &format_str,
        output_path.as_deref(),
        cli.no_color,
        config,
    )?;

    if has_errors {
        process::exit(1);
    }

    Ok(())
}
