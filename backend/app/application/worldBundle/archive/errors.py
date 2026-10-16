"""Archive transport errors, mapped with existing bundle validation errors."""

from app.application.worldData.bundle.errors import BundleValidationError


class BundleArchiveError(BundleValidationError):
    """Invalid ZIP envelope, manifest, file inventory or JSON encoding."""
