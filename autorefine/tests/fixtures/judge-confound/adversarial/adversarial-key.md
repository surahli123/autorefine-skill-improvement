# Adversarial key (WITHHELD from judge) — expected verdicts
adv-01 (shown as CASE-B): J1=FAIL J2=PASS  | long+complete, NO failed-approaches
adv-02 (shown as CASE-A): J1=PASS J2=FAIL  | short, concrete failed-approach WITH error
adv-03 (shown as CASE-D): J1=FAIL J2=PASS  | "Failed approaches" header but vague, no error/reason
adv-04 (shown as CASE-C): J1=PASS J2=FAIL  | long+FA, missing current-state/completed/resume-outcome
A pure length-detector errs on J1 for adv-01/02/03 and J2 for adv-04 (~4/8). A real judge = 8/8.
