# Project Guidelines

## Plan-first workflow is mandatory for all creation tasks

For **any non-trivial creation work** in this repo — new features, refactors, schema/migration changes, cross-cutting edits, new scripts, new modules, or anything where getting the design wrong is expensive — you MUST use the `plan-first-workflow` skill (`.claude/skills/plan-first-workflow/SKILL.md`).

That means: invoke the skill, then proceed through its four phases in order — Research (`research.md`), Planning (`plan.md`), Annotation Cycle, Implementation — and **do not write code until the user has explicitly approved `plan.md`.**

Exceptions: trivial one-line fixes, typos, obvious bugs, or read-only questions. When in doubt, default to using the skill.

If the user says "just do it" on a non-trivial task, gently push back and offer to write a quick plan first.
