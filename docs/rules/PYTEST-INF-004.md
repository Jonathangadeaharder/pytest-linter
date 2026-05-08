# PYTEST-INF-004 — MacOsCopyArtefactRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-INF-004` |
| **Name** | MacOsCopyArtefactRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test uses macOS Finder copy artefact filename or shutil.copy — may cause cross-platform failures

## Rationale

On macOS, the Finder creates duplicate files with trailing ` N` suffixes (e.g., `file 2.txt`). Tests referencing these artefact filenames will fail on non-macOS systems. Additionally, `shutil.copy2` and `shutil.copy` preserve extended attributes and resource forks (xattr/`._` files), causing cross-platform test failures.

## Suggestion

Normalize filenames to remove Finder copy suffixes, or use `tmp_path` fixtures

## Examples

### ❌ Bad

```python
def test_file_copy():
    shutil.copy2("source.dat", "dest.dat")

def test_reads_artefact():
    content = Path("data 2.txt").read_text()
```

### ✅ Good

```python
def test_file_copy(tmp_path):
    dest = tmp_path / "dest.dat"
    dest.write_bytes(Path("source.dat").read_bytes())

def test_reads_data():
    content = Path("data.txt").read_text()
```
