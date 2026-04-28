"""Python wrapper for the pytest-linter Rust binary."""

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

__version__ = "0.1.0"

BINARY_NAME = "pytest-linter"


def _get_binary_path() -> str:
    """Find or download the pytest-linter binary."""
    # Check if binary is in PATH
    path = subprocess.run(
        ["which", BINARY_NAME] if os.name != "nt" else ["where", BINARY_NAME],
        capture_output=True,
        text=True,
    )
    if path.returncode == 0:
        return path.stdout.strip()

    # Check local bin directory
    local_bin = Path.home() / ".local" / "bin" / BINARY_NAME
    if local_bin.exists():
        return str(local_bin)

    # Try to download
    return _download_binary()


def _download_binary() -> str:
    """Download the appropriate binary for the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine == "arm64":
            target = "aarch64-apple-darwin"
        else:
            target = "x86_64-apple-darwin"
    elif system == "linux":
        target = "x86_64-unknown-linux-gnu"
    elif system == "windows":
        target = "x86_64-pc-windows-msvc"
    else:
        raise RuntimeError(f"Unsupported platform: {system} {machine}")

    url = f"https://github.com/Jonathangadeaharder/pytest-linter/releases/latest/download/pytest-linter-{target}.tar.gz"

    bin_dir = Path.home() / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary_path = bin_dir / BINARY_NAME

    print(f"Downloading pytest-linter for {target}...", file=sys.stderr)

    import urllib.request
    import tarfile

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        urllib.request.urlretrieve(url, tmp.name)
        with tarfile.open(tmp.name) as tar:
            for member in tar.getmembers():
                member_path = os.path.normpath(os.path.join(bin_dir, member.name))
                if not member_path.startswith(os.path.normpath(str(bin_dir)) + os.sep) and member_path != os.path.normpath(str(bin_dir)):
                    raise RuntimeError(f"Attempted path traversal in tar: {member.name}")
                tar.extract(member, path=bin_dir)
        os.unlink(tmp.name)

    binary_path.chmod(0o755)
    return str(binary_path)


def main():
    """Run the pytest-linter binary with the given arguments."""
    binary = _get_binary_path()
    result = subprocess.run([binary] + sys.argv[1:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
