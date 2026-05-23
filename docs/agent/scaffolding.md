# Scaffolding: prefer official generators over hand-written templates

Most ecosystems ship an official generator for starting a new project,
creating a new package, or adding a framework-specific artefact. Use
those generators. Their output reflects the ecosystem's current
conventions, directory layouts, build tool versions, and idiomatic
patterns — the very things your training data is most likely to have
a stale view of.

Hand-written boilerplate is the fallback, not the default.

## Rule of thumb

Before writing config files, project skeletons, or framework-specific
files from scratch, ask: **does an upstream tool generate this?**

- New Node project → `pnpm init` (for bare `package.json`), or one of
  the framework-specific creators for a framework-scaffolded project.
- New Next.js app → `pnpm create next-app@latest`.
- New Vite app → `pnpm create vite@latest`.
- New Astro app → `pnpm create astro@latest`.
- New Python package → `uv init --package` or the equivalent for the
  build tool in use (`hatch new`, `poetry new`).
- New Python project with a specific framework → the framework's
  cookiecutter / template CLI when one exists.
- New Rust crate / binary → `cargo new --lib <name>` / `cargo new <name>`.
- New Go module → `go mod init <path>`.
- New database migration → the ORM or migration tool's own CLI
  (`alembic revision`, `pnpm drizzle-kit generate`, `pnpm prisma
  migrate dev`, `sqlx migrate add`, etc.). Never hand-author a
  migration file when the tool can generate one.
- New component / route / model inside an opinionated framework →
  the framework's own generator when it has one (Rails `bin/rails
  generate`, Nest `nest g`, etc.).

## Why

1. **The generator is current.** It was updated when the ecosystem
   was updated. Your memory was not.
2. **The generator is idiomatic.** The files it produces are the
   reference for "how people lay out a project of this kind right
   now", which is exactly the thing you are most likely to guess
   incorrectly.
3. **The generator is complete.** It produces the set of files the
   framework actually expects, including the ones that are easy to
   forget (`.gitignore` entries, `tsconfig.json` paths, lock files,
   `engines` fields).

## How to run generators in this environment

The Dev Container has `pnpm`, `npx`, and the language runtimes listed
in its Dockerfile. Run generators from inside
`/workspaces/<project-name>`.

Some generators ask interactive questions. If you are running
non-interactively, check the generator's `--help` for flags that
answer them in advance (`--yes`, `--ts`, `--tailwind`, etc.). If you
cannot avoid interactivity and you are running in an agent session,
stop and ask the user to run the generator themselves; surface the
exact command you would have run.

## When to bypass a generator

- The generator's output is demonstrably wrong for this project's
  conventions, and the difference is small enough to fix by hand.
- No generator exists for the artefact in question (many utility
  libraries have no scaffolder).
- The team has explicitly decided against it, recorded in an ADR.

In all three cases, write the rationale in the commit message (or the
ADR) so the next contributor knows the bypass was deliberate.

## When in doubt

If you do not know whether a generator exists for what you are about
to hand-write, **ask**. A 10-second clarification ("is there a
preferred way to scaffold X in this project?") is cheaper than
producing hand-written files that do not match what the team expected.
