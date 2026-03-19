"""App-level error types.

These are raised by validators/services and converted into HTTP responses by FastAPI
exception handlers.
"""


class InvalidRequestError(ValueError):
    """Raised when a request is invalid at the application layer (maps to 422)."""


class InternalError(RuntimeError):
    """Raised when a data invariant is violated (maps to 500)."""
