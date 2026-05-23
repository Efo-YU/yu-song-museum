# Common traps

Running list of things that have looked right and been wrong when
**writing code** in this repository. Add to this file whenever a
subtle mistake is caught in review or after the fact — it spares the
next contributor, human or agent, from repeating it.

**Scope.** This file covers mistakes in the code-writing loop
(choosing APIs, structuring changes, handling dependencies).
Environment-level problems (Dev Container won't start, DNS hanging,
volume not persisting) go in the README's troubleshooting section,
which is oriented at humans setting up or recovering the
environment. If you are unsure, place the entry wherever the symptom
first appears — the two files are allowed to cross-reference each
other.

Each entry is short: the symptom, the cause, and the lesson.

<!--
Template for new entries:

## <Short, searchable title>

**Symptom.** <What looks right or what error appears.>

**Cause.** <Why the naive approach fails here.>

**Lesson.** <What to do instead, in one sentence.>
-->

## Writing files outside `/workspaces/<project-name>`

**Symptom.** Files created during a session disappear after the
container is rebuilt.

**Cause.** Anything written outside the workspace bind mount lives in
the container's writable layer, which is discarded on rebuild.

**Lesson.** All project artefacts go under
`/workspaces/<project-name>`. Personal scratch goes outside the repo
entirely (CLAUDE.md §10).

## Writing code from training-data memory instead of installed reality

**Symptom.** The code type-checks in your head but fails at runtime,
or lint/type-checker reports that a function or option does not
exist. Stack traces mention APIs whose names are almost but not
quite right.

**Cause.** The library moved between your training cutoff and the
version this repository actually uses. You wrote the older shape;
the installed version no longer has it.

**Lesson.** Before calling into a third-party API you are not certain
about, check the installed source or run the registry query
described in
[`verifying-current-practice.md`](verifying-current-practice.md). If
you still cannot confirm, ask the user. Never guess.

## Hand-writing framework boilerplate when a generator exists

**Symptom.** The files you produce look mostly right but are subtly
wrong — missing a build config, a TypeScript path, a `package.json`
field, a lockfile — and the next contributor cannot just "run the
project".

**Cause.** The framework's own scaffolder would have produced a
current, complete skeleton; hand-authored versions reflect your
training-data snapshot of the framework, which is often a release
or two behind.

**Lesson.** Run the official generator (`pnpm create next-app`,
`cargo new`, `uv init`, etc.) rather than hand-writing the
skeleton. See [`scaffolding.md`](scaffolding.md) for the fallback
policy.

## Editing `package.json` by hand instead of using the package manager

**Symptom.** `pnpm-lock.yaml` drifts from `package.json`, CI fails
with an "out of sync" error, or teammates' installs produce a
different dependency graph than yours.

**Cause.** You added or changed a dependency by editing
`package.json` directly. The lockfile was not updated to match, so
subsequent `pnpm install` runs produce inconsistent results.

**Lesson.** Use `pnpm add`, `pnpm remove`, `pnpm update` — never
hand-edit the `dependencies` or `devDependencies` blocks. The same
rule applies to `uv add` / `cargo add` / `go get` in their
respective ecosystems.

## Adding a dependency without an ADR

**Symptom.** A dependency appears in the lockfile with no
corresponding ADR or developer-doc entry, and no one remembers why
it was chosen over alternatives.

**Cause.** It felt like "just adding a library", but adding a
dependency is a decision (see
[`when-to-write-an-adr.md`](when-to-write-an-adr.md)).

**Lesson.** New direct dependencies get an ADR or, at minimum, a
line in the relevant developer doc explaining what they are for and
why this one. This is part of the Definition of Done (CLAUDE.md
§8).
