# Four Clocks, Cost Denominators, Instrumentation, and Failure Signatures

All figures are illustrative. Calibrate against your own traces before adopting them as SLOs.

## The four clocks

Emit and record all four as separate telemetry events:

| Clock | Name | Target | Owned by |
| --- | --- | --- | --- |
| TTFE | Time to first event | ≤ 0.3 s | Admission / queueing gateway |
| TTFT | Time to first token | ≤ 1.2 s | Context size, provider queueing, prefill |
| TTA | Time to first action | ≤ 4.0 s | Loop design and first real tool call |
| TTC | Time to validated completion | ≤ 45 s | Full end-to-end with required gates |

Parallel branches compose as max(A, B), not A + B. Do not sum p95s.

## Instrumentation

Attach span dimensions at span creation, not in a post-processing job. Track workload class, model region, warm/cold state, repo size bucket, tool name, sandbox mode, approval path, cache state, and retry reason.

Track `trace_id`, `thread_id`, `turn_id`, `item_id`, `attempt`, and `deadline_ms` on every span.

## Milestone events

Track accepted request, turn start, retrieval completion, reasoning start, first token, tool start, tool completion, plan update, and turn completion.

## Tool wrapper instrumentation

Start the span when the runtime accepts the tool call, not when the child process starts. Include schema validation, permission check, sandbox creation, process startup, stdout capture, and encoding.

## Retrieval as an SLO

Track `retrieval.tokens_selected` alongside `retrieval.p95_ms`. A retrieval stage that meets its millisecond SLO while returning huge context still breaks the system downstream.

## Inference by turn role

Segment all inference metrics by turn role. Track queue time, prefill time, first-token time, decode rate, output tokens, and cache read tokens separately.

## Cost denominators

Never report cost per call. Report cost per completed task. Also log input and output tokens separately. Failed attempts bill in full.

## Key cost facts

- Output tokens are more expensive than input tokens.
- Failed attempts bill in full.
- Prompt caching saves a fixed fraction only on the repeated prefix.
- Human review can dominate cost at low escalation rates.

## Failure-mode signatures

Alert on p95/p99 jumps, unbounded retry loops, approval prompts that stall, and retrieval that returns far too many tokens.
