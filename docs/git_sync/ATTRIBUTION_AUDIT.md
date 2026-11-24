# Attribution audit (Task B3)

Scope: every tracked file in the working tree (README, docs, manuscript/supplement
LaTeX, source headers, generated reports, release metadata, repository description)
plus the full commit-message history on every local branch, searched case-insensitively
for `claude`, `chatgpt`, `openai`, `codex`, `claudecode`.

## What was checked and the result

| Surface | Checked | Result |
|---|---|---|
| README.md, PROJECT_DOCUMENTATION.md, README_ICAPS_EXPERIMENTS.md | yes | no matches |
| AUTHORS / CITATION / CONTRIBUTING files | yes (searched the whole tree) | none exist in the project itself (matches found only inside third-party packages under `.venv*/`, e.g. pip's own `AUTHORS.txt` — unrelated, left untouched) |
| Manuscript and supplement author lines | yes (`\author{...}` in both `.tex` files) | `Anonymous Submission` in both; no tool name |
| Source file headers (`phase0/`, `scripts/`, `tests/`) | yes | no matches |
| Generated reports (`docs/final_icaps/*.md`, `docs/multisolver/*.md`) | yes | no matches |
| GitHub repository description / topics | yes (`gh repo view`) | both empty |
| GitHub releases | yes (`gh release list`) | none exist |
| Commit messages, all 76 commits on all 6 local branches | yes (`git log --all`) | see below |

## Commit-message finding (requires an author decision)

Every commit this assistant created in this project — 76 commits across all
branches, from the start of this project's use of Claude Code through the most
recent commit (`0b77c2a`) before this audit — ends with a trailer of the form:

```
Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

This is the standard Git co-author trailer the Claude Code harness appends to
every commit it creates, by a standing instruction given to the assistant at the
start of each session (independent of, and predating, this task's B1
instruction). It is a provenance marker on a historical, already-created commit,
not an authorship credit inserted into the paper, README, or any contributor
list.

**Action taken:** none of the 76 existing commits were amended or rewritten.
Task B2 explicitly prohibits rewriting historical commits to conceal prior
activity, and `origin` is a public GitHub remote with this history already
pushed — rewriting it would also force-rewrite shared history, which Task C3
separately prohibits without explicit authorization. This audit does not decide
that question; it is recorded here as the one outstanding author action from
Part B of this task:

> **Author decision needed:** whether the pre-existing `Co-Authored-By: Claude`
> trailers on past commits should remain (they are an accurate record of how
> those commits were produced) or be scrubbed via a history rewrite — which
> would require force-pushing and coordinating with anyone who has already
> cloned the public repository.

**Going forward:** per this task's explicit instruction (Part B1/C2), commits
created for the remainder of this task (the reproducibility pipeline, this
audit, and the final git-sync work) omit the `Co-Authored-By: Claude` trailer.
This is a user instruction specific to this repository and this task, and takes
precedence over the harness's standing default for new commits from this point
on; it does not retroactively change any already-created commit.

## No fabricated or altered authorship

- No human author's name, identity, or git `user.name`/`user.email` was invented,
  removed, or replaced anywhere in the repository.
- The manuscript's `Anonymous Submission` author line is the double-blind
  convention for a submission under review, not a concealment of AI assistance;
  the required disclosure of AI-assisted writing (if the venue's policy asks for
  one) is listed as an outstanding author action in
  `docs/final_icaps/FINAL_MULTISOLVER_RESEARCH_REPORT.md`, section 14, and no
  statement claiming "no AI assistance was used" appears anywhere in the
  manuscript, supplement, or repository.
- `git log` author/committer identity (the repository owner's real name and
  email on commits predating and alongside this assistant's commits) was left
  untouched.

## Verdict

**ATTRIBUTION COMPLIANCE: REQUIRES REVIEW** — not because any new issue was
introduced by this task, but because of the one pre-existing, documented
decision above (historical commit trailers). No manuscript, documentation,
README, or repository-metadata attribution to an AI tool as an author,
contributor, or implementer was found anywhere.
