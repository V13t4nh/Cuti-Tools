"""Single error taxonomy for CUTI-Tools.

Every failure is explicit and typed. No silent fallbacks anywhere in the code
base: a component either returns a valid result or raises one of these errors.
"""

from __future__ import annotations


class CutiError(Exception):
    """Base class for every error raised by this package."""


class ConfigError(CutiError):
    """Invalid or missing configuration."""


class FetchError(CutiError):
    """A source could not be fetched."""


class ScrapeError(CutiError):
    """A source payload could not be parsed into complete records."""


class NormalizationError(CutiError):
    """A title could not be normalized into brand / model / condition."""


class StorageError(CutiError):
    """The SQLite layer is unusable or a write violated an invariant."""


class PricingError(CutiError):
    """Pricing inputs are invalid."""


class NotifierError(CutiError):
    """An alert could not be delivered."""
