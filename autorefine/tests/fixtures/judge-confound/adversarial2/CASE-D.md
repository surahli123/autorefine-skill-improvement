# HANDOVER
**Branch:** infra/datastore | **Status:** In Progress
## Goal
Pick and stand up the datastore for the new service.
## Completed
- [x] Wrote the access-pattern doc.
## Key decisions
| decision | rationale |
|---|---|
| Chose Postgres over Mongo | Mongo's lack of real joins would force app-side joins for our relational access. |
| Chose RDS over self-hosted | No ops bandwidth for patching. |
## Current state
- Working: Terraform for the RDS instance drafted (`infra/rds.tf:1`).
## Resume instructions
1. `terraform apply` the RDS module -> instance reachable, connection string in SSM.
