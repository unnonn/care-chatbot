---
name: plan-first-workflow
description: Plan-first AI-assisted development workflow based on Boris Tane's methodology — never write code until a written plan has been reviewed and approved. Use when the user wants to tackle a non-trivial feature, refactor, or migration with deep research, an annotated `plan.md`, and disciplined execution. Triggers include "plan first", "計画優先", "research then implement", "annotate the plan", "boris tane workflow", or any request to plan a feature before implementing it.
---

# Plan-First Workflow

A disciplined, four-phase workflow that separates **thinking** from **typing**. The core rule: **never write code until the user has reviewed and approved a written plan.**

The plan lives in markdown files in the repo (`research.md`, `plan.md`) — not in chat — so it survives context compaction, is reviewable in an editor, and becomes the shared mutable state between the user and Claude.

## When to use this skill

Use it for any task that is more than a one-line change:
- New features
- Non-trivial refactors
- Schema/migration work
- Cross-cutting changes that touch multiple files
- Anything where getting the design wrong is expensive

For trivial fixes (typo, one-liner, obvious bug), skip this skill and just do it.

## The Four Phases

Make a todo list with these four phases and work through them in order. **Do not skip ahead.**

### Phase 1 — Research

Goal: prove you understand the surrounding code well enough to plan a correct change.

1. Identify the relevant areas of the codebase, related modules, existing patterns, and any constraints.
2. Read them **deeply** — not just the file you'll edit, but its callers, its tests, and any nearby modules that establish conventions.
3. Write findings to `research.md` at the repo root (or `.claude/plans/research.md` if the user prefers to keep the repo clean).

`research.md` should contain:
- Which files/modules are relevant and why
- Existing patterns to match (with file path + line number references)
- Constraints, invariants, and gotchas you discovered
- Open questions for the user
- Links to any external docs or open-source implementations worth referencing

Use deliberate language to signal depth: "I read X **deeply**, including its callers in Y and Z." This is for the user's review — they should be able to verify your comprehension before you plan anything.

**Stop here. Ask the user to review `research.md` before moving on.**

### Phase 2 — Planning

Once research is approved, draft `plan.md` (same location as `research.md`).

`plan.md` should be detailed enough that implementation becomes mechanical:
- Concrete file paths and the changes each one needs
- Code snippets for non-obvious sections
- Phased task list (Phase 1, Phase 2, …) with checkboxes
- Explicit trade-off notes where decisions were made
- References to existing patterns to mirror (e.g. "match the shape of `users` table exactly")
- Out-of-scope list — what we are deliberately **not** doing

Prefer custom markdown over the built-in plan mode so the user can edit it directly.

**Stop here. Hand the plan to the user and explicitly say: do not implement yet.**

### Phase 3 — Annotation Cycle (the most important phase)

The user reviews `plan.md` in their editor and adds inline notes — corrections, rejections, domain knowledge, constraint clarifications. They send it back.

For each pass:

1. Read every annotation carefully. Treat each as a hard constraint.
2. Update `plan.md` so the annotations are resolved (rewrite sections, drop rejected ideas, fold in domain knowledge).
3. Surface any annotation you don't understand — ask, don't guess.
4. Reply with a short summary of what changed, and ask the user to review again.
5. **Do not start implementing.** Wait for the user to explicitly approve the plan.

Expect 1–6 rounds. Common annotation types:
- Domain corrections ("use `drizzle:generate` for migrations, not raw SQL")
- Approach rejections ("remove this section entirely")
- Constraint clarifications ("visibility field belongs on the list itself, not the items")
- Interface protections ("this function signature is fixed — do not change it")

Markdown is the shared mutable state. Don't rehash decisions in chat that belong in the plan.

### Phase 4 — Implementation

Only after the user explicitly approves `plan.md`. Then execute with this standardized stance:

> Implement the full plan. As you complete each task or phase, mark it `[x]` in `plan.md`. Do not stop until everything is done. Do not add unnecessary comments or jsdocs. Do not use `any` or `unknown` types. Continuously run typecheck (and linter/tests when relevant) and fix issues as they appear.

While implementing:
- Treat the plan as the spec. If you discover the plan is wrong, **stop and update `plan.md` first**, then continue — don't silently deviate.
- For UI/frontend work, expect more iteration. Use screenshots from the user for visual issues.
- When direction derails, prefer reverting and re-scoping over patching incrementally.
- Keep updating the checkboxes — the plan file is the live progress log.

## Operating Principles

- **One continuous session.** Research, plan, annotate, and execute in the same session. The markdown files persist across context compaction with full fidelity, so the session can be long.
- **Driver control stays with the user.** Cherry-pick proposals at item level, trim scope, protect interfaces, surface technical choices the user might want to override.
- **Plan files survive, chat doesn't.** Put decisions in `plan.md`, not in chat messages. Chat is for navigation and quick clarification.
- **Never code without an approved plan.** If the user asks you to "just do it" on a non-trivial task, gently push back and offer to write a quick plan first. The plan can be short — it just has to exist and be approved.

## Wrap-up

When the implementation phase finishes:

1. Make sure every checkbox in `plan.md` is checked, or that uncompleted items have a clear note explaining why.
2. Run typecheck, linter, and tests one final time.
3. Summarize for the user: what was built, what was deferred, and any follow-ups.
4. Ask whether `research.md` and `plan.md` should be committed alongside the code (useful as a paper trail) or deleted before committing.
