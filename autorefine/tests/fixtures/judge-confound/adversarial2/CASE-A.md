# HANDOVER
Goal: migrate the user table to the new schema.
Failed approaches: tried an in-place `ALTER`; it locked the table too long on the 40M-row prod copy (cancelled after 90s).
