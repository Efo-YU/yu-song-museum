# Git workflow

CLAUDE.md §3 summarises the git workflow; this file is the full
procedure, including edge cases, commit-message conventions, and how
to recover when something has gone sideways.

## The invariant

Every change reaches `main` (or `master`, if the project uses that
name) through a pull request. You do not commit to `main` directly,
ever. This is enforced by `.claude/settings.json` and, ideally, by a
GitHub branch-protection rule on the remote (see README "Getting
started"). The discipline exists because:

- A PR creates a reviewable diff and a discussion record for every
  change.
- A protected `main` means reverting to a known-good state is a
  `git checkout main` away, even when a topic branch has gone wrong.
- An agent working autonomously is much less dangerous when the
  worst it can do is produce a branch you can ignore.

## Branch naming

`<type>/<kebab-case-slug>`, where `<type>` is one of:

| Type       | Use                                                       |
| ---------- | --------------------------------------------------------- |
| `feat`     | New user-facing feature or capability                     |
| `fix`      | Bug fix                                                   |
| `refactor` | Change the shape of the code without changing behaviour   |
| `docs`     | Documentation only                                        |
| `chore`    | Build, tooling, dependency bumps, routine housekeeping    |
| `test`     | Add or improve tests                                      |

The slug is specific and short. `feat/login-form` is good;
`feat/stuff` is not. Avoid personal identifiers in the branch name —
this is a work branch, not your branch.

## Starting a change

```sh
# Confirm where you are and fetch the latest main.
git branch --show-current
git fetch origin
# Do NOT run `git switch main` to pull — that is denied by policy,
# and you do not need to be on main to branch from it. Instead:
git switch -c feat/login-form origin/main
```

That last command creates a new branch from the current origin/main
without switching to main at any point. It is the canonical way to
start a fresh piece of work.

If you are already on a topic branch and want to start something
unrelated, commit or stash first, then branch from `origin/main`
again:

```sh
git stash
git switch -c fix/null-check origin/main
```

## Committing

Stage files by explicit path:

```sh
git add src/auth/login.ts src/auth/login.test.ts
git diff --staged        # review what you are about to commit
git commit -m "feat: add login form with CSRF token"
```

`git add -A` / `git add --all` are denied by policy so that the
working set of a commit stays visible. Likewise `git commit -a`.

### Commit message shape

```
<type>: <imperative summary, <=72 chars>

<body: why this change. what alternatives were considered and
 rejected. what this change does NOT do. issue links.>

<optional trailers>
```

A one-line commit message is fine for truly trivial changes (typo
fixes, formatting). Anything behaviour-changing gets a body. The
body answers "why", not "what" — the diff already says what.

### Atomic commits

Each commit should be a coherent unit that could be reverted in
isolation. If a change is mid-way through a refactor and the commit
does not compile or test-pass on its own, either finish the work
first, or squash before opening the PR.

## Pushing

First push of a branch:

```sh
git push -u origin HEAD
```

This sets the upstream; subsequent pushes are just:

```sh
git push
```

Pushing `main` / `master` directly is denied by policy, including
via refspecs like `git push origin HEAD:main`.

## Opening a pull request

```sh
gh pr create --fill
```

`--fill` uses the branch's commit messages (title from the first
commit, body concatenated) as the PR description. This is usually
what you want if the commit messages are good. If you need to write
a custom description:

```sh
gh pr create --title "feat: add login form" \
    --body "$(cat <<'EOF'
## What
Adds a login form at /login that posts to /api/auth/login.

## Why
Implements docs/upstream/prd/0003-authentication.md.

## Notes for reviewers
- The CSRF token handling follows the pattern in docs/developer/auth.md.
- Rate limiting is intentionally out of scope; tracked as
  docs/upstream/prd/0003-authentication.md §"Future work".
EOF
)"
```

Reference any relevant `docs/upstream/` document explicitly. A
reviewer should be able to open the PR and find the "why" without
asking.

## During review

- Address feedback by pushing additional commits to the same branch.
  Do not force-push; the policy denies `--force` / `-f` to prevent
  history loss during review.
- If the branch falls behind `main` and needs updating, rebase
  locally (`git rebase origin/main`) and push with
  `--force-with-lease` only if your team has explicitly decided
  force-pushing during review is acceptable. If in doubt, merge
  `main` into your branch instead.

## Merging

**Not your job.** A human decides when a PR is ready to merge and
clicks the button. The agent's job ends at "PR is open, tests are
green, reviewer has been notified".

## Recovery

### "I accidentally committed to main"

You shouldn't be able to — the policy denies `git switch main` and
`git checkout main`. If you somehow arrived on `main` via a
pre-existing session state:

```sh
git branch --show-current   # confirm you are on main
git log --oneline -5        # see what you have committed

# Move the commits to a topic branch so main can be reset.
git switch -c feat/recover-work
# At this point main's tip still points at your accidental commits.
# Resetting main to its correct upstream state requires being on
# main, which the policy denies. Stop here and ask a human to run
# `git fetch origin && git switch main && git reset --hard origin/main`
# locally for you.
```

Stop and ask a human. Do not try to work around the denial.

### "My PR is on the wrong base"

If you branched from something other than `origin/main`:

```sh
git rebase --onto origin/main <wrong-base> HEAD
git push --force-with-lease     # only after the team has agreed
                                # — and only on unshared branches
```

If `--force-with-lease` is denied or if the branch is shared,
coordinate with a human instead.
