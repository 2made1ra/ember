from __future__ import annotations


class DependencyUnavailableError(RuntimeError):
    """Raised when a required local service is not reachable or rejects a request."""
