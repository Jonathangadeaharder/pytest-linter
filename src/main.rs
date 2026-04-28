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
