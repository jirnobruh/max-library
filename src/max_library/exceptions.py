"""
Exceptions for max-client library.
"""
from typing import Any


class MaxError(Exception):
    """Base exception for all max-client errors."""
    pass


class MaxConnectionError(MaxError):
    """Raised when WebSocket connection fails or disconnects unexpectedly."""
    pass


class MaxTimeoutError(MaxError):
    """Raised when an RPC request to the MAX server times out."""
    pass


class MaxAPIError(MaxError):
    """
    Raised when the MAX server returns an error response.
    """
    def __init__(
        self,
        error: str,
        title: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
        raw_response: dict[str, Any] | None = None,
    ):
        self.error = error
        self.title = title or error
        self.message = message or title or error
        self.payload = payload or {}
        self.raw_response = raw_response or {}
        super().__init__(f"{self.title}: {self.message} ({self.error})")


class AuthError(MaxAPIError):
    """Raised when authentication fails."""
    pass


class VerifyCodeWrong(AuthError):
    """Raised when the provided SMS/verification code is incorrect."""
    pass


class UserNotFoundError(MaxAPIError):
    """Raised when a user is not found by ID or phone number."""
    pass
