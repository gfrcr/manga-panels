"""Known manga_panels errors — actionable message, not a stack trace."""
from __future__ import annotations


class MangaPanelsError(Exception):
    """Base for expected failures (the CLI catches these and prints the message)."""


class EmptyArchive(MangaPanelsError):
    """Archive with no images."""


class BadArchive(MangaPanelsError):
    """Corrupt archive or invalid image inside it."""


class MissingDependency(MangaPanelsError):
    """Optional extra ([ml]/cbr) or system binary missing."""
