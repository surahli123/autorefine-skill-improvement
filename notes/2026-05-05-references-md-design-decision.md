# `references.md` Placement — Design Decision

**Date:** 2026-05-05
**Status:** Tradeoffs presented; awaiting product owner's call.
**Trigger:** Section 1g checklist items #8 + #9 (Phase 1 prompt template + `library_context_manifest` schema) are blocked on a `references.md` decision. Section 1d also expects a "tiny resolution layer" there.

---

## Reframe — what the handover got partially wrong

The 2026-05-05 handover says "`references.md` does not exist in dev/ submodule" and treats this as a blocker. That's literally true but misleading: **`autorefine/references.md` already exists in the parent repo at 6,079 lines** (the canonical v3 contract anchor that the running skill consumes). It's not missing — it's just on the other side of the submodule boundary.

So the real question is **not** "create or inline." It's **where does the v4 contract surface live, and how does it cross the parent ↔ submodule split?**

The dev/ submodule is the design+research+fixtures workspace. The parent owns the runtime skill bundle (`autorefine/SKILL.md` + `autorefine/references.md`). v4 currently lives entirely as design prose in dev/, but the moment v4.0 ships, the contract sections need to land in the parent's `autorefine/references.md` for the running skill to use them.

---

## What's at stake (concrete, not abstract)

Section 1g alone wants to add to `references.md`:

1. **Phase 1 prompt template additions** — the consolidation-pressure dimension's prompt block (~30-50 lines).
2. **`library_context_manifest` schema** — YAML schema defining how the skill library state is captured per-audit (~40-60 lines).
3. **`consolidation_pressure_audit_summary` aggregator field shape** — already specified inline in Section 1g; could be promoted (~20 lines).

Section 1d wants:
4. **Pattern → calibration profile resolution table** — small (~15 lines).

Total Section 1g + 1d: ~100-150 lines if moved.

Across the full v4 design (per the design doc's own Estimated Size Impact at lines 2055-2061):
- v4.0 adds **~200 lines** to references.md
- v4.1 adds **~250 lines**
- v4.2 adds **~140 lines**
- **Total v4 projected `references.md`: ~1,611 lines** of *additions* on top of the existing 6,079 → ~7,690 lines.

This is a non-trivial chunk of contract surface, not a one-off schema.

---

## The four real options

### Option A — Extend the parent's existing `autorefine/references.md`

Land Section 1g's schema additions directly in the parent's canonical contract file when v4.0 ships. Continue to write prose in dev/. References.md is one file in one place — same as v3.

**Pros:**
- Single source of truth. Tests and runtime already point at this path.
- No bifurcation; no risk of "which references.md does this section number belong to?"
- Matches the historical restructure plan ("`autorefine/references.md` remains the compatibility anchor").

**Cons:**
- dev/ commits can't include schema work — every `references.md` edit must happen in a parent PR. Slower iteration during the design phase.
- The v4 design doc in dev/ will keep referencing "see references.md > X" for content that doesn't exist in references.md until v4.0 ships. Forward-references for ~6 months of design work.
- The 6,079-line file gets to ~7,690 lines. Already past the comfortable-to-navigate threshold.

---

### Option B — Create `dev/references.md` as a v4-staging contract anchor

A separate file in dev/ that holds v4-only schema additions during the design phase. At v4.0 ship time, merge contents into the parent's `autorefine/references.md`.

**Pros:**
- dev/ can ship complete contract+prose+fixtures bundles without parent coupling.
- The 2 BLOCKED Section 1g items unblock immediately on this branch.
- Clear staging area; nothing gets prematurely committed to the runtime skill.

**Cons:**
- Two files named `references.md` in two repos with overlapping intent. Easy to confuse.
- Migration step at v4.0 ship: someone has to merge `dev/references.md` into `autorefine/references.md` carefully (section ordering, deduplication, cross-ref updates).
- If migration isn't done atomically with the v4.0 cutover, the runtime skill points at sections that don't exist yet.

---

### Option C — Inline everything in the design doc

Keep all schemas, prompt blocks, and resolution tables inline in `design-autorefine-v4-skill-eval-platform.md`. Drop the "see references.md" forward-references entirely. Promote to references.md only when v4.0 ships.

**Pros:**
- Zero new files. Zero migration. Zero "which references.md."
- Section 1g already inlines `library_context_manifest` schema and the aggregator field shape — this just makes the existing pattern policy.
- During design iteration, having schema next to prose in the same file makes review faster (no jumping between files for context).

**Cons:**
- Design doc is already 2,066 lines. Adding ~590 more lines of schema → ~2,650 lines. Past the "single-file readability" threshold.
- Promote-at-ship-time is still required, just deferred. Same migration risk as Option B but later.
- Section 1d's "tiny resolution layer" was conceptualized as a *runtime* lookup table the agent reads at audit time, not a design-doc artifact. Inlining changes its semantic role.

---

### Option D — Hybrid: prose in design doc, schema in parent's references.md, nothing new in dev/

Section 1g's prose stays in the design doc. Schema additions go directly to the parent's `autorefine/references.md` in a *separate parent commit* (same parent PR that does the submodule pointer bump). Dev/ never gets a `references.md`.

**Pros:**
- Single canonical references.md (parent's). No bifurcation.
- Parent PR for the submodule pointer bump is the natural place to also add the v4.0-portion of references.md content. Bundling both keeps the runtime skill in sync with the design.
- Forward-references in design doc become "see references.md > X" pointing at content that *is* added in the same PR cycle.

**Cons:**
- Couples the design-doc PR cycle to the parent's references.md update cadence. Each new design section that needs schema requires a parent commit, not just a dev/ commit.
- For Section 1g specifically: PR #4 is already open in dev/ without the references.md additions. Either we merge PR #4 as-is and add the references.md content in the parent PR (next-step #2), OR we hold PR #4 until parent's references.md is also ready.
- "Schema lives in parent, prose lives in dev/" is a mental model the team has to maintain. Easy to forget when a non-Section-1g change adds new schema.

---

## Recommendation (and where I'd push back)

**My read: Option D is closest to right, but with one modification.**

For Section 1g specifically, since PR #4 is already open and clean:
1. **Merge PR #4 as-is.** It bundles prose + fixtures + cross-doc consistency. References.md additions weren't in scope anyway.
2. **In the parent PR (next-step #2),** alongside the submodule pointer bump, add the Section 1g schema additions to `autorefine/references.md`:
   - Phase 1 prompt template block for consolidation_pressure
   - `library_context_manifest` schema (lift from the inline version in Section 1g)
   - Already-specified `consolidation_pressure_audit_summary` shape (move from inline → references.md)
3. **For future sections (1d resolution layer, v4.1, v4.2),** apply the same pattern: design prose in dev/, schema in parent's references.md, no `dev/references.md` file ever exists.

**Why not Option A pure?** Because deferring schema-writing until v4.0 ship means ~6 months of forward-references that nobody can verify. Better to write them as we go in the parent.

**Why not Option B?** Two `references.md` files is a cross-repo confusion vector with no offsetting benefit once you accept that schema work has to happen in the parent eventually anyway.

**Why not Option C pure?** A 2,650-line design doc is past the readable threshold, and Section 1d's resolution layer really is a runtime artifact, not a design-doc artifact.

---

## Hard pushback on the recommendation

Three things that could change the call:

1. **If you don't want the parent PR to do double duty.** Parent PR #2 (submodule pointer bump) is currently scoped narrowly. Bundling references.md additions makes it a bigger review surface. If you'd rather keep that PR focused, Option C (inline, defer) becomes more attractive.

2. **If references.md is going to get split into `references/*.md` per the historical restructure plan anyway.** The plan-autorefine-skill-entrypoint-reference-restructure.md document mentions splitting references.md into per-phase files (`gulf1-comprehension.md`, etc.). If that split is imminent, anchoring new schema to the about-to-be-deprecated monolith adds rework.

3. **If the team is one-person-deep on this codebase.** Bifurcation costs scale with team size. Solo-dev with strong context loading can navigate Option B without confusion; the migration step is the only real cost.

---

## Decision points I need from you

1. **Option A, B, C, or D?** (My recommendation: D-modified.)
2. **For PR #4:** merge as-is and do references.md in the parent PR, OR hold PR #4 until references.md content is ready and bundle everything?
3. **Is the historical references.md → references/*.md split imminent or stale?** This changes whether anchoring to references.md is worth the effort.
4. **Should I draft the actual references.md additions in this session** (so you can review concrete content alongside the design call), or is the placement decision enough for now?

---

## Files to consult before deciding

- `dev/docs/design-autorefine-v4-skill-eval-platform.md` lines 462-742 — Section 1g (where schema currently lives inline)
- `dev/docs/design-autorefine-v4-skill-eval-platform.md` line 354 — Section 1d's reference
- `dev/docs/plan-autorefine-skill-entrypoint-reference-restructure.md` — historical split plan, status "Historical completed plan"
- `autorefine/references.md` — the existing 6,079-line canonical contract anchor (parent repo)
