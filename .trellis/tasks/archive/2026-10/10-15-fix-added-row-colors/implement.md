# Implementation Plan and Sonnet Handoff

## Current Status and Authorization

- Status: **planning**. This delivery creates planning artifacts only.
- Task: `.trellis/tasks/10-15-fix-added-row-colors`.
- Worktree: `/home/decade/Data-Comparator-addition-color-plan`.
- Branch: `plan/addition-colors`; base: `main` at `b28b458` when created.
- Intended later executor: Sonnet, as requested by the user. No executor has been launched.
- User approval of task creation does **not** approve implementation. Obtain a subsequent explicit approval of the final plan before `task.py start` or source/test edits.
- Do not commit, merge, push, archive, delete branches/worktrees, or install dependencies without the required separate authorization. Leave the planning worktree available for handoff.

## Allowed Future Write Scope

1. `src/backend/domain/excel_utils.py`: minimal row-fill selection and directly affected comments/docstring only.
2. `tests/test_highlight_colors.py`: focused unit plus workbook integration/end-to-end regressions.
3. This task's artifacts and metadata as execution evidence develops.
4. `.trellis/spec/backend/excel-data-guidelines.md`: after implementation, add a concise verified row/header/tab color contract through the spec-update phase; preserve all existing Excel invariants.

Existing test files are regression read/run targets, not planned rewrites. Broader production changes require an explanation and scope review first. The original checkout at `/home/decade/Data-Comparator` contains pre-existing, uncommitted Trellis toolchain changes; do not copy, overwrite, commit, or clean them up.

## Ordered Checklist

### 0. Approval and preflight

- [ ] The user explicitly approves the final scope: added rows use the configured addition color; added-column bodies and deletion colors are not redesigned.
- [ ] Enter the existing task worktree; verify the branch, worktree status, and task metadata. Continue on this dedicated task branch rather than modifying `main` or creating a competing writer.
- [ ] Read curated `implement.jsonl` entries, then `prd.md`, `design.md`, and this file. Load `trellis-before-dev` and relevant module/test instructions before editing code.
- [ ] Validate the task manifests and fetch phase 1.4 guidance. Only after approval, run:

```bash
cd /home/decade/Data-Comparator-addition-color-plan
python3 ./.trellis/scripts/task.py validate .trellis/tasks/10-15-fix-added-row-colors
python3 ./.trellis/scripts/get_context.py --mode phase --step 1.4
python3 ./.trellis/scripts/task.py start .trellis/tasks/10-15-fix-added-row-colors
```

- [ ] Verify that `task.json.status` is `in_progress`. If session identity is missing, follow the actual CLI hint rather than inventing an identity or bypassing the activation gate.
- [ ] Check the selected Python environment has the existing runtime/test dependencies, `pytest-cov`, and quality tools. Confirm `src.__file__` resolves inside this worktree. Do not dump environment values or inspect ignored virtual-environment contents.
- [ ] Record a pre-change full-test/coverage baseline with the same interpreter and coverage options used for final verification:

```bash
python3 -m pytest tests --cov=src --cov-report=term-missing
```

If `pytest-cov` or other required tools are missing, report the limitation and request installation authorization; do not change dependencies/build scripts. If the baseline is failing or below 80%, record the exact blocker and seek a bounded resolution rather than hiding it or expanding this task into unrelated test work.

### 1. RED — reproduce the color defect with tests first

- [ ] Create `tests/test_highlight_colors.py` using real `ConfigManager`, `Workbook`, and highlighter objects. Use synthetic values only, local fixtures, and Arrange/Act/Assert organization.
- [ ] Parameterize default colors and three distinct custom colors (for example update `#112233`, deletion `#445566`, addition `#778899`). Assert exact solid fill/ARGB values, not merely the existence of a fill.
- [ ] Add single-behavior tests for: an added row including empty cells; deleted rows retaining `highlight_fill`; updates coloring only changed cells; unchanged cells staying unhighlighted; marker font preservation; added/deleted/ordinary header colors with display labels different from SAS names.
- [ ] Add `@pytest.mark.integration` report cases listed in the matrix below. Reopen the generated `.xlsx` output and close workbook handles. Use `tmp_path` for all generated files. Do not mock the highlighter or comparison pipeline under test.
- [ ] Run the new file **before changing production code** and record the expected failures: added-row fill assertions should fail because the old code uses the update fill. Verify that unrelated color-preservation assertions already pass.

```bash
python3 -m pytest tests/test_highlight_colors.py -q
```

### 2. GREEN — smallest implementation

- [ ] Inside the existing `mark_value in ("新增", "删除")` branch, select `config.new_sheet_tab_fill` only for `新增`; keep `config.highlight_fill` for `删除`.
- [ ] Reuse the selected fill for the existing row-cell loop. Preserve marker styling, function signature, `diff_keys` location, cancellation checks, and the update branch.
- [ ] Update only directly affected comments/docstrings. Do not refactor large functions, alter defaults, or modify API/frontend/config schemas.
- [ ] Rerun the new regression file and confirm all tests pass.

### 3. Regression and full verification

- [ ] Run focused compatibility tests without weakening their existing assertions:

```bash
python3 -m pytest tests/test_highlight_colors.py tests/test_highlight_stop_and_perf.py tests/test_merge_deleted_data_alignment.py tests/test_compare_scope_and_order.py tests/test_highlight_optimizer.py tests/test_processing_control.py -q
```

- [ ] Run full tests and the coverage gate; compare the percentage with the recorded pre-change baseline. The final percentage must be at least 80% and must not fall below the baseline. Do not lower the threshold or exclude code to make the gate pass.

```bash
python3 -m pytest tests --cov=src --cov-report=term-missing --cov-fail-under=80
```

- [ ] Run scoped quality checks with available existing tools:

```bash
python3 -m black --check src/backend/domain/excel_utils.py tests/test_highlight_colors.py
python3 -m isort --check-only src/backend/domain/excel_utils.py tests/test_highlight_colors.py
python3 -m py_compile src/backend/domain/excel_utils.py tests/test_highlight_colors.py
```

- [ ] Use the project's existing mypy configuration if the tool is available; record unavailable checks explicitly. Do not silently install tools or add configuration. If a check finds a pre-existing issue, distinguish it from this patch and do not reformat/rewrite unrelated code.
- [ ] Run `trellis-check` within the approved write scope. Inspect the actual diff, including the contents of new untracked tests, for accidental deletion recoloring, schema changes, broad formatting, and lost stop/alignment safeguards. Do not describe self-review as independent review.
- [ ] No frontend/browser check is planned because the scoped UI/API are unchanged. Report the saved-workbook integration/end-to-end coverage instead; do not claim a browser flow was validated.

### 4. Spec and delivery

- [ ] Review the verified color contract through `trellis-update-spec`; add a short section to `.trellis/spec/backend/excel-data-guidelines.md` covering added rows versus existing header/tab and deletion/update behavior. Do not update it during this planning-only turn.
- [ ] Update task evidence and report RED, GREEN, focused/full checks, baseline/final coverage, and not-run/failed/environment-blocked items separately.
- [ ] Stop before any unrequested commit or publication. Trellis bookkeeping/spec changes must remain separate from project-code commits if the user later authorizes commits.

## Observable Regression Matrix

| Case | Input/scenario | Required observation | AC |
| --- | --- | --- | --- |
| U1 | `新增` row with non-empty and empty cells; default/custom palettes | Every row cell is solid addition fill, including marker and blanks | AC1 |
| U2 | Deleted row, updated row with one changed field, unchanged row; separate tests | Previous row/cell fills and marker font stay intact | AC5 |
| U3 | Added/deleted/ordinary columns, SAS names different from displayed labels | Header fills resolve through SAS metadata, not visible labels | AC4 |
| I1 | Common sheet containing added, updated, deleted, unchanged subjects; parameterize merge on/off | New row addition-colored; values/markers correct; update highlights aligned after filtering; deleted row preserved/omitted according to the flag | AC1/AC5 |
| I2 | Old workbook has a common sheet; new workbook also has a new-only sheet with multiple records | Saved new sheet's tab and data rows match custom addition color; ordinary headers unchanged | AC2 |
| I3 | A sheet exists in both files; old has only headers and new has data | Saved added rows use addition fill through the special empty-to-populated branch | AC3 |
| I4 | Existing sheet gains a column; at least one non-empty added value and one empty value | Added header uses addition fill; body cells retain existing row/diff-based behavior, not unconditional column recoloring | AC4 |
| R1 | Existing cancellation, diff-key and alignment suites | No regression of stop behavior, normalization cost, key-type equivalence, or positional highlights | AC6 |
| R2 | Full suite plus baseline/final coverage and actual diff review | No regressions, no coverage decrease, minimum 80%, bounded diff | AC7 |

## Planning-Only Verification Record

This session inspected the actual UI color keys, configuration assembly, shared highlighter, new-sheet/empty-sheet branches, common write path, existing tests, and quality specs. It did **not** run the code tests or measure coverage; those are execution-stage checklist items, not completed results.

A baseline worktree was intentionally created from committed `main`, not from the original checkout's uncommitted Trellis edits. Its task CLI supports planning artifacts and manifests. Developer initialization was absent, so task creation used the existing repository user via `--assignee decade6666`; no developer settings were changed.

## Execution Record (2026-10-15)

Approval: the user confirmed the final scope in the execution turn; `task.py start` flipped the task to `in_progress` inside this worktree.

- Environment: dedicated `uv` venv at `.venv/` (gitignored) created with user authorization; `httpx2` added with explicit user approval after the auto classifier blocked the install (starlette 1.8.0 TestClient requirement; `tests/conftest.py:8` blocks all collection without it). Interpreter resolves `src` inside this worktree; pandas 2.3.3 satisfies the `<3.0.0` constraint.
- Baseline (before the production change): `pytest tests --cov=src --cov-report=term-missing` → 342 collected = 330 pre-existing tests all passed + 12 new tests (6 expected RED failures, 6 protection passes); TOTAL coverage 84% (3998 stmts / 630 missed). No pre-existing failures.
- RED: the 6 added-row assertions failed with exactly the wrong-fill symptom (default `FFFFE5E5` vs expected `FF00FF00`; custom `FF112233` vs expected `FF778899`); all 6 protection assertions passed.
- GREEN: `excel_utils.py` row-fill selection (新增 → `new_sheet_tab_fill`, 删除 → `highlight_fill`) plus the directly affected docstring lines. New test file after the change: 12/12 passed.
- Focused regression (colors / stop-perf / merge-deleted alignment / scope-order / optimizer / processing-control): 48 passed.
- Full + gate: `pytest tests --cov=src --cov-report=term-missing --cov-fail-under=80` → 342 passed, TOTAL 84% (3999 stmts / 630 missed); gate passed, no coverage decrease vs baseline.
- Quality: black (one reformat of the new test file), isort, py_compile, mypy (project config, both changed files) all clean.
- Independent review: `trellis-check` sub-agent — 7/7 checks passed, 0 defects, 0 self-fixes; independently re-ran focused (48 passed) and full (342 passed, 84.25%).
- Spec: the verified color contract was appended to `.trellis/spec/backend/excel-data-guidelines.md`.
- Not run / environment-limited: no real Python 3.8 interpreter available (3.8 compatibility by syntax review; the venv is 3.12.3); the reviewer did not re-verify RED by rolling the hunk back (the main-session RED run above is the recorded evidence); no browser validation (UI/API unchanged by design). No commit/push per user instruction; task left `in_progress` pending the user-authorized finish flow.
