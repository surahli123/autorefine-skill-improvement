# Trust Model

AutoRefine separates fast mutation-time scoring from final trust decisions.

## Mutation-time scoring

During Phase 7, candidate revisions are scored on the approved mutation-time surface. This is how AutoRefine decides whether a revision looks promising enough to keep exploring.

## Final trust decision

The final promotion surface is the holdout artifact written at Session Close.

The important rule is:

- final trust is not decided by mutation-time scores alone

AutoRefine keeps the final trust decision separate so a candidate can look good during iteration but still fail the final trust gate.

## Human role

Human review remains part of the system:

- in error analysis
- in judge approval
- in experiment confirmation
- in interpreting final results

This is deliberate. AutoRefine is a guided research workflow, not a fire-and-forget optimizer.
