# Documentation policy

This document is the full specification of how this repository treats
documentation. `CLAUDE.md` points here; the detail lives here so it
does not occupy per-turn attention when it is not needed. Read this
file when a task involves creating, updating, or deciding where to
place documentation.

## 1. Audiences and directories

Documentation lives under `docs/`, split by audience:

| Directory          | Audience                             | Examples                                                              |
| ------------------ | ------------------------------------ | --------------------------------------------------------------------- |
| `docs/agent/`      | Claude and other coding agents       | Task playbooks, conventions the agent should follow, test recipes     |
| `docs/developer/`  | People writing code in this repo     | Architecture, module guides, how-to-add-a-new-X, debugging tips       |
| `docs/operator/`   | People running the system            | Deployment, configuration, runbooks, on-call procedures               |
| `docs/user/`       | End users of the product             | Feature guides, tutorials, API reference                              |
| `docs/upstream/`   | Anyone deciding *what* to build      | PRDs, design docs, ADRs                                               |

Each directory must contain an `index.md` listing its contents with
one-line summaries. The indices are the navigation surface of the
documentation; they are updated in the same PR as any content change,
and this is enforced by `scripts/check-docs.sh` (see §7).

## 2. When to update which

The rule, by change type:

- Changing an internal module, function signature, or invariant
  → update `docs/developer/`, and `docs/agent/` if the agent relied
  on the old behaviour.
- Changing how the system is deployed, configured, monitored, or
  recovered → update `docs/operator/`.
- Changing externally visible behaviour → update `docs/user/`.
- Making a non-trivial design decision → add an ADR under
  `docs/upstream/adr/` (see §4).
- Adding a workflow the agent will perform repeatedly → add a
  playbook under `docs/agent/`.

For the distinction between `docs/upstream/` and `docs/developer/` in
particular, see §5.2.

## 3. What good documentation looks like here

- **Current, not aspirational.** If a feature does not exist yet, it
  is not documented as if it does. Plans live in `docs/upstream/`.
- **Task-shaped, not topic-shaped.** Prefer "How to add a new
  migration" over "About migrations".
- **Short.** Link out rather than duplicate. A 100-line document that
  is read is better than a 1000-line one that is skimmed.
- **Dated when it matters.** Every file under `docs/operator/` must
  carry a footer of the form `Last reviewed: YYYY-MM-DD`. A runbook
  or operator document is considered stale once it has not been
  reviewed for **6 months**; `scripts/check-docs.sh` warns at 6
  months and fails at 12 months. Revisit, update if needed, and bump
  the date — the date is a claim that the content was verified
  against reality on that day, not a claim that the file was
  touched.

Other audiences (`developer/`, `user/`, `upstream/`, `agent/`) do not
require date footers: developer docs are validated by the test
suite, user docs by customer feedback, upstream docs are immutable
after acceptance (§5.1), and agent playbooks are validated by the
agent's results.

## 4. Architecture Decision Records (ADRs)

Non-trivial decisions are recorded as ADRs under
`docs/upstream/adr/NNNN-short-title.md`, where `NNNN` is a zero-padded
sequence number. Each ADR follows this shape:

```markdown
---
status: accepted            # proposed | accepted | superseded
date: YYYY-MM-DD
authors: [handle-1, handle-2]
supersedes: []
superseded-by: null
---

# ADR NNNN: <Title>

## Context
<What is the situation? What forces are at play?>

## Decision
<What did we decide?>

## Consequences
<What becomes easier? What becomes harder? What remains open?>
```

`authors` is redundant with `git blame` inside the repository, but
ADRs are sometimes shared outside — in reviews, in onboarding, in
external design discussions — where the blame view is not available.
The front matter keeps the attribution self-contained.

ADRs are immutable once accepted. If a decision is revisited, write a
new ADR that supersedes the old one; do not edit the old one in place
except to update its `superseded-by` pointer.

### 4.1 Number collisions across branches

Since ADRs (and PRDs, design docs) are numbered sequentially in a
shared directory, two concurrent branches may independently claim
the same number. The rule:

- **At PR review time**, if the branch's highest-numbered new
  document collides with one already on the main branch, the PR
  author renumbers their document upward during rebase and updates
  any inbound references (commit messages, other ADRs with
  `supersedes`/`superseded-by` pointers) in the same rebase.
- **Numbers are for ordering, not identity.** An ADR's identity is
  its slug and content; renumbering during review is a routine
  fix-up, not a correction.
- **When in doubt, take the next free number.** The cost of
  renumbering is low; the cost of a silent collision (two documents
  with the same number in history) is higher.

## 5. Upstream documents (PRDs, design docs, RFCs)

Upstream documents — those that describe *what* and *why* before the
*how* — live in `docs/upstream/`:

```
docs/upstream/
├── index.md               # Table of contents with status for each document
├── prd/                   # Product requirements documents
│   └── NNNN-<slug>.md
├── design/                # Technical design documents / RFCs
│   └── NNNN-<slug>.md
└── adr/                   # Architecture decision records (see §4)
    └── NNNN-<slug>.md
```

These are **in-repo, versioned artefacts**, not entries in an external
wiki or ticketing system. The reasoning:

1. Every change to a requirement or design is a reviewable diff with
   an author, a date, and a discussion history.
2. The state of the project's intent at any past commit is
   recoverable via `git log -- docs/upstream/`.
3. An agent working in this repository can read the upstream
   documents without needing access to an external system.
4. Pull requests that implement a PRD or design doc naturally
   reference it by relative path, creating a permanent link from the
   code back to its rationale.

### 5.1 Lifecycle

Each PRD or design document carries a status in its front matter:

- `draft` — being written; not a source of truth yet.
- `in-review` — under team review; do not build against it.
- `accepted` — the team has committed to it; implementation may
  reference it.
- `implemented` — the code reflects it. The document stays as
  historical context and is not edited except to record supersession.
- `superseded` — replaced by a newer document; link forward via
  `superseded-by`.

Do not edit `accepted`, `implemented`, or `superseded` documents in
place to reflect new thinking. Write a new document that supersedes
the old one.

### 5.2 `docs/upstream/` vs `docs/developer/`

This is the decision that drives the "what goes where" rule in §2:

- `docs/upstream/` answers "what should exist, and why did we decide
  to build it this way?" — the shape of the target.
- `docs/developer/` answers "how does the code that exists today
  actually work?" — the shape of reality.

When the two agree, the project is on plan. When they drift,
`docs/upstream/` preserves past intent while `docs/developer/` is the
authority on the present. Drift itself is useful signal; it should be
visible rather than hidden.

### 5.3 How the agent interacts with upstream documents

When implementing a non-trivial feature, the agent should:

1. Check whether `docs/upstream/` contains a relevant PRD or design
   doc, and read it first if so.
2. Cite the document's path in the commit message and PR description.
3. If the implementation covers the document in full, update the
   document's `status` to `implemented` in the same PR.
4. Open or update a corresponding section in `docs/developer/` that
   describes the resulting reality of the code.

## 6. Documentation for the agent (`docs/agent/`)

Files under `docs/agent/` are written with Claude (and similar agents)
as the primary reader. They should:

- Be written as *instructions*, not prose essays.
- State assumptions the agent may make without re-checking.
- Point to the exact commands, file paths, and conventions to use.
- Call out the traps — things that look right but have been wrong
  before.

`CLAUDE.md` itself is the index of `docs/agent/`: it carries only what
must be resident in context on every turn. Anything that can be read
on demand belongs here, not there.

## 7. Mechanical enforcement (`scripts/check-docs.sh`)

The policies above are mostly norms, but two of them are mechanical
enough to be checked by a script: `scripts/check-docs.sh` is wired
into the Definition of Done (CLAUDE.md §8) and fails the check if:

1. Any directory under `docs/` contains files that are not listed in
   its `index.md`, or lists files that do not exist. For this check
   the script parses inline markdown links of the form
   `[text](path.md)` or `[text](path.md "title")` in the index —
   write your indices in that form. Reference-style links and HTML
   anchors are not recognised; if you need them, extend the script.
2. Any `.md` file under `docs/operator/` is missing a
   `Last reviewed: YYYY-MM-DD` footer, or the date is more than 12
   months old. A date between 6 and 12 months old produces a
   warning. (Months are counted as 30 days; calendar drift of a
   few days over a year is immaterial for runbook freshness.)

The script is deliberately small. If you extend it, keep it that way:
bash, no runtime dependencies, readable end-to-end in one screen. It
exists to turn policy into a reflex, not to become its own system.

The same check runs in CI via `.github/workflows/docs.yml` on every
pull request, so a missed local run is caught before merge. The local
run still matters as the fast feedback loop — waiting on CI to
discover that an index is out of date is avoidable.

## 8. File placement rules

- Persistent project artefacts live under the workspace bind mount,
  `/workspaces/<project-name>`. Anything written elsewhere (for
  example `/home/vscode`, `/tmp`) is lost when the container is
  rebuilt.
- Source code goes under `src/` or the language-appropriate
  equivalent.
- Tests go under `tests/` and mirror the structure of the source.
- Scripts intended to be run by humans go under `scripts/` with a
  shebang line and a one-line comment describing what they do.
- Generated artefacts (build output, coverage reports) are gitignored
  and never committed.
