/// Criterion benchmark: lint a synthetic 100K-line test repository.
///
/// The fixture generates N test files each containing 10 test functions
/// that exercise a variety of smells, giving a realistic workload for the
/// tree-sitter parser and rule engine without requiring an external checkout.
use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use pytest_linter::{config::Config, engine::LintEngine};
use std::path::PathBuf;
use tempfile::TempDir;

/// Return Python source for a single test module.  `file_idx` is embedded in
/// symbol names so each file is unique (avoids filename-collision shortcuts).
fn make_test_module(file_idx: usize, num_tests: usize) -> String {
    let mut src = String::from("import time\nimport os\n\n");
    for t in 0..num_tests {
        // Alternate between clean tests and various smell patterns so that
        // multiple rules fire, giving a representative rule-check workload.
        match t % 5 {
            0 => {
                // FLK-001: time.sleep
                src.push_str(&format!(
                    "def test_sleep_{file_idx}_{t}():\n    time.sleep(0.1)\n    assert True\n\n"
                ));
            }
            1 => {
                // MNT-004: no assertion
                src.push_str(&format!(
                    "def test_no_assert_{file_idx}_{t}():\n    x = 1 + 1\n\n"
                ));
            }
            2 => {
                // MNT-006: assertion roulette (>3 assertions)
                src.push_str(&format!(
                    "def test_roulette_{file_idx}_{t}():\n    assert 1 == 1\n    assert 2 == 2\n    assert 3 == 3\n    assert 4 == 4\n\n"
                ));
            }
            3 => {
                // FLK-004: cwd dependency (os.getcwd)
                src.push_str(&format!(
                    "def test_cwd_{file_idx}_{t}():\n    path = os.getcwd()\n    assert path\n\n"
                ));
            }
            _ => {
                // Clean test — no smells
                src.push_str(&format!(
                    "def test_clean_{file_idx}_{t}(tmp_path):\n    result = 1 + 1\n    assert result == 2\n\n"
                ));
            }
        }
    }
    src
}

/// Write `num_files` test files (each with `tests_per_file` tests) into a
/// temporary directory and return the dir + root path.
fn build_repo(num_files: usize, tests_per_file: usize) -> (TempDir, PathBuf) {
    let dir = tempfile::tempdir().expect("create tempdir");
    for i in 0..num_files {
        let name = format!("test_module_{i:04}.py");
        let path = dir.path().join(&name);
        let src = make_test_module(i, tests_per_file);
        std::fs::write(&path, src).expect("write test file");
    }
    let root = dir.path().to_path_buf();
    (dir, root)
}

fn bench_engine(c: &mut Criterion) {
    // We benchmark two sizes:
    //   "small"  — 100 files × 10 tests = 1 000 test functions
    //   "medium" — 500 files × 20 tests = 10 000 test functions
    // (A true 100K-line repo would use ~1 000 files × 100 tests but that
    //  takes several seconds per iteration; medium gives the shape of the
    //  curve and CI stays fast.)
    let configs: &[(&str, usize, usize)] = &[
        ("100_files_10_tests", 100, 10),
        ("500_files_20_tests", 500, 20),
    ];

    let mut group = c.benchmark_group("engine_lint");
    // Use fewer samples so CI does not time out; defaults are fine locally.
    group.sample_size(10);

    for &(label, num_files, tests_per_file) in configs {
        // Build the repo once outside the benchmark loop.
        let (_dir, root) = build_repo(num_files, tests_per_file);
        let paths = vec![root.clone()];

        // Create engine once outside the benchmark loop - engine creation involves
        // rule collection and filtering which should not be measured.
        let engine = LintEngine::new(Config::default()).expect("create engine");

        group.bench_with_input(BenchmarkId::from_parameter(label), label, |b, _| {
            b.iter(|| engine.lint_paths(&paths).expect("lint"));
        });

        // `_dir` is dropped here which cleans up the tempdir.
    }

    group.finish();
}

criterion_group!(benches, bench_engine);
criterion_main!(benches);
