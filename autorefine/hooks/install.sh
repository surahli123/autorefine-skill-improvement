#!/bin/bash
# Install git hooks and exclude rules for the autorefine public repo.
# Run once after cloning: bash autorefine/hooks/install.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_DIR="$REPO_ROOT/.git/hooks"
EXCLUDE="$REPO_ROOT/.git/info/exclude"

# Install pre-commit hook
cp "$SCRIPT_DIR/pre-commit" "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/pre-commit"

# Add exclude rules (like .gitignore but not tracked)
if ! grep -q "autorefine internal artifacts" "$EXCLUDE" 2>/dev/null; then
    cat >> "$EXCLUDE" << 'EOF'

# autorefine internal artifacts — live in dev/ (private submodule)
audits/
principles/
references/
tests/
docs/
handover-*.md
.gitignore
EOF
fi

echo "Installed: pre-commit hook + git exclude rules"
