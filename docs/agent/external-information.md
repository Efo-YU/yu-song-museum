# External information

`.claude/settings.json` denies `WebFetch` by default. This is
deliberate: agent-initiated network fetches are a frequent source of
confusion (stale content, hallucinated URLs, injected instructions
from third-party pages) and rarely necessary for code changes in a
well-scoped repository.

## What to do when you want to reach the web

**When the answer is in the repository.** Read the relevant
documentation under `docs/`, or search the code. Nearly every
"how do we do X here?" question is answerable locally.

**When the answer is about a dependency.** Read the installed
package's source under the repository's dependency directory
(`node_modules/`, `vendor/`, your language's equivalent), or its
vendored docs. The exact version in use is right there; the web
version may drift.

**When external information is genuinely required.** Stop and say
so. Ask the human for the specific page, quote, or fact you need,
and let them paste it into the conversation. This is faster than
guessing and keeps the session auditable.

## Do not guess

`WebFetch` being denied is **not** a licence to fill the gap from
your training data. "I cannot look it up, so I will write what I
remember" is a worse failure mode than a WebFetch call would have
been, because the guess blends in with the rest of the output and
silently becomes part of the repository.

If you do not know something and cannot verify it from:

- the repository's own files,
- the installed dependencies (see
  [`verifying-current-practice.md`](verifying-current-practice.md)),
- or a registry query that a local tool can perform,

then say so. "I do not know the current signature of `X.foo` and I
cannot verify it from `node_modules/`; can you confirm it or paste
the docs?" is the correct response. A plausible-looking fabrication
is not.

## Why not just relax the policy?

A blanket `WebFetch` allow opens the door to prompt injection from
any page the agent visits, including pages linked by the user with
good intent. Keeping it denied by default and negotiating access
per-session — via a human paste rather than a tool call — is a
simpler boundary than trying to enumerate safe domains. The project
has chosen that trade-off (CLAUDE.md §9: "Do not weaken
`.claude/settings.json` for convenience").
