# Verifying current practice

CLAUDE.md §6 requires that you treat your training data as provisional
and use authoritative sources when choosing libraries, APIs, or
version numbers. `WebFetch` is denied by policy (see
[`external-information.md`](external-information.md)), so this file
documents how to verify currency without direct network access.

## Order of authority

When in doubt about the shape of a library, the name of a function,
or which version is appropriate:

1. **What is already installed here.** The lockfile and the
   dependency directory are the ground truth for this repository's
   reality right now.
2. **What the registry currently publishes.** Reachable with a
   single local command per ecosystem (§ below).
3. **The user.** Ask for the page, release notes, or documentation
   you need. A brief paste is faster and more reliable than a
   guess.

Your recollection is not on this list. If you wrote code from memory
and you cannot confirm the API against one of the three above, treat
the code as speculative and flag it.

## Reading installed versions

### Node / JavaScript / TypeScript

```sh
# Version of a specific installed package
cat node_modules/<pkg>/package.json | jq -r .version

# The exact declared + resolved versions for everything
cat pnpm-lock.yaml      # or package-lock.json, yarn.lock

# What this project declares as a direct dependency
cat package.json | jq '.dependencies, .devDependencies'
```

### Python

```sh
# What is installed, with versions
pip list --format=freeze            # or: uv pip list

# Where a package is on disk (its __init__.py for reading APIs)
python -c 'import <pkg>; print(<pkg>.__file__)'

# Declared dependencies
cat pyproject.toml              # modern projects
cat requirements*.txt           # older projects
```

### Rust

```sh
cargo tree -p <pkg>             # full version tree
cat Cargo.lock | grep -A1 '<pkg>'
cat Cargo.toml                  # declared deps
```

### Go

```sh
go list -m all                  # all module versions in use
cat go.mod                      # declared deps
```

### Reading installed source

Once you know the version, read the package's own source for API
shape. It is on disk under `node_modules/`, the Python site-packages
directory (see `python -c 'import <pkg>; print(<pkg>.__file__)'`),
`~/.cargo/registry/src/` for Rust, or `$GOMODCACHE` for Go. The
installed source is the authority: it is what the code you write will
actually run against.

## Querying the registry

These commands hit the public registry but do not do `WebFetch` — they
go through the language-specific tool, which is permitted.

```sh
# Latest stable version of an npm package
pnpm view <pkg> version
pnpm view <pkg> versions --json          # full history

# Latest version of a PyPI package
pip index versions <pkg>                 # newer pip
uv pip install --dry-run '<pkg>==9999'   # lists available as an error

# Latest version of a crate
cargo search <pkg>

# Latest version of a Go module
go list -m -versions <module>
```

If a package manager command reports a version you were not expecting
— newer or older than your memory — **trust the command**. That is
what will be installed.

## When you still cannot tell

If, after consulting installed source and registry metadata, you are
still unsure:

- Whether an API signature changed between two versions, or
- Whether a convention is current (e.g. "is the `App Router` still
  the recommended pattern in Next.js?"), or
- Which of several plausible APIs to use,

**ask the user.** A useful shape:

> I want to use `<thing>` here. My training data says the API is
> `<shape A>`, but the installed version is `X.Y.Z` and I cannot
> verify from `node_modules/` alone whether that is still current.
> Could you confirm the signature, or paste the relevant page of the
> docs?

This is cheaper than writing plausible-looking broken code and
discovering the mismatch at runtime or in review.
