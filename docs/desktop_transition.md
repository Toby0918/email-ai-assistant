# Independent Windows desktop baseline

The maintainer cancelled the governed Project Container migration route on
2026-09-19 and selected an independent runnable Windows desktop application.
This branch descends from master commit
`407f49b1a3b10786b496d339e4eb39a1f8cc30b2`, preserving the repository history.
Historical source remains available through Git; migration modules and scripts
are removed from the active source tree rather than carried into desktop startup.

The product retains current-email analysis, bounded user-selected attachments,
privacy and grounding checks, human review before copying drafts, a local-only
service and optional session-configured AI providers. The native desktop window
and PyInstaller packaging provide an executable without a separately installed
Python runtime. The retained browser extension requires manual installation and
separate current-message integration acceptance. Historical knowledge import and
administrator mailbox ingestion are not part of this baseline.

Issues #29, #39 and #40 were closed as not planned. Issues #24–#27 remain open for
scope reconciliation, and the earlier historical-knowledge requirements remain
deferred. Local synthetic tests do not satisfy those earlier acceptance criteria.

The Windows Desktop workflow installs the exact compatible dependency lock and
checks the official SQLite archive checksum before building. Its quality-gates
job runs the source suite and actual packaged executable self-test, then produces
a runnable Windows artifact. All model and mailbox access remains disabled during
these checks. It does not claim that real-mailbox integration or AI answer quality
has been accepted.

The former migration/provenance workflows are removed on this branch. Master
protection still requires legacy provenance checks until the maintainer reviews
the transition; branch protection is not weakened by this source change. Merging
requires reconciling that policy with the new Windows workflow. No check with a
legacy provenance name is fabricated to bypass the old requirements.

Local historical archives, runtime installations, builds, databases, configuration,
logs and retirement receipts are excluded from Git. Encrypted local archives are
never loaded by the application and contain no operational dependency of the new
desktop program.
