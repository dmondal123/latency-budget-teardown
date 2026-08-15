# Collaboration Notes

This file records how the human and AI worked together, especially decisions, corrections, rejected assumptions, approval gates, and changes in direction. It is not a transcript. Keep entries short, factual, and linked to repository evidence.

Update this file after significant agent decisions or corrections and before each commit. The final submission must include at least two cases where the agent was wrong or suboptimal and explain how the issue was caught and corrected.

## Working agreement

| Topic | Agreement |
|---|---|
| Requirements | `PROBLEM_STATEMENT.md` is authoritative |
| Implementation plan | `RAG_PIPELINE_PLAN.md` is approved as of 2026-08-16 |
| Human approval | Required at the measurement-contract, baseline-integrity, intervention-decision, and final-delivery gates |
| Metrics | Only reproducible script output may appear as measured evidence |
| Experiments | Register before execution and log immediately in `EXPERIMENT_LOG.md` |
| Progress | Update `PROGRESS.md` after meaningful milestones or blockers |
| Corrections | Preserve the original issue, how it was found, and the resulting preventive rule |

## Decision and correction index

| ID | Date | Type | Summary | Evidence |
|---|---|---|---|---|
| C001 | 2026-08-16 | Human approval | Approved the structure-first RAG pipeline plan | `RAG_PIPELINE_PLAN.md` |
| C002 | 2026-08-16 | Agent correction | Replaced ambiguous cache testing with separate application-cache and engine-prefix-cache policies | `RAG_PIPELINE_PLAN.md` sections 3, 8, and 9 |
| C003 | 2026-08-16 | Agent correction | Changed multimodal prefix caching from an assumption to a correctness-gated policy | `RAG_PIPELINE_PLAN.md` section 8 |
| C004 | 2026-08-16 | Agent correction | Stopped a failed discovery command from suppressing later checks by running checks independently | Collaboration session evidence |

## Detailed entries

### C001: Structure-first plan approval

Context: The human asked for the pipeline stages, baseline metrics, p50/p95 waterfall, quality gates, two isolated interventions, and budget methodology to be established before implementation. The human also asked for vLLM-Metal-specific latency exploration.

Agent contribution: Reviewed the existing plan using the evaluation and latency skills, checked current vLLM-Metal primary sources, and proposed a structure-first rewrite.

Human decision: Explicitly approved the structure-first rewrite and then approved the refined plan.

Result: `RAG_PIPELINE_PLAN.md` is the implementation authority. It remains subject to the approval gates inside the plan.

### C002: Cache experiment ambiguity

What was suboptimal: The earlier plan used a generic cache off/on condition and placed a unique nonce at the start of every prompt. That design mixed application caching with vLLM prefix caching and would have removed representative shared-prefix reuse.

How it was caught: The agent compared the plan with current vLLM-Metal defaults and upstream vLLM prefix-cache behavior during the source-backed review.

Correction: The plan now separates application caches from engine KV-prefix caching. The nonce begins only at the dynamic user/evidence portion, leaving the stable system contract eligible for realistic reuse. Cache-hit tokens must be measured.

Preventive rule: Name every cache layer, record its state independently, and never use a benchmark anti-cache mechanism without stating which reuse it invalidates.

### C003: Experimental multimodal prefix-cache assumption

What was wrong: The first rewrite treated automatic prefix caching as safe for every primary Qwen3-VL condition. Upstream vLLM supports multimodal cache hashing, but the vLLM-Metal Qwen3-VL path is experimental, so upstream capability alone did not prove Metal-path correctness.

How it was caught: A post-edit source audit distinguished upstream cache design from the selected experimental hardware plugin path.

Correction: Prefix caching now requires same-text/different-image, repeated-image, concurrency-2, and cache-disabled parity probes. The resulting policy is frozen across product interventions. A failed gate keeps prefix caching disabled and preserves the incompatibility as evidence.

Preventive rule: Do not infer plugin support from upstream framework support. Require a target-backend correctness probe before performance testing.

### C004: Discovery command sequencing

What was suboptimal: A repository-discovery command chained `git log` with later read-only checks. Because the new repository had no commits, `git log` exited nonzero and prevented the remaining checks from running.

How it was caught: The command output ended at the empty-history error and lacked the expected status and search results.

Correction: Later discovery and validation checks were run independently, so an expected absence in one source could not suppress unrelated evidence.

Preventive rule: Run independent discovery checks independently. Treat an empty Git history as valid repository state.

## Entry template

```markdown
### CXXX: Short decision or correction title

Date:
Participants:
Type: Human direction | Human approval | Agent proposal | Agent correction | Rejected approach

Context:

Human direction or decision:

Agent contribution:

What was wrong or uncertain:

How it was caught:

Correction or final decision:

Evidence:

Preventive rule or learning:

Follow-up:
```
