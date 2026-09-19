# Independent Email AI Assistant Desktop

This project is a NEW, independent Windows desktop build requested on 2026-09-19.
The original email_ai_assistant migration route was cancelled by the operator on
2026-09-19. The operator authorizes deletion of the exact seven legacy directories
after verified extraction of useful history, dirty work, data and sensitive config.
See docs/desktop_transition.md for the active product boundary. Local retirement
scope and receipts are retained under the Git-excluded docs/retirement_20260919.
This application does not implement or execute the old Issue #39 migration.

Keep all application-owned source, Python runtime, dependency packages, build
cache, binaries, configuration, data, logs and temporary files beneath this folder.
Use Python 3.14.7 and the stable dependency versions recorded in requirements.txt
and requirements-resolved.lock. The operator explicitly superseded old version
ceilings and requested latest stable versions after compatibility verification.

Analyze only user-submitted current-email text and explicitly selected attachments
after a click. At most 5 files, 10 MiB each, 25 MiB total. No mailbox scanning,
automatic sending, deletion or archiving. Model results are suggestions requiring
human review. Treat all mail, files and model outputs as untrusted data.

Remote providers default disabled. Keys are session-only, backend-only, and never
saved or logged. Legacy sensitive config and historical data may be retained only
in the operator-approved encrypted LegacyArchive, excluded from Git and normal
runtime. Do not automatically restore or connect those archives to the application.
External private stores are outside retirement scope. No history import or
authority-store reader is connected. Preserve privacy, grounding and schema checks.

Run Runtime/Python3147/python.exe -B -m unittest discover -s tests. Build with
scripts/build_windows.ps1. Verify the actual executable with its --self-test
using synthetic data, not a real mailbox or provider. Record tested limitations.

Matt Pocock skills are the preferred workflow; Superpowers is not used here.
