# Agent documentation index

Documentation written with Claude Code (and similar agents) as the
primary reader. `CLAUDE.md` links here for anything that does not need
to be resident in context on every turn.

| Document                                                           | Purpose                                                                  |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| [documentation-policy.md](documentation-policy.md)                 | Full documentation scheme: audiences, ADRs, PRD lifecycle                |
| [git-workflow.md](git-workflow.md)                                 | Branching, commits, push, and PR workflow (`main` is read-only)          |
| [when-to-write-an-adr.md](when-to-write-an-adr.md)                 | Concrete criteria for deciding whether a change needs an ADR             |
| [how-to-start-a-new-feature.md](how-to-start-a-new-feature.md)     | Default workflow from ambiguous ask to declared-done                     |
| [verifying-current-practice.md](verifying-current-practice.md)     | How to confirm library versions and API shapes without `WebFetch`        |
| [scaffolding.md](scaffolding.md)                                   | Prefer official generators (`pnpm create …`, `cargo new`, …) over boilerplate |
| [external-information.md](external-information.md)                 | Why `WebFetch` is denied, what to do when external info is needed, and why guessing is worse |
| [common-traps.md](common-traps.md)                                 | Running list of things that have looked right and been wrong             |

<!--
When adding a new playbook here:
  1. Create the file under docs/agent/ with a task-shaped name
     (e.g. "how-to-add-a-migration.md", "test-recipes.md").
  2. Add a row above with a one-line summary.
  3. If the playbook is something the agent should consult on every
     relevant task, add a pointer to it from CLAUDE.md §4 or §9.
     Otherwise, this index is sufficient.
-->
