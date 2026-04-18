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

## Adapter-aware evaluation

Some skills need a stronger primary oracle than an LLM judge.

Examples:

- search skills need ranking or retrieval metrics
- code-verification skills need tests or static checks
- extraction skills may need exact-match or F1-style evaluation

For these cases, AutoRefine uses:

- a **primary oracle** that decides task quality
- **secondary judges** that diagnose clarity, explanation quality, or boundary behavior
- the same shared trust loop and holdout model

This keeps the system general without pretending one evaluator works for every domain.

## Why this matters

The central claim of AutoRefine is that optimization without eval grounding is cheap but misleading. The pipeline is structured to make the mutation loop downstream of comprehension and judge validation, not a substitute for them.

## Key product principle

The mutation loop should optimize against what actually matters, not what is easiest to game.

In adapter-aware runs, that means:

- primary oracle first
- judge diagnostics second
- holdout trust last
