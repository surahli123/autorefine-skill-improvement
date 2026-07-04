# HANDOVER
Goal: make the staging deploy read the updated environment variable.
Failed approaches: set `API_URL` via the Dockerfile `ENV` directive — but the running container kept the old value, raising `KeyError: 'API_URL'` at startup, because the entrypoint sources `.env`, which overrides ENV.
Next: put the variable in the `.env` file the entrypoint actually loads.
