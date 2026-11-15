"""Errors raised by the Digital Factory client."""

from __future__ import annotations


class DigitalFactoryError(Exception):
    """Base class for every Digital Factory client error."""


class AuthenticationError(DigitalFactoryError):
    """The credential was rejected; the user has to sign in again."""


class PermissionDenied(DigitalFactoryError):
    """The credential is valid but may not do this."""


class InsufficientPlan(DigitalFactoryError):
    """The workspace's subscription plan does not include this."""


class RateLimited(DigitalFactoryError):
    """The API asked the client to slow down."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ApiUnavailable(DigitalFactoryError):
    """A temporary failure: network trouble, a timeout or a server error."""


class ApiError(DigitalFactoryError):
    """The API answered in a way the client does not understand."""
