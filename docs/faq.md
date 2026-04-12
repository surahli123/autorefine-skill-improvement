# FAQ

## Is AutoRefine only for Claude Code?

No. It is designed around `SKILL.md` workflows and works best with coding agents that can read files, write files, and run shell commands.

## Does AutoRefine change my original skill immediately?

No. It works on a copied skill inside its workspace and only applies changes back if you approve them.

## Do I need existing evals before I start?

No. Standard AutoRefine exists specifically to help you build the eval surface from observed failures.

## Is the dashboard required?

No. It is useful for inspection, but the core workflow is the skill and the artifacts it writes.

## Can I run multiple sessions at once?

That is not recommended. AutoRefine expects one active session per workspace.
