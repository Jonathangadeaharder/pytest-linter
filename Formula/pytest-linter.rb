class PytestLinter < Formula
  desc "Fast, tree-sitter-powered test smell detector for pytest"
  homepage "https://github.com/Jonathangadeaharder/pytest-linter"
  url "https://github.com/Jonathangadeaharder/pytest-linter/releases/download/v#{version}/pytest-linter-aarch64-apple-darwin.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  version "0.1.0"
  license "MIT"

  on_intel do
    url "https://github.com/Jonathangadeaharder/pytest-linter/releases/download/v#{version}/pytest-linter-x86_64-apple-darwin.tar.gz"
    sha256 "PLACEHOLDER_SHA256_INTEL"
  end

  def install
    bin.install "pytest-linter"
  end

  test do
    system bin / "pytest-linter", "--help"
  end
end
