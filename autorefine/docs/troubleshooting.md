# AutoRefine Troubleshooting

## Lost in Phase 7? Render the status ledger.

When a Phase 7 run gets confusing — you cannot tell which experiment is active, what the agent is about to do, or where to look to verify a verdict — run the status-ledger script. It is a manual debugging tool that reads `state.json` plus the most recent run artifacts and writes a one-page snapshot to `[workspace]/phase7-status.md`. Pure stdlib; you invoke it yourself, the agent does not.

Invocation:

```
python3 autorefine/scripts/render-phase7-status.py [workspace_path]
```

Example output (the "You Are Here" block):

```
## You Are Here
- Run: run_2026-05-02T18-00-00 (runs/run_2026-05-02T18-00-00/)
- Experiment: 3 (slot: 3)
- Stage: mutate (status: ready)
- Last mutation: Completed -> advancing to test (runs/.../iteration_003/mutation.md)
- Next action: Analyze and propose next mutation
```

Exit codes (the script prints a single-line reason on any non-zero exit):

- `0` success
- `2` bad workspace (missing path or not a directory)
- `3` malformed `state.json`, `results.json`, or active contract JSON
- `4` cannot write `phase7-status.md` (disk full / read-only)
- `5` path escape (a state-file ref is absolute or resolves outside the workspace)
