use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;
use std::process;

#[derive(Parser)]
#[command(name = "pytest-linter")]
#[command(about = "Detect test smells in Python/pytest test files")]
struct Cli {
    #[arg(required = true)]
    paths: Vec<PathBuf>,

    #[arg(long, default_value = "terminal", value_parser = ["terminal", "json"])]
    format: String,

    #[arg(long)]
    output: Option<PathBuf>,

    #[arg(long)]
    no_color: bool,
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    let has_errors = pytest_linter::engine::run_linter(
        &cli.paths,
        &cli.format,
        cli.output.as_deref(),
        cli.no_color,
    )?;

    if has_errors {
        process::exit(1);
    }

    Ok(())
}
