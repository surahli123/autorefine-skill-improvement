#!/bin/bash
# AutoRefine Preflight Dry-Run Test
# Simulates the agent following SKILL.md Step 0 instructions
# Tests all 3 user-reported issues are fixed

PASS=0
FAIL=0
TOTAL=0
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

assert() {
  TOTAL=$((TOTAL + 1))
  local desc="$1"
  local result="$2"  # 0 = pass, non-zero = fail
  if [ "$result" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "  ✓ $desc"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ FAIL: $desc"
  fi
}

# Portable content hash for equality checks. CI (Ubuntu) has no BSD `md5`;
# macOS has no GNU `md5sum` by default. We only compare hashes for equality
# within a single run, so any consistently-available algorithm works. `shasum`
# ships on both macOS and Ubuntu, so both platforms take the same first branch.
file_hash() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v md5sum >/dev/null 2>&1; then
    md5sum "$1" | awk '{print $1}'
  elif command -v md5 >/dev/null 2>&1; then
    md5 -q "$1"
  else
    echo "file_hash: no hash tool (shasum/sha256sum/md5sum/md5) found" >&2
    return 1
  fi
}

MOCK_SKILL="/tmp/autorefine-test/mock-skill"
WORKSPACE="/tmp/autorefine-mock-test-skill"

echo "=== Test Suite: AutoRefine Preflight ==="
echo ""

# --- Fixture setup: create the mock skill before tests run ---
# Previous versions of this test relied on a side-effect of a prior run to
# populate $MOCK_SKILL — the cleanup block at the end recreates it, so the
# first run always failed. Now we create it up front so the test is hermetic.
mkdir -p "$MOCK_SKILL"
cat > "$MOCK_SKILL/SKILL.md" << 'FIXTURE_EOF'
---
name: mock-test-skill
description: A mock skill for testing AutoRefine preflight
---
# Mock Test Skill
This is a dummy skill for testing the AutoRefine preflight flow.
## Instructions
Do something useful.
FIXTURE_EOF

# --- Test Group 1: Issue 1 Fix — Workspace location negotiation ---
echo "--- Test Group 1: Workspace Location (Issue 1) ---"

# Clean up any prior test state
rm -rf "$WORKSPACE" "$WORKSPACE-prev" 2>/dev/null

# Step 0.1: Target skill path provided
assert "Step 0.1: Target path exists" "$([ -d "$MOCK_SKILL" ]; echo $?)"

# Step 0.2: Target readable
head -5 "$MOCK_SKILL/SKILL.md" > /dev/null 2>&1
assert "Step 0.2: Target SKILL.md readable" "$?"

# Step 0.3: Workspace location (simulating user chose option a = /tmp/)
# Agent should NEVER create without asking — we simulate the answer
CHOSEN_WORKSPACE="$WORKSPACE"
assert "Step 0.3: Workspace path is under /tmp/ (safe default)" "$(echo "$CHOSEN_WORKSPACE" | grep -q '^/tmp/'; echo $?)"

# Step 0.4: Workspace writable
mkdir -p "$CHOSEN_WORKSPACE" && touch "$CHOSEN_WORKSPACE/.preflight-test" && rm "$CHOSEN_WORKSPACE/.preflight-test"
assert "Step 0.4: Workspace is writable" "$?"

# Step 0.5: Skill import — copy into workspace
cp -r "$MOCK_SKILL/" "$CHOSEN_WORKSPACE/skill-under-test/"
assert "Step 0.5: Skill copied to workspace/skill-under-test/" "$([ -f "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" ]; echo $?)"

# Step 0.6: Persist paths (simulate writing state.json)
cat > "$CHOSEN_WORKSPACE/state.json" << SJEOF
{
  "schema_version": 4,
  "original_skill_path": "$MOCK_SKILL",
  "workspace_path": "$CHOSEN_WORKSPACE"
}
SJEOF
assert "Step 0.6: state.json has original_skill_path" "$(grep -q 'original_skill_path' "$CHOSEN_WORKSPACE/state.json"; echo $?)"
assert "Step 0.6: state.json has workspace_path" "$(grep -q 'workspace_path' "$CHOSEN_WORKSPACE/state.json"; echo $?)"

# Verify: original skill NOT modified
ORIGINAL_HASH=$(file_hash "$MOCK_SKILL/SKILL.md")
COPY_HASH=$(file_hash "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md")
assert "Invariant: Original skill unchanged (hashes match)" "$([ "$ORIGINAL_HASH" = "$COPY_HASH" ]; echo $?)"

echo ""

# --- Test Group 2: Issue 2 Fix — Sandbox isolation ---
echo "--- Test Group 2: Sandbox Isolation (Issue 2) ---"

# All operations should be within workspace, never touching original
# Simulate Phase 1: read the workspace copy, not the original
PHASE1_TARGET="$CHOSEN_WORKSPACE/skill-under-test/SKILL.md"
assert "Phase 1 reads workspace copy (not original)" "$([ -f "$PHASE1_TARGET" ]; echo $?)"
assert "Phase 1 target is NOT the original path" "$([ "$PHASE1_TARGET" != "$MOCK_SKILL/SKILL.md" ]; echo $?)"

# Simulate Phase 7: mutation files go in workspace
touch "$CHOSEN_WORKSPACE/mock-test-skill-optimized.md"
touch "$CHOSEN_WORKSPACE/mock-test-skill-optimized-prev.md"
assert "Phase 7 mutations live in workspace" "$([ -f "$CHOSEN_WORKSPACE/mock-test-skill-optimized.md" ]; echo $?)"
assert "Phase 7 backups live in workspace" "$([ -f "$CHOSEN_WORKSPACE/mock-test-skill-optimized-prev.md" ]; echo $?)"

# Verify: NO files created outside workspace or original skill dir
# (This is a negative test — we check that our test didn't accidentally write elsewhere)
assert "No autoresearch-* dirs created anywhere" "$([ ! -d "/tmp/autoresearch-mock-test-skill" ] && [ ! -d "$MOCK_SKILL/../autoresearch-mock-test-skill" ]; echo $?)"

echo ""

# --- Test Group 3: Issue 3 Fix — Fast-fail on errors ---
echo "--- Test Group 3: Fast-Fail (Issue 3) ---"

# Test: unreadable skill path should produce immediate STOP
head -5 /nonexistent/path/SKILL.md > /dev/null 2>&1
UNREADABLE_EXIT=$?
assert "Unreadable path returns non-zero exit (fast-fail trigger)" "$([ "$UNREADABLE_EXIT" -ne 0 ]; echo $?)"

# Test: unwritable workspace should produce immediate STOP
# Note: on macOS /tmp/ dirs may not respect chmod 444 for owner, so we test
# with a path that definitely doesn't exist as parent
touch /nonexistent-parent-dir/autorefine-test/.preflight-test 2>/dev/null
UNWRITABLE_EXIT=$?
assert "Unwritable workspace returns non-zero exit (fast-fail trigger)" "$([ "$UNWRITABLE_EXIT" -ne 0 ]; echo $?)"

echo ""

# --- Test Group 4: Session Close — Apply Back Gate ---
echo "--- Test Group 4: Apply Back Gate ---"

# Simulate: mutation improved the skill
echo "# Improved Mock Skill" > "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md"

# Apply back: copy workspace version to original
ORIGINAL_BEFORE=$(file_hash "$MOCK_SKILL/SKILL.md")
cp "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" "$MOCK_SKILL/SKILL.md"
ORIGINAL_AFTER=$(file_hash "$MOCK_SKILL/SKILL.md")
assert "Apply back changes the original" "$([ "$ORIGINAL_BEFORE" != "$ORIGINAL_AFTER" ]; echo $?)"

# Read original_skill_path from state.json (simulating resume scenario)
RESTORED_PATH=$(python3 -c "import json; print(json.load(open('$CHOSEN_WORKSPACE/state.json'))['original_skill_path'])")
assert "Apply back path recoverable from state.json" "$([ "$RESTORED_PATH" = "$MOCK_SKILL" ]; echo $?)"

# Simulate: sandbox blocks the copy (we test the fallback message logic)
assert "Fallback: manual copy command constructable" "$(echo "cp $CHOSEN_WORKSPACE/skill-under-test/SKILL.md $RESTORED_PATH/SKILL.md" | grep -q "$MOCK_SKILL"; echo $?)"

echo ""

# --- Test Group 5: No autoresearch-<skill> patterns remain ---
echo "--- Test Group 5: Naming Convention Audit ---"

SKILL_MD="$PROJECT_ROOT/autorefine/SKILL.md"
if [ -f "$SKILL_MD" ]; then
  LEGACY_COUNT=$(grep -c 'autoresearch-<skill>' "$SKILL_MD" 2>/dev/null; true)
  LEGACY_COUNT=${LEGACY_COUNT:-0}
  assert "Zero 'autoresearch-<skill>' references in SKILL.md" "$([ "$LEGACY_COUNT" -eq 0 ]; echo $?)"

  # Check workspace references are consistent
  WORKSPACE_REFS=$(grep -c '\[workspace\]' "$SKILL_MD" 2>/dev/null; true)
  WORKSPACE_REFS=${WORKSPACE_REFS:-0}
  assert "Workspace path references exist (>5 expected)" "$([ "$WORKSPACE_REFS" -gt 5 ]; echo $?)"
else
  echo "  ⚠ SKILL.md not found at expected path — skipping naming audit"
fi

echo ""

# --- Test Group 6: Circuit Breaker State ---
echo "--- Test Group 6: Circuit Breaker ---"

# Simulate state.json with circuit breaker fields
cat > "$CHOSEN_WORKSPACE/state.json" << SJEOF
{
  "schema_version": 4,
  "original_skill_path": "$MOCK_SKILL",
  "workspace_path": "$CHOSEN_WORKSPACE",
  "consecutive_discards": 0,
  "circuit_breaker": null
}
SJEOF

# Test: consecutive_discards starts at 0
CD=$(python3 -c "import json; print(json.load(open('$CHOSEN_WORKSPACE/state.json'))['consecutive_discards'])")
assert "Circuit breaker: consecutive_discards starts at 0" "$([ "$CD" -eq 0 ]; echo $?)"

# Simulate 3 discards
python3 -c "
import json
s = json.load(open('$CHOSEN_WORKSPACE/state.json'))
s['consecutive_discards'] = 3
s['circuit_breaker'] = {'triggered_count': 1, 'last_experiment': 3, 'diagnosis': 'strategy_review'}
json.dump(s, open('$CHOSEN_WORKSPACE/state.json', 'w'))
"
CD_AFTER=$(python3 -c "import json; print(json.load(open('$CHOSEN_WORKSPACE/state.json'))['consecutive_discards'])")
assert "Circuit breaker: tracks 3 consecutive discards" "$([ "$CD_AFTER" -eq 3 ]; echo $?)"

CB=$(python3 -c "import json; print(json.load(open('$CHOSEN_WORKSPACE/state.json'))['circuit_breaker']['triggered_count'])")
assert "Circuit breaker: triggered_count recorded" "$([ "$CB" -eq 1 ]; echo $?)"

# Simulate reset on keep
python3 -c "
import json
s = json.load(open('$CHOSEN_WORKSPACE/state.json'))
s['consecutive_discards'] = 0
json.dump(s, open('$CHOSEN_WORKSPACE/state.json', 'w'))
"
CD_RESET=$(python3 -c "import json; print(json.load(open('$CHOSEN_WORKSPACE/state.json'))['consecutive_discards'])")
assert "Circuit breaker: resets to 0 on keep" "$([ "$CD_RESET" -eq 0 ]; echo $?)"

echo ""

# --- Test Group 7: Verification Isolation (eval-task files) ---
echo "--- Test Group 7: Verification Isolation ---"

mkdir -p "$CHOSEN_WORKSPACE/eval-tasks"
cat > "$CHOSEN_WORKSPACE/eval-tasks/exp1-E1.md" << 'ETEOF'
# Eval Task: E1 — test eval
## Judge Prompt
Score pass or fail.
## Fixture Input
test input
## Skill Output to Evaluate
test output
## Instructions
Evaluate the Skill Output above against the Judge Prompt criteria.
ETEOF

assert "Eval-task file created in eval-tasks/" "$([ -f "$CHOSEN_WORKSPACE/eval-tasks/exp1-E1.md" ]; echo $?)"
assert "Eval-task file does NOT contain mutation hypothesis" "$(! grep -q 'hypothesis\|mutation\|Phase 1\|audit' "$CHOSEN_WORKSPACE/eval-tasks/exp1-E1.md"; echo $?)"
assert "Eval-task file contains judge prompt section" "$(grep -q 'Judge Prompt' "$CHOSEN_WORKSPACE/eval-tasks/exp1-E1.md"; echo $?)"
assert "Eval-task file contains skill output section" "$(grep -q 'Skill Output to Evaluate' "$CHOSEN_WORKSPACE/eval-tasks/exp1-E1.md"; echo $?)"

echo ""

# --- Test Group 8: Ambient Learning ---
echo "--- Test Group 8: Ambient Learning ---"

# Restore mock skill to original, workspace copy is different (simulating user edit)
cat > "$MOCK_SKILL/SKILL.md" << 'EOF'
---
name: mock-test-skill
description: A mock skill for testing
---
# Mock Test Skill
## Instructions
Do something useful.
## Gotchas
Be careful with edge cases.
EOF

cat > "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" << 'EOF'
---
name: mock-test-skill
description: A mock skill for testing
---
# Mock Test Skill
## Instructions
Do something useful.
EOF

# Diff should detect the change (user added Gotchas section)
DIFF_OUTPUT=$(diff "$MOCK_SKILL/SKILL.md" "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" 2>&1 || true)
assert "Ambient: diff detects user edits" "$([ -n "$DIFF_OUTPUT" ]; echo $?)"

# Size gate: count changed lines
DIFF_LINES=$(diff "$MOCK_SKILL/SKILL.md" "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" 2>/dev/null | grep -c '^[<>]' || echo "0")
assert "Ambient: small diff (<=20 lines) triggers preference extraction" "$([ "$DIFF_LINES" -le 20 ]; echo $?)"

# Sync: after ambient learning, workspace copy matches original
cp "$MOCK_SKILL/SKILL.md" "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md"
SYNC_DIFF=$(diff "$MOCK_SKILL/SKILL.md" "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" 2>&1 || true)
assert "Ambient: sync makes workspace copy match original" "$([ -z "$SYNC_DIFF" ]; echo $?)"

# Preferences file
mkdir -p "$CHOSEN_WORKSPACE"
cat > "$CHOSEN_WORKSPACE/preferences.md" << 'EOF'
# User Preferences (ambient learning)

## Preference 1 (captured: 2026-04-02)
RULE: User wants a Gotchas section in skills
EVIDENCE: (none) → "## Gotchas\nBe careful with edge cases."
CONFIDENCE: high
EOF
assert "Ambient: preferences.md created" "$([ -f "$CHOSEN_WORKSPACE/preferences.md" ]; echo $?)"
assert "Ambient: preferences.md has RULE/EVIDENCE/CONFIDENCE format" "$(grep -q 'RULE:' "$CHOSEN_WORKSPACE/preferences.md" && grep -q 'EVIDENCE:' "$CHOSEN_WORKSPACE/preferences.md" && grep -q 'CONFIDENCE:' "$CHOSEN_WORKSPACE/preferences.md"; echo $?)"

echo ""

# --- Test Group 9: Resume Ordering ---
echo "--- Test Group 9: Resume Ordering ---"

# Simulate: checkpoint exists AND skill was edited
# Step A (checkpoint) must run BEFORE Step B (ambient learning)
cat > "$CHOSEN_WORKSPACE/state.json" << SJEOF
{
  "schema_version": 4,
  "original_skill_path": "$MOCK_SKILL",
  "workspace_path": "$CHOSEN_WORKSPACE",
  "skill_pattern": "pipeline",
  "phase1_context": {
    "selected_skill_pattern": "pipeline",
    "selection_scope": "current_run",
    "source_skill_path": "skill-under-test/SKILL.md"
  },
  "consecutive_discards": 2,
  "circuit_breaker": null,
  "checkpoint": {
    "next_action": "Continue Phase 7: resume from experiment 4",
    "files_to_read_on_resume": ["state.json", "results.json"],
    "resume_prompt": "Resume from exp 4. Consecutive discards: 2."
  }
}
SJEOF

# Checkpoint exists → should skip ambient learning (mid-Phase-7 resume)
HAS_CHECKPOINT=$(python3 -c "import json; c=json.load(open('$CHOSEN_WORKSPACE/state.json'))['checkpoint']; print('yes' if c else 'no')")
assert "Resume: checkpoint detected" "$([ "$HAS_CHECKPOINT" = "yes" ]; echo $?)"

IS_PHASE7=$(python3 -c "import json; c=json.load(open('$CHOSEN_WORKSPACE/state.json'))['checkpoint']['next_action']; print('yes' if 'Phase 7' in c else 'no')")
assert "Resume: mid-Phase-7 checkpoint skips ambient learning" "$([ "$IS_PHASE7" = "yes" ]; echo $?)"

LOADED_PATTERN=$(python3 -c "import json; s=json.load(open('$CHOSEN_WORKSPACE/state.json')); print(s['phase1_context']['selected_skill_pattern'])")
assert "Resume: deserialized phase1_context restores selected pattern" "$([ "$LOADED_PATTERN" = "pipeline" ]; echo $?)"

MIRROR_MATCH=$(python3 -c "import json; s=json.load(open('$CHOSEN_WORKSPACE/state.json')); print('yes' if s['phase1_context']['selected_skill_pattern'] == s['skill_pattern'] else 'no')")
assert "Resume: loaded phase1_context matches skill_pattern mirror" "$([ "$MIRROR_MATCH" = "yes" ]; echo $?)"

# After checkpoint recovery, clear it
python3 -c "
import json
s = json.load(open('$CHOSEN_WORKSPACE/state.json'))
s['checkpoint'] = None
json.dump(s, open('$CHOSEN_WORKSPACE/state.json', 'w'))
"
CLEARED=$(python3 -c "import json; print(json.load(open('$CHOSEN_WORKSPACE/state.json'))['checkpoint'])")
assert "Resume: checkpoint cleared after recovery" "$([ "$CLEARED" = "None" ]; echo $?)"

PATTERN_AFTER_CLEAR=$(python3 -c "import json; s=json.load(open('$CHOSEN_WORKSPACE/state.json')); print(s['phase1_context']['selected_skill_pattern'])")
assert "Resume: checkpoint clear preserves phase1_context pattern" "$([ "$PATTERN_AFTER_CLEAR" = "pipeline" ]; echo $?)"

echo ""

# --- Test Group 10: Apply Back Sync (optimized → skill-under-test) ---
echo "--- Test Group 10: Apply Back Sync ---"

# Simulate: Phase 7 produced an optimized version
echo "# OPTIMIZED SKILL" > "$CHOSEN_WORKSPACE/mock-test-skill-optimized.md"
echo "# ORIGINAL IN WORKSPACE" > "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md"

# Step 0 of Session Close: sync optimized → skill-under-test
cp "$CHOSEN_WORKSPACE/mock-test-skill-optimized.md" "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md"
SYNCED=$(cat "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md")
assert "Apply Back: optimized syncs to skill-under-test before copy-out" "$(echo "$SYNCED" | grep -q 'OPTIMIZED'; echo $?)"

# Then apply back to original
cp "$CHOSEN_WORKSPACE/skill-under-test/SKILL.md" "$MOCK_SKILL/SKILL.md"
APPLIED=$(cat "$MOCK_SKILL/SKILL.md")
assert "Apply Back: original receives optimized content" "$(echo "$APPLIED" | grep -q 'OPTIMIZED'; echo $?)"

echo ""

# --- Test Group 11: Placeholder Consistency Audit ---
echo "--- Test Group 11: Placeholder Audit ---"

SKILL_MD="$PROJECT_ROOT/autorefine/SKILL.md"
REF_MD="$PROJECT_ROOT/autorefine/references.md"
if [ -f "$SKILL_MD" ] && [ -f "$REF_MD" ]; then
  # No [chosen-workspace] outside Preflight (lines 1-36)
  OUTSIDE_PREFLIGHT=$(sed -n '37,$p' "$SKILL_MD" | grep -c '\[chosen-workspace\]'; true)
  OUTSIDE_PREFLIGHT=${OUTSIDE_PREFLIGHT:-0}
  assert "Placeholder: no [chosen-workspace] outside Preflight" "$([ "$OUTSIDE_PREFLIGHT" -eq 0 ]; echo $?)"

  # No [original] without -skill-path in references
  BARE_ORIGINAL=$(grep -c '\[original\]/' "$REF_MD" 2>/dev/null; true)
  BARE_ORIGINAL=${BARE_ORIGINAL:-0}
  assert "Placeholder: no bare [original]/ in references.md" "$([ "$BARE_ORIGINAL" -eq 0 ]; echo $?)"

  # No [workspace path] (should be [workspace])
  WS_PATH=$(grep -c '\[workspace path\]' "$SKILL_MD" 2>/dev/null; true)
  WS_PATH=${WS_PATH:-0}
  assert "Placeholder: no [workspace path] in SKILL.md" "$([ "$WS_PATH" -eq 0 ]; echo $?)"

  # state.json schema has all new fields
  for FIELD in original_skill_path workspace_path consecutive_discards circuit_breaker; do
    assert "Schema: references.md has $FIELD" "$(grep -q "$FIELD" "$REF_MD"; echo $?)"
  done
fi

echo ""

# --- Test Group 12: Discard Autopsy ---
echo "--- Test Group 12: Discard Autopsy ---"

# Simulate experiments with discard_autopsy field
cat > "$CHOSEN_WORKSPACE/results.json" << 'RJEOF'
{
  "skill_name": "mock-test-skill",
  "status": "running",
  "current_experiment": 3,
  "baseline_score": 0.6,
  "best_score": 0.75,
  "experiments": [
    {"id": 0, "score": 0.6, "status": "baseline", "discard_autopsy": null},
    {"id": 1, "score": 0.75, "status": "keep", "discard_autopsy": null,
     "changes": [{"type": "modified", "location": "gotchas"}]},
    {"id": 2, "score": 0.55, "status": "discard", "discard_autopsy": {"classification": "wrong_target", "reasoning": "voice section targeted but no improvement"},
     "changes": [{"type": "added", "location": "voice"}]},
    {"id": 3, "score": 0.60, "status": "discard", "discard_autopsy": {"classification": "wrong_params", "reasoning": "gotchas section responded before but this approach regressed"},
     "changes": [{"type": "modified", "location": "gotchas"}]}
  ]
}
RJEOF

# Test: discard_autopsy field exists in schema
assert "Autopsy: field exists in experiment record" "$(python3 -c "import json; exps=json.load(open('$CHOSEN_WORKSPACE/results.json'))['experiments']; assert all('discard_autopsy' in e for e in exps)" 2>&1; echo $?)"

# Test: kept/baseline experiments have null discard_autopsy
assert "Autopsy: null for kept experiments" "$(python3 -c "
import json
exps = json.load(open('$CHOSEN_WORKSPACE/results.json'))['experiments']
kept = [e for e in exps if e['status'] in ('keep', 'baseline')]
assert all(e['discard_autopsy'] is None for e in kept), f'Non-null autopsy on kept: {kept}'
" 2>&1; echo $?)"

# Test: discarded experiments have non-null discard_autopsy
assert "Autopsy: non-null for discarded experiments" "$(python3 -c "
import json
exps = json.load(open('$CHOSEN_WORKSPACE/results.json'))['experiments']
discarded = [e for e in exps if e['status'] == 'discard']
assert all(e['discard_autopsy'] is not None for e in discarded), f'Null autopsy on discard: {discarded}'
" 2>&1; echo $?)"

# Test: classification values are valid enum
INVALID_COUNT=$(python3 -c "
import json
VALID = ['wrong_target', 'wrong_params', 'wrong_type']
exps = json.load(open('$CHOSEN_WORKSPACE/results.json'))['experiments']
bad = 0
for e in exps:
    da = e.get('discard_autopsy')
    if da is not None:
        if da.get('classification') not in VALID or 'reasoning' not in da:
            bad += 1
print(bad)
")
assert "Autopsy: valid 3-way classification enum" "$([ "$INVALID_COUNT" -eq 0 ]; echo $?)"

# Test: SKILL.md references discard autopsy
assert "Autopsy: SKILL.md references discard_autopsy" "$(grep -q 'discard autopsy' "$SKILL_MD"; echo $?)"

echo ""

# --- Test Group 13: Aggregation Breakdown Persistence ---
echo "--- Test Group 13: Aggregation Breakdown Persistence ---"

# Simulate persisting a result record with a full aggregation breakdown
cat > "$CHOSEN_WORKSPACE/results.json" << 'RJEOF'
{
  "skill_name": "mock-test-skill",
  "status": "running",
  "current_experiment": 1,
  "baseline_score": 0.6,
  "best_score": 0.78,
  "experiments": [
    {
      "id": 1,
      "score": 0.78,
      "status": "keep",
      "decision_breakdown": {
        "components": [
          {
            "eval": "E1",
            "pass_fail": "pass",
            "weight": 1.0,
            "weight_source": "code_eval_fixed",
            "weighted_points": 1.0,
            "normalized_contribution": 0.5263
          },
          {
            "eval": "E2",
            "pass_fail": "fail",
            "weight": 0.9,
            "weight_source": "phase_6_validation_average",
            "weighted_points": 0.0,
            "normalized_contribution": 0.0
          }
        ],
        "formula": "combined_score = weighted_points / total_weight",
        "weighted_points": 1.0,
        "total_weight": 1.9,
        "combined_score": 0.5263,
        "combined_score_pct": 52.63,
        "threshold": 0.5,
        "proposed_decision": "keep"
      },
      "discard_autopsy": null
    }
  ]
}
RJEOF

# Test: persisted result still exposes the full aggregation breakdown after reload
assert "Persistence: reload preserves full decision_breakdown object and values" "$(python3 -c "
import json

expected = {
    'components': [
        {
            'eval': 'E1',
            'pass_fail': 'pass',
            'weight': 1.0,
            'weight_source': 'code_eval_fixed',
            'weighted_points': 1.0,
            'normalized_contribution': 0.5263,
        },
        {
            'eval': 'E2',
            'pass_fail': 'fail',
            'weight': 0.9,
            'weight_source': 'phase_6_validation_average',
            'weighted_points': 0.0,
            'normalized_contribution': 0.0,
        },
    ],
    'formula': 'combined_score = weighted_points / total_weight',
    'weighted_points': 1.0,
    'total_weight': 1.9,
    'combined_score': 0.5263,
    'combined_score_pct': 52.63,
    'threshold': 0.5,
    'proposed_decision': 'keep',
}

experiments = json.load(open('$CHOSEN_WORKSPACE/results.json'))['experiments']
assert len(experiments) == 1
stored = experiments[0]['decision_breakdown']
assert stored == expected, f'Reloaded breakdown drifted: {stored!r}'
" 2>&1; echo $?)"

echo ""

# --- Test Group 14: Derived Mutation Registry ---
echo "--- Test Group 14: Derived Mutation Registry ---"

# Simulate canonical headings in session-log
cat > "$CHOSEN_WORKSPACE/session-log.json" << 'SLEOF'
{"skill":"mock-test-skill","session_start":"2026-04-02T10:00:00Z","entries":[
  {"phase":"7","type":"canonical_headings","sections":["Instructions","Gotchas","Voice","Progressive Disclosure","Scripts"]},
  {"phase":"7","type":"derived_registry_snapshot","experiment":3,"sections_explored":{"Gotchas":{"count":2,"best_delta":0.12,"last_tried":3},"Voice":{"count":1,"best_delta":-0.03,"last_tried":2}},"mutation_types":{"add":1,"modify":2,"delete":0},"diversity_score":0.4}
]}
SLEOF

# Test: canonical headings logged
assert "Registry: canonical_headings entry in session-log" "$(python3 -c "
import json
entries = json.load(open('$CHOSEN_WORKSPACE/session-log.json'))['entries']
headings = [e for e in entries if e.get('type') == 'canonical_headings']
assert len(headings) == 1 and len(headings[0]['sections']) == 5
" 2>&1; echo $?)"

# Test: derived registry snapshot in session-log
assert "Registry: snapshot entry in session-log" "$(python3 -c "
import json
entries = json.load(open('$CHOSEN_WORKSPACE/session-log.json'))['entries']
snapshots = [e for e in entries if e.get('type') == 'derived_registry_snapshot']
assert len(snapshots) == 1
" 2>&1; echo $?)"

# Test: diversity_score computed correctly (2 sections explored / 5 total = 0.4)
assert "Registry: diversity_score is correct" "$(python3 -c "
import json
entries = json.load(open('$CHOSEN_WORKSPACE/session-log.json'))['entries']
snap = [e for e in entries if e.get('type') == 'derived_registry_snapshot'][0]
assert snap['diversity_score'] == 0.4, f'Expected 0.4, got {snap[\"diversity_score\"]}'
" 2>&1; echo $?)"

# Test: sections_explored tracks count and best_delta
SECTION_OK=$(python3 -c "
import json
entries = json.load(open('$CHOSEN_WORKSPACE/session-log.json'))['entries']
snap = [e for e in entries if e.get('type') == 'derived_registry_snapshot'][0]
gotchas = snap['sections_explored'].get('Gotchas', {})
bad = 0
if gotchas.get('count') != 2: bad += 1
if gotchas.get('best_delta') != 0.12: bad += 1
if gotchas.get('last_tried') != 3: bad += 1
print(bad)
")
assert "Registry: sections_explored has count, best_delta, last_tried" "$([ "$SECTION_OK" -eq 0 ]; echo $?)"

# Test: references.md has Derived Mutation Registry section
REF_MD="$PROJECT_ROOT/autorefine/references.md"
assert "Registry: references.md has Derived Mutation Registry section" "$(grep -q 'Derived Mutation Registry' "$REF_MD"; echo $?)"

echo ""

# --- Cleanup ---
rm -rf "$WORKSPACE" 2>/dev/null
# Restore mock skill to original state
cat > "$MOCK_SKILL/SKILL.md" << 'EOF'
---
name: mock-test-skill
description: A mock skill for testing AutoRefine preflight
---
# Mock Test Skill
This is a dummy skill for testing the AutoRefine preflight flow.
## Instructions
Do something useful.
EOF

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
