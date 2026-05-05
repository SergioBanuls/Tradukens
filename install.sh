#!/bin/sh
set -eu

REPO_URL="${TRADUKENS_REPO_URL:-https://github.com/SergioBanuls/Tradukens.git}"
INSTALL_SOURCE="${TRADUKENS_INSTALL_SOURCE:-git+$REPO_URL}"

say() {
  printf '%s\n' "$1"
}

fail() {
  printf 'tradukens install failed: %s\n' "$1" >&2
  exit 1
}

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) fail "unsupported operating system: $(uname -s)" ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export PATH

if ! command -v uv >/dev/null 2>&1; then
  fail "uv was installed but is not available on PATH"
fi

say "Installing Tradukens from $INSTALL_SOURCE..."
uv tool install --python 3.12 --force "$INSTALL_SOURCE"

if ! command -v tradukens >/dev/null 2>&1; then
  fail "tradukens was installed but is not available on PATH"
fi

say "Downloading local translation models..."
tradukens setup --lang es

say "Checking installation..."
tradukens doctor || true

say ""
say "Tradukens installed."
say "Try one of:"
say "  tradukens codex"
say "  tradukens claude"
say "  tradukens opencode"
