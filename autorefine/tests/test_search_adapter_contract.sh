#!/bin/bash
# AutoRefine Search Adapter Contract Test Suite
# Locks the minimum viable search gold-set row and search adapter shape.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF_MD="$PROJECT_ROOT/autorefine/references.md"

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

echo "=== Test Suite: AutoRefine Search Adapter Contract ==="
echo ""

if [ ! -f "$REF_MD" ]; then
  echo "FATAL: references.md is missing"
  exit 2
fi

SEARCH_SECTION="$(sed -n '/CONTRACT-ANCHOR:search_adapter:start/,/CONTRACT-ANCHOR:search_adapter:end/p' "$REF_MD")"

echo "--- Test Group 1: minimum viable search row ---"
assert "search contract section exists" \
  "$(grep -q '^### Search adapter reference' "$REF_MD"; echo $?)"
assert "search adapter reference defines stable adapter id" \
  "$(echo "$SEARCH_SECTION" | grep -q '"adapter_id": "search_retrieval_v1"'; echo $?)"
assert "search adapter reference defines default retrieval metrics" \
  "$(echo "$SEARCH_SECTION" | grep -q 'ndcg_at_5' && echo "$SEARCH_SECTION" | grep -q 'recall_at_5'; echo $?)"
for field in query doc_id grade metadata; do
  assert "search gold-set row mentions $field" \
    "$(echo "$SEARCH_SECTION" | grep -q "\"$field\""; echo $?)"
done
echo ""

echo "--- Test Group 2: required search fields ---"
assert "search contract marks query as required" \
  "$(echo "$SEARCH_SECTION" | grep -q '\- `query`'; echo $?)"
assert "search contract marks doc_id as required" \
  "$(echo "$SEARCH_SECTION" | grep -q '\- `doc_id`'; echo $?)"
assert "search contract marks grade as required" \
  "$(echo "$SEARCH_SECTION" | grep -q '\- `grade`'; echo $?)"
assert "search contract states doc_id sequence is the primary oracle" \
  "$(echo "$SEARCH_SECTION" | grep -q 'ordered `doc_id` sequence'; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
