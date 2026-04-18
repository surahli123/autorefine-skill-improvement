#!/bin/bash
# AutoRefine Code Adapter Contract Test Suite
# Locks the second concrete adapter reference and its primary-oracle semantics.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF_MD="$PROJECT_ROOT/autorefine/references.md"
GULF2="$PROJECT_ROOT/autorefine/references/gulf2-specification.md"
GULF3="$PROJECT_ROOT/autorefine/references/gulf3-generalization.md"

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

echo "=== Test Suite: AutoRefine Code Adapter Contract ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$GULF2" ] || [ ! -f "$GULF3" ]; then
  echo "FATAL: required prompt files are missing"
  exit 2
fi

CODE_SECTION="$(sed -n '/^### Code adapter reference/,/^### Minimum viable search gold-set row/p' "$REF_MD")"

echo "--- Test Group 1: reference adapter ---"
assert "code adapter reference exists" \
  "$(grep -q '^### Code adapter reference' "$REF_MD"; echo $?)"
assert "code adapter uses stable adapter id" \
  "$(echo "$CODE_SECTION" | grep -q '"adapter_id": "code_verification_v1"'; echo $?)"
assert "code adapter reference includes tests_pass and static_checks_pass" \
  "$(echo "$CODE_SECTION" | grep -q 'tests_pass' && echo "$CODE_SECTION" | grep -q 'static_checks_pass'; echo $?)"
echo ""

echo "--- Test Group 2: Gulf 2 semantics ---"
assert "Gulf 2 defines code_verification_v1 specialization" \
  "$(grep -q 'For `code_verification_v1`' "$GULF2"; echo $?)"
assert "Gulf 2 states code primary oracle is executable verification" \
  "$(grep -q 'primary oracle = executable verification' "$GULF2"; echo $?)"
echo ""

echo "--- Test Group 3: Gulf 3 semantics ---"
assert "Gulf 3 defines code_verification_v1 experiment contract" \
  "$(grep -q 'For `code_verification_v1`, the experiment contract must name' "$GULF3"; echo $?)"
assert "Gulf 3 prevents explanation quality from overriding failed code verification" \
  "$(grep -q 'failing test/static-check result cannot be overridden into keep by explanation quality alone' "$GULF3"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
