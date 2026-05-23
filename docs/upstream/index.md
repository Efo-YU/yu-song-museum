# Upstream documents

Product requirements, technical designs, and architecture decisions —
documents that describe *what* should exist and *why*, as opposed to
how the code that exists today works (the latter lives under
[`../developer/`](../developer/)). See
[`../agent/documentation-policy.md`](../agent/documentation-policy.md) §5
for the full policy.

## Sub-directories

- [`prd/`](prd/) — Product requirements documents.
- [`design/`](design/) — Technical design documents / RFCs.
- [`adr/`](adr/) — Architecture decision records.

Each sub-directory has its own `index.md` listing its contents with
status.

## Numbering

Documents are numbered `NNNN-<slug>.md` where `NNNN` is a
zero-padded sequence number per sub-directory. See
[`../agent/documentation-policy.md`](../agent/documentation-policy.md) §5
and [`../agent/when-to-write-an-adr.md`](../agent/when-to-write-an-adr.md)
for details, including how to resolve numbering collisions between
concurrent branches.
