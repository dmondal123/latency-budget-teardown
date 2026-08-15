---
name: selecting-models

description: Use when choosing, comparing, or routing between LLMs for a workload. Covers the decision ladder, binary vetoes vs scores, per-turn model routing, and the 4-slot model variant identity. Rigid gating.
---

# Selecting Models

## Purpose

Pick models by workflow evidence and hard constraints, not leaderboard scores. Produce a routing policy, not a single winner.

## When to use

Choosing a model, comparing candidates, or deciding per-turn routing. Feeds the per-turn model choice in [[reducing-llm-latency]] and depth choices in [[rlm-based-rag]].

## Decision ladder

1. Write the contract: tasks, tools, SLAs, and data constraints.
2. Gate impossible options with binary vetoes: privacy, region, license, capacity, and tool protocol.
3. Measure the workflow on real traffic, not synthetic benchmarks.
4. Normalize evidence to declared thresholds on a common scale.
5. Expose weights explicitly and test ±5% sensitivity.
6. Route requests, not one winner: pools by risk, privacy, difficulty, and deadline.

## Latency-relevant rules

A reasoning-tuned model at max effort is a hard veto if the latency budget is tight.

- Coding-tuned and tool-tuned checkpoints often beat general benchmark winners for agentic work.
- Route cheap, fast models to routing and summarization turns, and the strongest model to repair or patch.
- Measure accuracy at context depth from real corpus samples; advertised window attention is not enough.

## Model variant identity

Specify all four slots:

checkpoint
reasoning_mode
chat_template
tool_protocol

## References

`references/decision-ladder.md` — instrument table, veto examples, variant identity detail

## Related skills

[[reducing-llm-latency]] [[evaluating-llm-systems]] [[rlm-based-rag]]
