# Methodology

AutoRefine combines two ideas:

- **Hamel's Three Gulfs**
- **Karpathy-style autoresearch**

## The Three Gulfs

### Gulf 1: Comprehension

You read outputs and identify real failure modes. This is the part that must stay close to human judgment.

### Gulf 2: Specification

You write judges grounded in the observed failures and validate that they are directionally trustworthy.

### Gulf 3: Generalization

Only after the eval surface is credible do you run the mutation loop and compare candidate skill revisions.

## Why this matters

The central claim of AutoRefine is that optimization without eval grounding is cheap but misleading. The pipeline is structured to make the mutation loop downstream of comprehension and judge validation, not a substitute for them.

## Key product principle

The mutation loop should optimize against what actually matters, not what is easiest to game.
