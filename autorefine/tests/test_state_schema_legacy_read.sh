#!/bin/bash
# AutoRefine legacy state schema read contract.
# Verifies the public status renderer can read legacy v2/v3-era state.json
# snapshots without crashing.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RENDER="$PROJECT_ROOT/autorefine/scripts/render-phase7-status.py"
WORKSPACE="$(mktemp -d /tmp/autorefine-legacy-state.XXXXXX)"
trap 'rm -rf "$WORKSPACE"' EXIT

assert() {
  TOTAL=$((TOTAL + 1))
  local desc="$1"
  local result="$2"
  if [ "$result" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "  ✓ $desc"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ FAIL: $desc"
  fi
}

echo "=== Test Suite: AutoRefine Legacy State Schema Read ==="
echo ""

if [ ! -f "$RENDER" ]; then
  echo "FATAL: render-phase7-status.py is missing"
  exit 2
fi

cat > "$WORKSPACE/state.json" << 'JSON'
{
  "schema_version": 2,
  "skill_name": "legacy-schema-skill",
  "current_phase": 7,
  "current_gulf": 3
}
JSON

python3 "$RENDER" "$WORKSPACE" > "$WORKSPACE/render.stdout" 2> "$WORKSPACE/render.stderr"
RC=$?

echo "--- Renderer output ---"
cat "$WORKSPACE/render.stdout"
cat "$WORKSPACE/render.stderr"
echo ""

assert "render-phase7-status.py accepts a legacy schema_version 2 state.json" \
  "$([ "$RC" -eq 0 ]; echo $?)"
assert "renderer writes phase7-status.md" \
  "$([ -f "$WORKSPACE/phase7-status.md" ]; echo $?)"
assert "rendered status names the legacy skill" \
  "$(grep -q '# Phase 7 Status - legacy-schema-skill' "$WORKSPACE/phase7-status.md"; echo $?)"
assert "rendered status identifies truncated/legacy state instead of crashing" \
  "$(grep -q 'truncated/legacy' "$WORKSPACE/phase7-status.md"; echo $?)"

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
