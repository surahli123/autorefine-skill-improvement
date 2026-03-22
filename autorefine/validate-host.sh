#!/bin/bash
# AutoRefine Host Validation
# Tests whether your agent supports Read when: progressive disclosure.
# Run once per agent platform. Result determines v2 line budget strategy.
#
# Usage: bash autorefine/validate-host.sh

set -e

MARKER="AUTOREFINE_RW_PROBE_c4f9e2"
TEST_DIR=$(mktemp -d)
TEST_SKILL="$TEST_DIR/SKILL.md"

# Clean up temp directory on error (normal exit keeps it for user to inspect)
trap 'echo ""; echo "Cleaned up: $TEST_DIR"; rm -rf "$TEST_DIR"' ERR

# --- Create test skill with a Read when: gated section ---
cat > "$TEST_SKILL" << 'SKILL_EOF'
---
name: autorefine-validation-test
description: One-time test for Read when: tag support
---

# Validation Test Skill

## Phase 1: Always Visible

This section loads on every invocation. If you can see this, the skill loaded correctly.

MARKER_VISIBLE_OK

## Phase 3 Details

Read when: Phase 3 active.

This section should only load when Phase 3 is active.

AUTOREFINE_RW_PROBE_c4f9e2

If you can see the line above, your agent loads the entire SKILL.md
regardless of Read when: tags. This is not a bug — it just means
AutoRefine v2 will use references.md for new content instead of
progressive disclosure within SKILL.md.
SKILL_EOF

# --- Print instructions ---
echo "================================================================"
echo "  AutoRefine Host Validation"
echo "================================================================"
echo ""
echo "Test skill created at:"
echo "  $TEST_SKILL"
echo ""
echo "Steps:"
echo "  1. Open your agent (Claude Code, in-house agent, etc.)"
echo "  2. Load the test skill. Examples:"
echo "     - Claude Code: read and follow $TEST_SKILL"
echo "     - In-house agent: point it at $TEST_DIR/"
echo "  3. Tell the agent: 'You are on Phase 1. List every line"
echo "     that starts with MARKER_ or AUTOREFINE_ that you can see.'"
echo "  4. Enter the agent's response below (paste, then press Enter twice):"
echo ""

# --- Collect response ---
RESPONSE=""
while IFS= read -r line; do
    [ -z "$line" ] && break
    RESPONSE="$RESPONSE $line"
done

# --- Evaluate ---
echo ""
echo "================================================================"

HAS_VISIBLE=$(echo "$RESPONSE" | grep -c "MARKER_VISIBLE_OK" || true)
HAS_HIDDEN=$(echo "$RESPONSE" | grep -c "$MARKER" || true)

if [ "$HAS_VISIBLE" -gt 0 ] && [ "$HAS_HIDDEN" -eq 0 ]; then
    echo "  RESULT: PASS"
    echo ""
    echo "  Your agent respects Read when: tags."
    echo "  AutoRefine v2 will use progressive disclosure in SKILL.md."
    echo "  Line budget: ~620 lines."
elif [ "$HAS_VISIBLE" -gt 0 ] && [ "$HAS_HIDDEN" -gt 0 ]; then
    echo "  RESULT: FAIL (not a problem)"
    echo ""
    echo "  Your agent loads the entire SKILL.md regardless of Read when: tags."
    echo "  AutoRefine v2 will put new content in references.md instead."
    echo "  Line budget: ~500 lines for SKILL.md, overflow to references.md."
elif [ "$HAS_VISIBLE" -eq 0 ]; then
    echo "  RESULT: INCONCLUSIVE"
    echo ""
    echo "  Could not detect MARKER_VISIBLE_OK in the response."
    echo "  The agent may not have followed the instruction. Try again,"
    echo "  or manually check: does your agent see the Phase 3 section"
    echo "  when told it is on Phase 1?"
fi

echo ""
echo "================================================================"
echo "  Cleanup: rm -rf \"$TEST_DIR\""
echo "================================================================"
