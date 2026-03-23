#!/bin/bash
# Install git hooks for the autorefine public repo.
# Run once after cloning: bash autorefine/hooks/install.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_DIR="$REPO_ROOT/.git/hooks"

cp "$SCRIPT_DIR/pre-commit" "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/pre-commit"

echo "Hooks installed to $HOOK_DIR"
