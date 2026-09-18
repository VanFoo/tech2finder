#!/usr/bin/env bash
#
# Set up a working development environment for tech2finder.
#
# Safe to run repeatedly: every step checks before acting. Used both by the
# devcontainer's postCreateCommand and by hand, so there is one definition of
# "a working environment" rather than two that drift apart.
#
#   ./scripts/setup.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

say() { printf '\033[1m==>\033[0m %s\n' "$1"; }
note() { printf '    %s\n' "$1"; }

# ---------------------------------------------------------------- uv ---------
# uv manages both the virtualenv and the Python interpreter itself, so this
# works even on an image without pip — which is what the devcontainer's
# TypeScript/Node base actually is.

export PATH="$HOME/.local/bin:$PATH"

# The workspace and uv's cache sit on different filesystems in a devcontainer,
# so hardlinking is unavailable and uv warns about it on every sync. Copying is
# the correct mode here, and saying so keeps the output readable.
export UV_LINK_MODE=copy

if command -v uv >/dev/null 2>&1; then
  say "uv already installed ($(uv --version))"
else
  say "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  hash -r
fi

# --------------------------------------------------------------- PATH --------
# The installer puts uv in ~/.local/bin, which is not on PATH in a fresh shell
# on every image. Add it once, guarded, so a new terminal finds uv.

for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [ -f "$rc" ] || continue
  if ! grep -qF '# tech2finder: uv on PATH' "$rc"; then
    say "Adding ~/.local/bin to PATH in $(basename "$rc")"
    printf '\n# tech2finder: uv on PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >>"$rc"
  fi
done

# ------------------------------------------------------- dependencies --------

say "Syncing dependencies"
uv sync --extra dev

# ------------------------------------------------------------- verify --------

say "Verifying"
uv run python -c 'import fastapi, jinja2, httpx' 2>/dev/null \
  && note "imports ok" \
  || { note "dependency import failed"; exit 1; }

if uv run pytest -q >/dev/null 2>&1; then
  note "test suite passes"
else
  note "test suite is failing — the environment is set up, but something else is wrong"
fi

cat <<'USAGE'

Ready. Common commands:

  uv run pytest                 tests
  uv run ruff check .           lint
  uv run ruff format .          format
  uv run mypy                   typecheck (strict)
  uv run python -m tech2finder  dev server on http://127.0.0.1:8000

If `uv` is not found in this shell, either open a new terminal or run:

  export PATH="$HOME/.local/bin:$PATH"

USAGE
