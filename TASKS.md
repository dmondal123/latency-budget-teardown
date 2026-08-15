1. Refine RAG_PIPELINE_PLAN.md using the evaluation
     and latency skills.
      - Establish the pipeline stages, baseline metrics,
        p50/p95 waterfall, quality gates, two isolated
        interventions, and budget methodology first.

  2. Add/update the architecture documentation.
      - It should explain the retrieval → model →
        validation flow and where instrumentation,
        clocks, budgets, and experiments sit.

  3. Create the documentation scaffolding:
      - PROGRESS.md
      - an experiment log (description, steps, results,
        observations, learnings)

      - COLLABORATION_NOTES.md

  4. Improve AGENTS.md.
      - Link all core docs, define when parallel agents
        are appropriate, define GitNexus invocation
        policy, enforce the three-MCP maximum, and state
        the commit convention.

  5. Decide GitNexus policy: invoke it on demand, not as
     a hook.
      - A hook adds friction and context/tool overhead;
        the existing “impact before symbol edits” rule
        is sufficient.

  6. Keep MCPs and skills selectively enabled.
      - This is an ongoing operating rule, not a one-
        time deliverable. Prefer CLIs and keep at most
        three MCPs active.

  7. Maintain PROGRESS.md, the experiment log, and
     collaboration notes continuously.
      - Update progress after meaningful milestones.
      - Log every experiment immediately after its run.
      - Update collaboration notes for significant agent
        decisions/corrections, especially before
        commits.

  8. Commit each completed feature/fix with a short
     message.
      - Also ongoing; do it after each small, validated
        unit of work—not for every documentation
        keystroke.