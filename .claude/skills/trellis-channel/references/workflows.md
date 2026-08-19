# Workflows

Use these patterns by intent. Prefer durable channels for multi-round work and
`channel run` for one-shot questions.

## Pattern A: Multi-round Brainstorm

Use when the user says "和 codex/claude 讨论一下", "brainstorm", or "拉一个 agent
进来一起看".

```bash
trellis channel create brainstorm-storage-layer --by main \
  --task .trellis/tasks/05-XX-storage-adapter

trellis channel spawn brainstorm-storage-layer \
  --agent architect --provider codex \
  --file .trellis/tasks/05-XX-storage-adapter/prd.md \
  --file .trellis/tasks/05-XX-storage-adapter/design.md \
  --as cx-arch --timeout 30m

trellis channel send brainstorm-storage-layer \
  --as main --to cx-arch --text-file /tmp/brainstorm-r1.md

trellis channel wait brainstorm-storage-layer \
  --as main --kind done --from cx-arch --timeout 10m
```

Do not stop after one answer. Read the answer, identify vague areas, send a
new probe, and repeat until the result is executable.

Minimum round structure:

1. Direction split: should this live in an existing mechanism or a new one?
2. MVP boundary: v1, v2, and what would force v2 back into v1.
3. Data contract: events, schema, metadata, state source of truth, compatibility.
4. CLI / UX contract: command names, flags, errors, defaults, ambiguity.
5. Cross-layer risk and tests: shared helpers, drift points, release-blocking tests.

Optional rounds:

- Operations: logs, debugging, stuck workers, kill/restart, recovery.
- Migration/release: breaking status, manifest, changelog, docs-site.
- Opposition review: ask the peer agent to argue against the current plan.

Every probe should request concrete file paths, commands, schema, rejected
alternatives, and release-blocking issues. Reject hedging when a decision is
needed.

## Pattern B: Implement / Check Agent

Use when the user asks to dispatch implementation or review work.

```bash
TASK=.trellis/tasks/05-12-foo
trellis channel create cr-foo --task "$TASK" --by main

trellis channel spawn cr-foo \
  --agent check \
  --jsonl "$TASK/check.jsonl" \
  --file "$TASK/prd.md" \
  --file "$TASK/design.md" \
  --file "$TASK/implement.md" \
  --cwd "$PWD" --timeout 15m

trellis channel send cr-foo --as main --to check --text-file /tmp/cr-brief.md
trellis channel wait cr-foo --as main --kind done --from check --timeout 15m
trellis channel messages cr-foo --kind message --from check --tag final_answer
```

For implement work, use `--agent implement` and send an implementation brief.
For check work, include the exact diff scope, relevant specs, and validation
already run.

## Pattern C: Parallel Reviewers

Use one channel and distinct worker names.

```bash
trellis channel create cr-feature --by main --ephemeral

trellis channel spawn cr-feature --agent check \
  --jsonl "$TASK/check.jsonl" --file "$TASK/prd.md" --file "$TASK/design.md" \
  --timeout 15m

trellis channel spawn cr-feature --agent check --provider codex --as check-cx \
  --jsonl "$TASK/check.jsonl" --file "$TASK/prd.md" --file "$TASK/design.md" \
  --timeout 15m

trellis channel send cr-feature --as main --to check --text-file /tmp/cr-brief.md
trellis channel send cr-feature --as main --to check-cx --text-file /tmp/cr-brief.md
trellis channel wait cr-feature --as main --kind done --from check,check-cx --all --timeout 15m
```

`--all` means every listed worker must emit a matching event.

## Pattern D: One-shot Worker

```bash
trellis channel run --provider codex --message "say hi in 3 words" --timeout 1m
trellis channel run --agent plan --message-file /tmp/plan-question.md --timeout 10m
```

On success, `run` removes the ephemeral channel. On error/timeout/killed, it
keeps the channel and prints the path for inspection.

## Pattern E: Forum Channel

Use for issue forums, topic-style feedback, release todos, agent findings, and
internal changelogs. Read `forum.md` for the full model.

## Pattern F: Take Over Existing Thread

If the user gives a forum/thread name, restore context yourself:

```bash
trellis channel forum <board> --scope global
trellis channel thread <board> <thread> --scope global --raw
trellis channel context list <board> --scope global --thread <thread>
trellis channel messages <board> --scope global --raw --thread <thread>
```

Output a constraint summary, not a transcript dump:

- user-level problem
- context files that affect this repo
- current-version versus future-version requirements
- whether current code/design satisfies it
- next action or comment to append

## Pattern G: Dual-model Plan Analysis

Use the Codex and Antigravity analysis cards in parallel, then synthesize both
outputs in the main session. Workers start idle — always `create` → `spawn` →
`send` the same brief → `wait --all`.

```bash
TASK=.trellis/tasks/<active-task>
BRIEF=/tmp/plan-dual-brief.md   # requirements + open questions

trellis channel create plan-dual --by main --task "$TASK"

trellis channel spawn plan-dual \
  --agent analyze-cx --provider codex --as analyze-cx \
  --file "$TASK/prd.md" --timeout 30m

trellis channel spawn plan-dual \
  --agent analyze-agy --provider antigravity --as analyze-agy \
  --file "$TASK/prd.md" --timeout 30m

trellis channel send plan-dual --as main --to analyze-cx --text-file "$BRIEF"
trellis channel send plan-dual --as main --to analyze-agy --text-file "$BRIEF"

trellis channel wait plan-dual \
  --as main --from analyze-cx,analyze-agy --kind done --all --timeout 30m
```

After both workers finish, the main session synthesizes into `design.md` /
`prd.md` and sets `task.json` `meta.collab.dual_analysis_used = true`.

## Pattern H: Three-way Review

Use the Claude check worker with both read-only cross-review cards, then
arbitrate findings in the main session. Same idle-worker contract as Pattern G.

```bash
TASK=.trellis/tasks/<active-task>
BRIEF=/tmp/cr-3way-brief.md   # diff scope + specs + focus questions

trellis channel create cr-3way --by main --ephemeral

trellis channel spawn cr-3way \
  --agent check --provider claude --as check \
  --jsonl "$TASK/check.jsonl" --file "$TASK/prd.md" --file "$TASK/design.md" \
  --timeout 20m

trellis channel spawn cr-3way \
  --agent review-cx --provider codex --as review-cx \
  --jsonl "$TASK/check.jsonl" --file "$TASK/prd.md" --file "$TASK/design.md" \
  --timeout 20m

trellis channel spawn cr-3way \
  --agent review-agy --provider antigravity --as review-agy \
  --jsonl "$TASK/check.jsonl" --file "$TASK/prd.md" --file "$TASK/design.md" \
  --timeout 20m

trellis channel send cr-3way --as main --to check --text-file "$BRIEF"
trellis channel send cr-3way --as main --to review-cx --text-file "$BRIEF"
trellis channel send cr-3way --as main --to review-agy --text-file "$BRIEF"

trellis channel wait cr-3way \
  --as main --from check,review-cx,review-agy --kind done --all --timeout 20m
```

Main session arbitrates Critical/Warning/Info across the three reports before
declaring step 2.2 complete.
