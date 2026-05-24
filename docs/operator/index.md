# Operator documentation index

Documentation for people running the system — deployment,
configuration, runbooks, on-call procedures.

**Freshness requirement.** Every document in this directory (except
this index) must carry a `Last reviewed: YYYY-MM-DD` footer.
`scripts/check-docs.sh` warns at 6 months and errors at 12 months.
See [`../agent/documentation-policy.md`](../agent/documentation-policy.md) §3.

<!-- Add entries as the project grows. Example:

| Document                 | Purpose                                  |
| ------------------------ | ---------------------------------------- |
| deployment.md            | How to deploy a new version              |
| on-call.md               | First-responder runbook                  |
-->

**Start here:** [pipeline-checklist.md](pipeline-checklist.md) —
end-to-end bring-up checklist with links to each detail guide.

| Document | Purpose |
| -------- | ------- |
| [pipeline-checklist.md](pipeline-checklist.md) | Ordered bring-up checklist (start here) |
| [gas-setup.md](gas-setup.md) | GAS relay: clasp auth, push, Web App deploy, troubleshooting |
| [r2-setup.md](r2-setup.md) | Cloudflare R2: bucket, API token, model upload layout |
| [pipeline-secrets.md](pipeline-secrets.md) | All GitHub Actions secrets: what they are and how to obtain them |
