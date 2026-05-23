# When to write an ADR

CLAUDE.md §8 requires an ADR for "non-trivial decisions", and `docs/agent/documentation-policy.md` §4 defines the format. This playbook resolves the ambiguity: what counts as a decision that deserves an ADR?

## Write an ADR when any of these apply

- **A dependency is added, removed, or replaced.** This includes new
  direct dependencies, version-pinning a transitive dependency,
  vendoring, and forking an upstream package. "We're using X for Y"
  is always a decision.
- **A version selection is non-obvious.** Pinning to a specific major
  version when newer ones exist, choosing LTS over latest (or vice
  versa), staying on a deprecated API intentionally, or skipping a
  release for a known reason. The *currency-of-knowledge* constraint
  (CLAUDE.md §6) means these choices get made often; record the
  reasoning so the next contributor does not have to guess.
- **A public interface changes in a non-backwards-compatible way.**
  Breaking a function signature, wire protocol, database schema, or
  CLI flag contract that external code depends on.
- **A recurring operational cost is introduced.** A new service the
  team has to run, a new metric that must be monitored, a new backup
  policy, a new secret to rotate.
- **A convention is established that future contributors should follow
  without rediscovering why.** "Our repository uses `pnpm`", "we
  prefer composition over inheritance in X layer", "timestamps are
  stored in UTC".
- **A non-obvious trade-off is being made.** Choosing performance
  over readability in a specific module, accepting a known limitation
  to ship on time, using a deprecated API deliberately.
- **A constraint is being relaxed or tightened.** Allowing
  previously-forbidden patterns, adopting a stricter lint rule,
  changing the definition of done.

## Do not write an ADR for

- **Routine implementation.** "I added a helper function in X",
  "I renamed a variable", "I split a long function". These belong in
  the code and the commit message.
- **Bug fixes that restore intended behaviour.** Unless the fix
  reveals a design flaw that changes how a whole area of the code
  should work, a commit and a test are enough.
- **Purely local refactors** that do not change behaviour, external
  contracts, or team conventions.
- **Exploratory work** that may be reverted. Record the decision
  once it is actually made, not while it is being evaluated.

## Heuristics

- If the next contributor is likely to ask "why is this done this way?"
  and the answer is not obvious from the code, the decision needed an
  ADR.
- If you find yourself reversing a decision that was never written
  down, write the ADR for the reversal — and, if practical, write a
  retroactive one for the original choice, dated when it was made and
  supersed it in the same commit.
- When in doubt, write the ADR. ADRs are cheap to produce and
  valuable to have. The bar is "would anyone ever ask why?", not
  "is this earth-shattering?".

## Numbering

ADRs live at `docs/upstream/adr/NNNN-<slug>.md`. To pick the next
number, look at what is already there:

```sh
ls docs/upstream/adr/ | grep -E '^[0-9]{4}-' | sort -n | tail -1
```

Take the next integer and zero-pad to four digits. The same rule
applies to PRDs (`docs/upstream/prd/`) and design documents
(`docs/upstream/design/`); each directory has an independent
sequence.

If two branches claim the same number concurrently, resolve at
review time per
[`documentation-policy.md`](documentation-policy.md) §4.1:
renumber the newer PR's document upward during rebase, and update
any inbound references (other ADRs' `supersedes` /
`superseded-by` pointers, commit messages, PR descriptions) in the
same rebase.

## Length

Most ADRs are 15–40 lines. Context, decision, consequences — each in
a paragraph or two, in plain prose. If an ADR is growing beyond one
screen, ask whether the decision is actually one decision or several;
split accordingly.
