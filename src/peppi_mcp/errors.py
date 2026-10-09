"""Safe application errors. Never include raw source payloads or arguments."""

from pydantic import BaseModel, ConfigDict


class PeppiError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class ErrorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ErrorInfo
