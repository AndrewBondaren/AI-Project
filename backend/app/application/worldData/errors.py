"""Domain errors of the worldData application services — W1-1.

No FastAPI here: ``api/errorMapping.py`` maps these to HTTP responses.
``WorldDataValidationError`` doubles as ``ValueError`` so the existing
bundle preflight seam (``worldBundleService`` ``except ValueError``)
catches it without a second class — plan worlddata-http-decoupling.
"""

from __future__ import annotations


class WorldDataError(Exception):
    """Base worldData domain error."""


class WorldDataNotFoundError(WorldDataError):
    """Entity lookup miss — maps to 404 in the api layer."""


class WorldDataValidationError(WorldDataError, ValueError):
    """Invalid entity data — maps to 422; ``ValueError`` keeps the
    bundle preflight ``except ValueError`` seam working."""
