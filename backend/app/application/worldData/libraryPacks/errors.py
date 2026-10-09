"""Domain errors of the library-pack application service — TZ §0.2.

No FastAPI here: api routes (plan step 4d) map these to HTTP responses.
``usages`` on ``LibraryPackInUseError`` carries human-readable diagnostics
for the caller/report.
"""

from __future__ import annotations


class LibraryPackError(Exception):
    """Base library-pack domain error."""


class LibraryPackNotFoundError(LibraryPackError):
    """Pack or member uid not found."""


class LibraryPackValidationError(LibraryPackError):
    """Invalid input: bad keys, invalid body, owner/dependency violations."""


class LibraryPackConflictError(LibraryPackError):
    """Uniqueness violation (system_name / local_uid / template_uid)."""


class LibraryPackReadOnlyError(LibraryPackError):
    """Write attempted on a declared default pack (TZ §1.1, §6)."""


class LibraryPackInUseError(LibraryPackError):
    """Delete refused: the pack/member is referenced (§0.2 delete policy)."""

    def __init__(self, message: str, usages: tuple[str, ...] = ()) -> None:
        self.usages = usages
        super().__init__(message)
