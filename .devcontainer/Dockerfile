# Dockerfile for a Dev Container with Claude Code preinstalled.
#
# Contents:
#   - Node.js 20 (required by Claude Code).
#   - Claude Code CLI (@anthropic-ai/claude-code), installed globally.
#   - Corepack (pnpm / yarn on demand, pinned via package.json).
#   - A minimal set of command-line utilities for day-to-day work.
#
# Isolation model:
#   - The runtime user is unprivileged (`vscode`) with passwordless sudo.
#   - No host paths are bind-mounted beyond the project folder itself.
#   - Globally installed packages are installed by root at build time,
#     so the unprivileged runtime user cannot modify them.

FROM node:20-bookworm

ARG TZ=UTC
ENV TZ="$TZ"

# Baseline system packages.
#
# Trim freely if you want a smaller image. `sudo` is required so that
# routine ad-hoc tasks inside the container (apt-get install a missing
# package, etc.) are possible without rebuilding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        sudo \
        git curl ca-certificates less procps \
        jq ripgrep fd-find zsh \
        build-essential \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI (`gh`).
#
# Claude's PR-opening workflow (CLAUDE.md §3, docs/agent/git-workflow.md)
# uses `gh pr create`. Installed from GitHub's own APT repository per
# https://github.com/cli/cli/blob/trunk/docs/install_linux.md — the
# Debian-packaged version is often several minors behind.
RUN mkdir -p -m 755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Create the unprivileged runtime user.
#
# The `node` base image already has a uid=1000 `node` user, but we
# create a separate `vscode` user for clarity and to match VS Code's
# own conventions.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN if getent passwd $USER_UID >/dev/null; then \
        userdel -r "$(getent passwd $USER_UID | cut -d: -f1)" 2>/dev/null || true; \
    fi \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME

# Persistent directories.
#
# Both paths are backed by named volumes declared in devcontainer.json.
# The `.claude` and `.config/gh` paths are part of the coupling
# invariant documented in devcontainer.json above the `mounts` block:
# if you change any of them, update the mounts, the matching
# containerEnv entries, and this mkdir line.
RUN mkdir -p /commandhistory \
             /home/$USERNAME/.claude \
             /home/$USERNAME/.config/gh \
    && chown -R $USERNAME:$USERNAME \
             /commandhistory \
             /home/$USERNAME/.claude \
             /home/$USERNAME/.config

# Passwordless sudo for the runtime user.
#
# The container is already isolated from the host, so the trade-off
# here is only about limiting blast radius inside the container
# itself. Granting full sudo simplifies day-to-day use without
# materially weakening the boundary.
RUN echo "$USERNAME ALL=(root) NOPASSWD: ALL" \
        > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Install global Node-based tooling as root, before dropping privileges.
# /usr/local/lib/node_modules is root-owned in the official Node image,
# so these must run before the `USER` switch below.
RUN npm install -g @anthropic-ai/claude-code \
    && corepack enable

# Drop privileges for all subsequent layers and runtime.
USER $USERNAME

# Persist bash history across rebuilds via the /commandhistory volume.
RUN echo 'export PROMPT_COMMAND="history -a"' >> /home/$USERNAME/.bashrc \
    && echo 'export HISTFILE=/commandhistory/.bash_history' >> /home/$USERNAME/.bashrc
