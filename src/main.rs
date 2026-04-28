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

    let has_errors = pytest_linter::engine::run_linter(
        &cli.paths,
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
