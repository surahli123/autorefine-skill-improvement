# HANDOVER

Goal: get the staging deploy to pick up the new env var.

Failed approaches: tried setting `API_URL` in the Dockerfile `ENV` — the container still read the old value. Error: `KeyError: 'API_URL'` at boot, because the entrypoint loads `.env` which overrides ENV.

Next: move the var into the `.env` the entrypoint actually reads.
