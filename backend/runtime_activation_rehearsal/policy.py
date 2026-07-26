"""Code-fixed policy for the synthetic activation rehearsal."""

from __future__ import annotations

from enum import Enum
import hashlib


class ManagedZone(str, Enum):
    """The complete non-private first-stage role set."""

    MAIN = "main"
    RUNTIMES = "runtimes"
    LOCAL_DATA = "local_data"
    RUNTIME_TEMP = "runtime_temp"
    LOGS = "logs"
    ARTIFACTS = "artifacts"
    WORKTREES = "worktrees"
    CONFIG = "config"


class ManagedResourceRole(str, Enum):
    """Ordinary writable resources required by activation."""

    ATTACHMENT_TEMP = "attachment_temp"
    SERVICE_LOG = "service_log"
    PID_STATE = "pid_state"
    NON_SECRET_CONFIG = "non_secret_config"
    BROWSER_EXTENSION = "browser_extension"


PINNED_PYTHON_VERSION = "3.12.13"
PINNED_SQLITE_VERSION = "3.50.4"
LOCKED_DEPENDENCIES = (
    "beautifulsoup4==4.15.0",
    "cryptography==49.0.0",
    "openpyxl==3.1.5",
    "openai==2.45.0",
    "python-dotenv==1.2.2",
    "pypdf==6.14.2",
    "python-docx==1.2.0",
    "Pillow==12.3.0",
    "pytesseract==0.3.13",
)
CONFIG_KEYS = (
    "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
    "EMAIL_AGENT_LOG_LEVEL",
)
LOCK_SHA256 = hashlib.sha256(
    ("\n".join(LOCKED_DEPENDENCIES) + "\n").encode("utf-8")
).hexdigest()
