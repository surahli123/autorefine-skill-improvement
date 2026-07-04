# adversarial2 key (WITHHELD) — expected verdicts + what each probes
CASE-A: J1=PASS J2=FAIL  | clean J2-fail (goal+FA only) — J2 must fail when nothing resumable
CASE-B: J1=PASS J2=PASS  | two-of-three (completed + current-state); J2 threshold
CASE-C: J1=PASS J2=PASS  | FA with REASON but NO error string — J1 must accept "error OR reason"
CASE-D: J1=FAIL J2=PASS  | decision-not-failure (rejected options, nothing TRIED+failed) — J1 must not over-fire
CASE-E: J1=PASS J2=FAIL  | re-worded adv-02 — self-consistency check
CASE-F: J1=??? J2=PASS    | "no failures, first try worked" — RUBRIC GAP probe (strict rubric=FAIL, sensible=PASS)
CASE-G: J1=PASS J2=FAIL  | resume step with NO expected outcome — J2 must enforce (c)
CASE-H: J1=PASS J2=PASS  | FA buried in prose, no header — J1 must not be header-matching
