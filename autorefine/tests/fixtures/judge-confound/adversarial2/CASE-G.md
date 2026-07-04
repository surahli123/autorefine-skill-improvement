# HANDOVER
Goal: finish the data migration to the new warehouse.
## Failed approaches (don't repeat)
- Tried a single bulk COPY; it OOM'd the loader at ~20M rows. Error: `MemoryError`.
## Resume instructions
1. Continue the migration in batches.
