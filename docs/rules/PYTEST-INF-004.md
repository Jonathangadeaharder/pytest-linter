# PYTEST-INF-004 — MacOsCopyArtefactRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-INF-004` |
| **Name** | MacOsCopyArtefactRule |
| **Severity** | Info |
| **Category** | Flakiness |

## Message

> Test uses shutil.copy/copy2/copyfile — may copy macOS metadata artefacts

## Rationale

On macOS, `shutil.copy2` and `shutil.copy` preserve extended attributes and resource forks (xattr/`._` files). This can cause tests to fail when run on different platforms or when comparing file contents, as the metadata differs.

## Suggestion

Use `tmp_path.joinpath().write_bytes()` or `shutil.copy` without preserving metadata

## Examples

### ❌ Bad

```python
def test_file_copy():
    shutil.copy2("source.dat", "dest.dat")
```

### ✅ Good

```python
def test_file_copy(tmp_path):
    dest = tmp_path / "dest.dat"
    dest.write_bytes(Path("source.dat").read_bytes())
```
