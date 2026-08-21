---
last_update: 2026-08-20
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0011: Authenticated GitHub guardrail observation

## Status

Accepted for the approved local authenticated GitHub guardrail compatibility
implementation. This decision
does not authorize a live closure command, protected verifier, commit, push,
ruleset mutation, Issue #38 disposition or Issue #39 execution.

## Context

The fixed anonymous GitHub ruleset detail response can omit
`bypass_actors`. Absence cannot prove that bypass is empty. The authenticated
response explicitly exposes `bypass_actors=[]`, but GitHub currently also adds
the beta wire default `pull_request.parameters.required_reviewers=[]` to the
otherwise unchanged approved configuration. GitHub now also returns the
public-preview wire default
`pull_request.parameters.require_extra_approval_for_unattributed_changes=true`
for existing and new rulesets. GitHub documents that this setting has no effect
when the rule requires zero approving reviews; this ruleset's
`required_approving_review_count` is the exact integer `0`.

Deleting only those exact, semantically inactive wire defaults reproduces the established
965-byte canonical ruleset configuration and configuration fingerprint
`5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`.
The active ruleset observed under the separately approved GitHub-state change
has id `20601214`.

## Decision

Keep `SoloMaintainerClosure.prepare()` and `confirm()` unchanged. Hosted
run/job metadata continues through the code-fixed anonymous public HTTPS
reader. Move only guardrail observation behind private deep module
`github_guardrail.py`.

The production guardrail adapter runs the code-fixed absolute
`C:\Program Files\GitHub CLI\gh.exe`. It uses the existing active
`github.com` keyring identity for `Toby0918`, validates that identity before
and after observation, and makes exactly three code-fixed requests using
`gh api --hostname github.com --method GET --include`:

1. the master ruleset listing;
2. the detail endpoint for the validated positive integer ruleset id; and
3. classic protection for `master`.

Only an exact 404 on the classic-protection request means absent. Every other
non-200 status fails closed. The child process uses `shell=False`, disabled
stdin, separately bounded stdout/stderr, a fixed timeout, and a sanitized
allowlist environment. It disables GitHub CLI update checks and telemetry. The
only permitted nonempty stderr is the exact content-free
`gh: Branch not protected (HTTP 404)\n` diagnostic paired with the fixed classic
endpoint's HTTP 404 and process exit 1; every other stderr fails closed.
Ambient GitHub token, host, repository, config and proxy overrides are not
inherited. Python never requests, reads, stores, logs, returns or prints the
token.

The response must explicitly contain `bypass_actors=[]`. There must be exactly
one pull-request rule. Its `parameters.required_reviewers`, represented by the
wire field `required_reviewers=[]`, may be absent or exactly `[]`; only the exact
empty value is deleted. Its
`parameters.require_extra_approval_for_unattributed_changes` may be absent or
the exact Boolean `true` only when `required_approving_review_count` is the exact
integer `0`; only that accepted value is deleted before normal canonical
projection and exact equality. Missing bypass, nonempty or wrongly typed
bypass/reviewer values, false or wrongly typed unattributed-approval values,
boolean or nonzero approval counts, duplicate pull-request rules, unknown
nested fields, rule reordering, check or app-id drift, and every other mismatch
fail with the existing content-free GitHub guardrail rejection.

No public schema, snapshot field, closure interface, canonical bytes or
fingerprint changes.

## Considered options

### Treat omitted bypass as empty

Rejected because missing authenticated evidence cannot establish the absence
of a bypass actor.

### Add the beta field to the canonical configuration

Rejected because an empty wire-only default carries no approved semantic
change and would unnecessarily change stable canonical bytes and fingerprints.
The same applies to the exact enabled unattributed-approval default only at
exact integer zero approvals, where GitHub documents that it has no effect.

### Read the token in Python or accept caller transport configuration

Rejected because it would expand credential custody and arbitrary endpoint or
command capability beyond the closure contract.

## Consequences

- Current ruleset id `20601214` can be observed without weakening strict
  bypass validation or changing the existing snapshot contract.
- Authentication and transport failures remain one fixed content-free closure
  rejection; no token or raw GitHub response is surfaced.
- Anonymous public HTTPS remains sufficient for hosted provenance metadata,
  while guardrail evidence is authenticated and fresh for each derivation.
- Ruleset existence is evidence only. No live `prepare`, `confirm`, or verifier
  is authorized; Issue #38 and Issue #39 still require their own authorization.
