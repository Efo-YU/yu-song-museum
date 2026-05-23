# How to start a new feature

A default workflow for implementing a feature in this repository.
Deviate when there is reason to; use this as the starting shape when
there is not.

## 1. Understand the ask

- Restate the feature in one or two sentences in your own words. If
  you cannot, the request is too ambiguous to start (CLAUDE.md §9).
- Look for an existing PRD or design doc under `docs/upstream/`. If
  one exists and its status is `accepted`, read it first; it is the
  source of truth for scope and intent.
- If no upstream document exists and the feature is non-trivial —
  changes user-visible behaviour, touches multiple modules, or
  introduces a new concept — draft a short PRD or design doc
  *before* writing code. See `docs/agent/documentation-policy.md` §5.

## 2. Plan the change

- Locate the modules that will be touched.
- Decide the test that will demonstrate the feature works.
  If no such test is writable, the feature is not yet specified well
  enough to implement (CLAUDE.md §9 ambiguity trigger).
- Decide whether the plan involves a non-trivial decision that
  deserves an ADR
  (see [`when-to-write-an-adr.md`](when-to-write-an-adr.md)).
- **Create the topic branch before editing any file.** Run
  `git branch --show-current`; if it shows `main` or `master`, branch
  first:

  ```sh
  git fetch origin
  git switch -c <type>/<slug> origin/main
  ```

  where `<type>` is one of `feat`, `fix`, `refactor`, `docs`, `chore`,
  `test`. See [`git-workflow.md`](git-workflow.md) for the full
  branching convention and recovery procedures.

## 3. Implement

- If the change means starting a new project, creating a new package,
  or adding a framework-specific artefact, use the official generator
  rather than hand-writing boilerplate
  ([`scaffolding.md`](scaffolding.md)).
- Before calling into a library API, confirm the shape against the
  version actually installed
  ([`verifying-current-practice.md`](verifying-current-practice.md)).
  Do not write from memory; do not guess.
- Write the test first when feasible, or at least alongside the
  change. "New behaviour is covered by at least one new test" is in
  the definition of done (CLAUDE.md §8).
- Keep unrelated refactors out of this change. If you notice
  something that wants cleaning up, open a separate issue or a
  separate PR.
- Write files only under `/workspaces/<project-name>`. Anything
  elsewhere is lost on rebuild.

## 4. Document alongside the code

Update documentation for every audience the change affects:

- Internal structure or invariant changed → `docs/developer/`.
- Deployment / runtime / operation changed → `docs/operator/`
  (remember the `Last reviewed:` footer).
- User-visible behaviour changed → `docs/user/`.
- An implemented PRD or design doc → flip its `status` to
  `implemented` in the same PR.
- A non-trivial decision → add an ADR.
- A recurring pattern the agent will repeat → consider a new
  `docs/agent/*.md` playbook.

## 5. Before declaring done

- Run the full test suite.
- Run `bash scripts/check-docs.sh`.
- Re-read the diff as if reviewing someone else's PR.
- Verify every item in CLAUDE.md §8.
- Commit with a message that explains the *why*, not just the *what*.

## 6. Push and open the PR

- First push of the branch:
  ```sh
  git push -u origin HEAD
  ```
- Open the pull request:
  ```sh
  gh pr create --fill
  ```
  `--fill` uses the commit messages as the PR description. If the
  change is substantial, write a custom body that links to the
  relevant `docs/upstream/` document and summarises the diff — see
  [`git-workflow.md`](git-workflow.md) for the template.
- Check CI status:
  ```sh
  gh pr checks
  ```
  If anything fails, push fixes as additional commits to the same
  branch. Do not force-push (policy denies `--force`), and do not
  merge your own PR — merging is a human decision.
