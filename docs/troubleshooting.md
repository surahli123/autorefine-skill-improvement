# Troubleshooting

## AutoRefine cannot read my skill

Make sure the target directory contains `SKILL.md` and that the path you passed is readable by the agent runtime.

## AutoRefine cannot write the workspace

Use a writable path such as `/tmp/...` or another user-writable working directory.

## The dashboard does not render correctly

If your environment blocks CDN assets, the dashboard may need a local Chart.js copy or a friendlier local serving setup.

## A run looks overfit

That usually means the eval surface is not strong enough yet. Revisit the failure taxonomy and judge quality before trusting the mutation results.

## The workflow feels too heavy

Use the lighter entrypoint only if your workspace already has enough validated structure. Otherwise the heavier path is the point: it is protecting you from optimizing noise.
