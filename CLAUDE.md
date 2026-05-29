# CLAUDE.md — Project Operating Manual for Claude Code

<!--
This file is loaded on every Claude Code session in this repository.
It must stay short: every line here competes for the model's
attention on every turn. Detail lives in `docs/agent/`; this file is
the index.

Size budget: this file should stay under ~270 lines. If it grows
past that, extract the least-referenced sections into
`docs/agent/*.md` and leave pointers behind. See §11.

When adapting the template to a real project, fill in §1–§4 and leave
§5–§10 intact unless you have a concrete reason to change them.
-->

## 1. Project overview

A CI/CD-for-music-production platform that automates vocal synthesis
(NEUTRINO), accompaniment mixing (FluidSynth + FFmpeg), video
generation, YouTube upload (via a GAS relay), and website deployment
whenever MusicXML or configuration files change.  The system processes
only the songs that differ in each push.  A React + OSMD single-page
app renders interactive scores client-side; generated videos are never
persisted as CI artifacts.

## 2. Tech stack and runtime

<!-- Be specific about versions where a mismatch would cause confusion.
     Illustrative example (verify current releases per §6 before
     copying):
       - Language: TypeScript 5.x (strict)
       - Framework: Next.js (App Router)
       - Package manager: pnpm (pinned via package.json)
       - Database: PostgreSQL
       - Runtime target: current Node LTS inside the Dev Container
-->

- Language(s): TypeScript (frontend + GAS), Python 3.11 (pipeline scripts), Bash (CI scripts)
- Framework(s): React 19 + Vite 8 (frontend); Google Apps Script + Clasp (GAS relay)
- Package manager: **pnpm 9.15.9** for `frontend/`; **npm** for `gas/` (clasp needs npm); do not use yarn or bare npm in `frontend/`
- Storage: Cloudflare R2 (ephemeral model fetch + temp video); GitHub Pages (static site)
- Runtime target: Node 20 in the Dev Container and GHA ubuntu-latest runners

All commands in §3 assume you are inside the Dev Container at
`/workspaces/<project-name>`.

## 3. Common commands

<!-- The commands contributors actually run. If a command seems to be
     missing, add it here rather than inventing an ad-hoc invocation. -->

- Install frontend deps: `cd frontend && pnpm install`
- Install GAS deps: `cd gas && npm install`
- Run frontend dev server: `cd frontend && pnpm dev`
- Run tests: _(no test suite yet — add under `tests/` when first test is written)_
- Lint frontend: `cd frontend && pnpm lint`
- Type-check frontend: `cd frontend && pnpm type-check`
- Type-check GAS: `cd gas && npx tsc --noEmit`
- Build frontend: `cd frontend && pnpm build`
- Run pipeline locally (one song): `make SONG=song_001 all`
- Run full local pipeline (all songs, no YouTube): see §3a below
- songs.json is **skip-worktree** (applied by `make setup`, run automatically
  by the Dev Container `postCreateCommand`). Local dev changes are invisible to
  git. To restore the committed base state: `git restore frontend/src/data/songs.json`
- Check documentation invariants: `bash scripts/check-docs.sh`
  (verifies `docs/*/index.md` ↔ filesystem consistency and
  `Last reviewed:` freshness for operator docs; see
  `docs/agent/documentation-policy.md` §3 and §7)

### §3a. Running the full local pipeline (OOM-safe)

NEUTRINO's vocoder accumulates per-phrase audio in RAM.  On the 15 GiB
Dev Container, running multiple songs or variants concurrently causes OOM.

**Rules:**
1. **Never run two NEUTRINO synthesis jobs in parallel.**  Always use a
   sequential loop (song by song, variant by variant).
2. `scripts/02_synthesize.sh` already splits synthesis into per-phrase
   invocations (`-p N` flag).  Do not bypass this by calling `bin/neutrino`
   directly without `-p`.
3. Prefer `make dev-synth-populate` over bare `make synth` so assets are
   copied to the frontend immediately after each variant.

**Full local run (all songs, no YouTube):**
```bash
NEUTRINO_DIR=./neutrino sf3_PATH=./soundfonts/default.sf3
export NEUTRINO_DIR sf3_PATH
for song in yamagata-koto-kouka yamagata-nourin-shoyoka \
            yamagata-shihan-kouka yonezawa-kogyo-kouka; do
  for variant in $(ls projects/$song/variants/); do
    make SONG=$song VARIANT=$variant synth mix video
  done
done
python3 scripts/dev-populate.py
cd frontend && pnpm dev
```

Run `make dev-frontend` in a separate terminal after `dev-populate` if you
want to keep the shell free for further pipeline runs.

### Git workflow

Every change lives on a topic branch and reaches `main` only through a
pull request. Full procedure (branch naming, commit messages, push,
`gh pr create`): see
[`docs/agent/git-workflow.md`](docs/agent/git-workflow.md). At a
glance:

- `git switch -c <type>/<slug>` before editing.
- `git add <path>` (never `-A` / `-a`; denied by policy).
- `git commit -m "<type>: ..."` with a body that explains the *why*.
- `git push -u origin HEAD` on the first push, `git push` afterwards.
- `gh pr create --fill` to open the PR.

The agent does not merge PRs — merging is a human decision.

## 4. Repository layout

<!-- Edit this tree to match what actually exists. As delivered,
     `src/` and `tests/` are placeholders — create them on the first
     real commit, or delete those lines. Per §9, surface any
     inconsistency between this section and the filesystem. -->

```
.
├── .claude/          # Project-level Claude Code settings
├── .devcontainer/    # Dev Container image and VS Code config
├── docs/             # See docs/agent/documentation-policy.md for the full scheme
│   ├── agent/        # Written FOR Claude: playbooks, conventions, traps
│   ├── developer/    # For contributors (how the code works today)
│   ├── operator/     # For people running the system
│   ├── user/         # For end users
│   └── upstream/     # PRDs, design docs, ADRs (the "why" and "what")
├── frontend/         # React + Vite SPA (pnpm)
│   ├── public/       # Static assets deployed to GitHub Pages
│   │   ├── scores/   # MusicXML files (copied by 06_merge_songs.py)
│   │   └── audio/    # MP3 files (copied by 06_merge_songs.py)
│   └── src/
│       ├── components/ # ScoreViewer (OSMD), SongCard
│       ├── data/       # songs.json — generated; do not hand-edit
│       ├── pages/      # HomePage, SongPage
│       └── types/      # Song TypeScript interfaces
├── gas/              # GAS relay (Clasp + TypeScript, npm)
│   ├── src/          # youtube_relay.ts — clasp pushes this directory
│   └── appsscript.json
├── projects/         # Per-song source files
│   └── song_001/     # Example: vocal.musicxml, inst.musicxml, *.json configs
├── scripts/          # Pipeline scripts (Bash + Python); shebang required
└── Makefile          # Local task runner (`make SONG=song_001 all`)
```

## 5. Language policy

All persistent artefacts **must be written in English**: source code
identifiers, code comments, docstrings, commit messages, log messages,
error messages, and every file under `docs/`. Natural-language
conversation with the user may be in any language.

Comments explain *why*, not *what*. The code already shows what.

## 6. Currency of knowledge

Your training data is a snapshot. Libraries, APIs, and conventions
have moved since. Treat everything you "know" about external software
as provisional.

- **Authoritative sources, in order**: (1) what is actually installed
  in this repository (`node_modules/<pkg>/package.json`, the lockfile,
  etc.), (2) the current published release metadata, obtained via a
  local registry command, (3) the user. Your recollection is not on
  this list.
- **Do not invent** versions, flags, or signatures. If you cannot
  verify an API from the sources above, stop and ask (§9 ambiguity).
- **Prefer official generators** over hand-written boilerplate when
  starting a new project or framework artefact (`pnpm create …`,
  `cargo new`, `uv init`, etc.).
- **Version selection is a decision** — pinning a major, choosing LTS
  vs latest, keeping a deprecated API — and warrants an ADR.

For the practical how-to, see
[`docs/agent/verifying-current-practice.md`](docs/agent/verifying-current-practice.md),
[`docs/agent/scaffolding.md`](docs/agent/scaffolding.md), and
[`docs/agent/when-to-write-an-adr.md`](docs/agent/when-to-write-an-adr.md).

## 7. Documentation discipline

Documentation is **part of the work, not a follow-up to it.** A
behaviour change without the corresponding documentation change is
incomplete.

Documentation is split by audience under `docs/`:

| Directory         | Audience                                  |
| ----------------- | ----------------------------------------- |
| `docs/agent/`     | Claude and other coding agents            |
| `docs/developer/` | Contributors writing code in this repo    |
| `docs/operator/`  | People running the system                 |
| `docs/user/`      | End users of the product                  |
| `docs/upstream/`  | PRDs, design docs, ADRs (the "why")       |

For the full policy — when to update which, ADR format, PRD/design-doc
lifecycle, how `docs/upstream/` relates to `docs/developer/` — see
[`docs/agent/documentation-policy.md`](docs/agent/documentation-policy.md).
Read it before making non-trivial changes.

## 8. Definition of done

A change is complete only when **all** of the following hold:

1. Code compiles, type-checks, and lints cleanly.
2. The relevant tests pass locally.
3. New behaviour is covered by at least one new test.
4. Documentation for the affected audience (§7) has been updated.
5. For non-trivial decisions (see
   [`docs/agent/when-to-write-an-adr.md`](docs/agent/when-to-write-an-adr.md)),
   an ADR exists under `docs/upstream/adr/`.
6. `bash scripts/check-docs.sh` passes (exit 0). Warnings are
   acceptable — they surface things worth noticing, such as an
   operator doc approaching the 12-month freshness limit — but
   errors block the change.
7. The work lives on a topic branch, not on `main` / `master`.
8. The commit message explains the *why*, not just the *what*.
9. The branch is pushed and a PR is open (`git push -u origin HEAD`
   then `gh pr create --fill`), with a description linking any
   relevant `docs/upstream/` document.

Any of these missing means the work is a draft.

## 9. Working agreement

**Before writing code.** Read the relevant `docs/upstream/` document if
one exists, then `docs/developer/` and `docs/agent/`. If the request is
ambiguous, surface the ambiguity before editing files.

**Always work on a topic branch.** Before editing any tracked file,
run `git branch --show-current`. If it returns `main` or `master`,
create a topic branch (`git switch -c <type>/<slug>`; see §3)
before doing anything else. `main` is read-only to you; every
change reaches it through a PR. The permission policy is a
backstop, not a licence to relax the discipline.

A request is ambiguous when any of these is true:

- Two or more reasonable interpretations produce materially different
  code.
- The request contradicts an `accepted` document in `docs/upstream/`,
  or an invariant in `docs/developer/`.
- It is unclear how to write a test that proves the change is correct.
- The request assumes a file, command, or convention that does not
  exist in the repository.

When any of these apply, stop and ask.

**While writing code.** Prefer small, reviewable changes. Keep
unrelated refactors out of feature PRs. Write files only under
`/workspaces/<project-name>` (the workspace bind mount); anything
written to `/home/vscode`, `/tmp`, or elsewhere is lost on rebuild.

**Before declaring a change finished.** Re-read the diff as if it were
someone else's PR. Run the full test suite and `scripts/check-docs.sh`.
Verify every item in §8.

**Hard prohibitions:**

- **Never commit to `main` or `master`.** Always work on a topic
  branch (see above and §3). The permission policy blocks switching
  to or pushing `main` / `master`; do not try to work around it.
- Do not commit secrets, tokens, or credentials.
- Do not force-push any branch (policy denies `--force` / `-f`).
- Do not merge your own PR. Merging is a human decision.
- Do not edit `accepted`, `implemented`, or `superseded` documents in
  `docs/upstream/`. Write a new document that supersedes.
- Do not weaken `.claude/settings.json` for convenience. If a rule is
  wrong, change it in a PR with a rationale.
- Do not add a new dependency without noting it in the relevant
  developer doc, and — for significant dependencies — an ADR.

**When stuck.** If the task cannot be completed within these
constraints — information is missing, a tool is unavailable, a rule
here would have to be violated — **stop and say so.** A clearly stated
blocker is more useful than a silently broken change.

## 10. Personal configuration

Project-level `.claude/settings.json` is committed and applies to
everyone. Personal overrides go in `.claude/settings.local.json`
(gitignored). Personal scratch notes do not belong in the workspace;
keep them outside the repo.

(This is the only exception to the "write only under the workspace"
rule in §9: personal scratch, which is never committed and never read
by anyone else, is explicitly not workspace content.)

## 11. When this file is wrong

CLAUDE.md is a living document. If a policy here is outdated,
contradicted by reality, or demonstrably unhelpful, propose a change
to this file in a PR with reasoning — do not silently work around it.

Concrete triggers for proposing a change:

- A rule here says "use X" but the repository no longer uses X.
- A prohibition here prevents a task the team clearly intends to
  enable.
- The same ambiguity (§9) comes up repeatedly because this file does
  not resolve it.
- This file has grown past ~270 lines, or a section is read on
  nearly every turn: extract to `docs/agent/` and leave a pointer.
- `docs/agent/documentation-policy.md` has drifted from the table in
  §7: reconcile in a single PR.

The agent is encouraged to flag such inconsistencies as it notices
them, rather than working around them silently.
