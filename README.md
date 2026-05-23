# Claude Code in a Dev Container

A VS Code [Dev Container](https://containers.dev/) template for
projects that use [Claude Code](https://www.anthropic.com/claude-code).
Open the repository in VS Code, *Reopen in Container*, and you have a
disposable Linux sandbox with Claude Code (CLI + extension)
preinstalled and ready to use.

## What this template believes

This is not "a Dev Container with Claude Code installed in it". It is
an opinionated starting point for building software *with* an agent,
and the opinions are worth stating up front so you can decide whether
they match yours:

- **Your training data is a snapshot; the repository is the ground
  truth.** Libraries, APIs, and conventions move faster than any
  model's training cutoff. The template tells the agent (in
  `CLAUDE.md` §6) to treat its own recollection as provisional and
  to prefer installed source, lockfiles, and registry queries over
  memory. Official scaffolders (`pnpm create …`, `cargo new`,
  `uv init`) are preferred over hand-written boilerplate for the
  same reason.
- **Documentation is part of the work, not a follow-up to it.** A
  behaviour change without the corresponding documentation change is
  not finished. Documentation is split by audience (`docs/agent/`,
  `docs/developer/`, `docs/operator/`, `docs/user/`,
  `docs/upstream/`) so that each reader finds what is aimed at them
  without wading through the rest.
- **Norms are backed by mechanisms where practical.** A rule that
  lives only in prose is a rule that rots. The index-consistency and
  operator-doc freshness norms are enforced by `scripts/check-docs.sh`,
  which is part of the Definition of Done. The rest stay as norms
  deliberately: the script is small and readable, not a new system
  to maintain.
- **`CLAUDE.md` is an index, not a manual.** Every line there
  competes for the model's attention on every turn. Detail lives in
  `docs/agent/`, loaded on demand. The file budgets itself (~250
  lines) and flags its own drift for refactoring.
- **Isolation is containment, not a hard wall.** The Dev Container
  contains routine accidents — a bad `rm`, a misbehaving install
  script, an overenthusiastic agent — and keeps host credentials out
  of reach. It is not a boundary against a kernel-level attacker.
  For that, use a microVM or a disposable cloud VM instead.

If any of these feel wrong for your project, either fork and adapt,
or look for a different starting point. The template is small enough
to fork usefully.

## Layout

```
.
├── .devcontainer/
│   ├── devcontainer.json   # VS Code Dev Containers configuration
│   └── Dockerfile          # Base image with Claude Code preinstalled
├── .claude/
│   └── settings.json       # Shared permission policy for Claude Code
├── .github/
│   └── workflows/
│       └── docs.yml        # CI: run check-docs.sh on every PR
├── docs/
│   ├── agent/              # Written FOR Claude: playbooks, conventions, traps
│   ├── developer/          # For contributors (how the code works today)
│   ├── operator/           # For people running the system
│   ├── user/               # For end users
│   └── upstream/           # PRDs, design docs, ADRs
├── scripts/
│   └── check-docs.sh       # Index consistency + operator-doc freshness
├── CLAUDE.md               # Project operating manual loaded on every turn
├── README.md
└── .gitignore
```

Each directory under `docs/` ships with a skeleton `index.md` so that
`bash scripts/check-docs.sh` passes on first run. The CI workflow
under `.github/workflows/docs.yml` runs the same check on pull
requests; contributors should still run it locally before pushing,
but the CI is the backstop.

## Prerequisites

- **Docker.** Docker Desktop, [OrbStack](https://orbstack.dev/), or
  Docker Engine on Linux/WSL2 all work.
- **VS Code** with the
  [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
  extension.

The host does not need Node.js, the `claude` CLI, or the `gh` GitHub
CLI. All three live inside the container.

## Getting started

1. Create a new repository from this template (GitHub's *"Use this
   template"* button), or copy the files into an existing project.
2. Open the project folder in VS Code.
3. From the command palette (`F1` or `Ctrl`/`Cmd`+`Shift`+`P`), run
   **Dev Containers: Reopen in Container**.
4. Wait for the initial image build. Subsequent opens use the cached
   image and are fast.
5. Open a terminal inside the container (you land in
   `/workspaces/<project-name>`) and run:

   ```sh
   claude
   ```

   Authenticate once. Credentials are stored in a named volume scoped
   to this project and persist across container rebuilds, so this is a
   one-time step.
6. Fill in `CLAUDE.md` with the project's actual context. Accurate,
   specific notes here make Claude noticeably more useful.
7. Authenticate the GitHub CLI so Claude can open pull requests:

   ```sh
   gh auth login
   ```

   Choose HTTPS, authenticate with a browser, and grant the `repo`
   scope. `gh` stores its state under `~/.config/gh`, which is
   mounted as a project-scoped named volume, so credentials
   persist across rebuilds — this is also a one-time step per
   project.
8. **Enable branch protection on `main`.** On the repository's
   GitHub page, go to *Settings → Branches → Add branch protection
   rule* for `main` and enable at least:
   - Require a pull request before merging
   - Require status checks to pass before merging (select the `docs`
     workflow once it has run once, and any other CI you add)
   - Restrict who can push to matching branches (include yourself if
     you want a hard stop)

   The `.claude/settings.json` in this repository already denies
   Claude from switching to or pushing `main` / `master` as a
   first line of defence. Branch protection is the second line,
   enforced server-side, that catches both human mistakes and any
   agent that has somehow escaped the local policy.

## The git workflow in this repository

Every change reaches `main` through a pull request. The agent never
commits to `main` directly; it creates a topic branch
(`<type>/<slug>`), commits, pushes (`git push -u origin HEAD`), and
opens the PR with `gh pr create --fill`. A human reviews and merges.

This is enforced at three layers, weakest to strongest:

1. **Norm.** `CLAUDE.md` §9 states the rule in prose and points at
   `docs/agent/git-workflow.md` for the full procedure.
2. **Local policy.** `.claude/settings.json` denies
   `git switch main`, `git checkout main`, `git push origin main`,
   `git push --force`, and variants. An agent would have to
   deliberately bypass the policy to commit to main.
3. **Server policy.** GitHub branch protection (step 8 above)
   rejects direct pushes to `main` at the remote even if a client
   sends them.

If any one layer fails, the others still hold. If all three fail
simultaneously, the answer is not to tighten this template further
but to stop using a coding agent on that repository until the
operational discipline is fixed.

## What isolation you get

- Only your project directory is bind-mounted into the container.
  Nothing else on the host is reachable.
- The container runs as an unprivileged `vscode` user. Root inside the
  container is not root on the host.
- No Docker socket is mounted. The container cannot control the host's
  Docker daemon or spawn sibling containers.
- Host credentials (SSH keys, cloud tokens, browser cookies) are not
  visible from inside the container.
- Rebuilding the container restores a known-good state. If something
  becomes wedged or suspicious, rebuild.

This is sufficient to contain routine accidents and keep sensitive
host state out of reach. It is not a strong boundary against a
motivated attacker with a kernel exploit. For that level of
isolation, run the workload in a microVM or a disposable cloud VM.

### What this template does *not* try to do

Earlier iterations of this template enforced a network egress
allowlist via iptables/ipset. It was dropped because the maintenance
burden outweighed the benefit in practice: CDN IPs rotate, the VS
Code Marketplace uses per-extension subdomains, and useful SaaS
endpoints change frequently. If you need strict egress control for a
specific, high-risk workflow, handle that as a separate concern with a
narrower sandbox.

## The permission policy

`.claude/settings.json` is Claude Code's permission policy for this
project, checked into version control and shared with everyone who
opens the repo. The defaults allow routine read/edit and common dev
commands, while blocking a handful of operations that tend to be
regretted (recursive deletes, force-pushes, unreviewed web fetches).
Adjust to match your project's tooling.

Personal, machine-specific overrides belong in
`.claude/settings.local.json`, which is gitignored.

## Customization

### Add languages or tools

Edit `.devcontainer/Dockerfile`. Add `apt-get install` entries or
language-runtime installers before the `USER $USERNAME` line so they
end up owned by root.

```dockerfile
# Python
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Go — replace GOVERSION with the current release checked via
# `go version` at https://go.dev/dl/, or install via the distro.
# Hardcoding a version here ages poorly; follow CLAUDE.md §6.
RUN GOVERSION=1.23.4 \
    && curl -fsSL https://go.dev/dl/go${GOVERSION}.linux-amd64.tar.gz \
    | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

# Rust — install as the unprivileged user, after `USER $USERNAME`.
```

### Pin a specific pnpm or yarn version

Corepack is enabled, so add a `packageManager` field to your
`package.json` and Corepack will fetch and use the pinned version on
demand:

```json
{
  "packageManager": "pnpm@9.15.0"
}
```

### DNS

The container is launched with `--dns=1.1.1.1 --dns=8.8.8.8`. This
avoids a common failure mode where the container inherits a resolver
address (via `/etc/resolv.conf`) that is not reachable from the
container's network namespace — typical on WSL2 behind a home router,
inside a Tailscale tailnet, or on some corporate networks.

Replace those flags in `devcontainer.json` with your own resolver if
you need to resolve private hostnames.

## Troubleshooting

### Claude Code or `gh` prompts for authentication on every rebuild

Verify that the project-scoped named volumes are present and have not
been manually deleted:

```sh
docker volume ls | grep -E 'claude-config|gh-config'
```

You should see both `<project>-claude-config` and `<project>-gh-config`.
If either is missing, it was deleted; re-authenticate inside the
container (`claude` or `gh auth login`) and the volume will be
recreated.

### "My files disappeared after rebuild"

Check the path. The bind mount target is
`/workspaces/<project-name>`. Files created elsewhere (e.g. in
`/home/vscode`, `/tmp`) live in the container's writable layer and
are lost on rebuild.

To recover: *before* rebuilding, enter the old container and copy the
files into the bind-mount path:

```sh
cp -r /home/vscode/somewhere /workspaces/<project-name>/
```

Then commit.

### `EACCES` when installing a global npm package during build

The Dockerfile installs anything global as root, before the `USER`
switch. If you add your own `npm install -g` lines, make sure they
appear above `USER $USERNAME`.

### DNS timeouts or long hangs

Inside the container, verify that DNS works:

```sh
cat /etc/resolv.conf
getent hosts api.anthropic.com
```

If the second command prints nothing, your host's default resolver
is not reachable from the container. The template pins `1.1.1.1`
and `8.8.8.8`, which covers most cases; if you need a different
resolver, edit the `--dns=...` flags in `devcontainer.json`.

(`dig` is not in the default image; install `dnsutils` with `sudo
apt-get install -y dnsutils` if you want richer diagnostics.)

## License

TODO: Choose a license (e.g. MIT, Apache-2.0, or 0BSD) before
publishing this template.
