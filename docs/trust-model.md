# Trust Model

AutoRefine separates fast mutation-time scoring from final trust decisions.

## Mutation-time scoring

During Phase 7, candidate revisions are scored on the approved mutation-time surface. This is how AutoRefine decides whether a revision looks promising enough to keep exploring.

In adapter-aware runs, mutation-time scoring is split into:

- the **primary oracle** for task quality
- **secondary judge diagnostics** for behavioral quality

The primary oracle is the metric that should decide whether the candidate is actually better for the domain. The diagnostics stay visible, but they do not replace the primary oracle.

## Final trust decision

The final promotion surface is the holdout artifact written at Session Close.

The important rule is:

- final trust is not decided by mutation-time scores alone
- final trust is not decided by judge diagnostics alone
- adapter-aware runs still require held-out evidence before promotion

AutoRefine keeps the final trust decision separate so a candidate can look good during iteration but still fail the final trust gate.

## Evaluator separation

AutoRefine keeps the generator and evaluator roles separate.

The mutation actor proposes changes.
The evaluator scores those changes against the explicit run contract.

This matters more in adapter-aware runs, because the system should not let a candidate explain its way into a pass when the domain metric says it failed.

## Human role

Human review remains part of the system:

- in error analysis
- in judge approval
- in experiment confirmation
- in interpreting final results

This is deliberate. AutoRefine is a guided research workflow, not a fire-and-forget optimizer.
