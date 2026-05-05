"""MinIO / S3-compatible object storage abstraction."""

import io
import time
from functools import wraps
from pathlib import Path
from typing import Callable, TypeVar

from minio import Minio
from minio.error import S3Error

from core.config import settings

# ── singleton client ──────────────────────────────────────────────────────────

_minio_client: Minio | None = None


def _client() -> Minio:
    """Return the module-level Minio singleton, creating it on first call."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _minio_client


# ── retry decorator ───────────────────────────────────────────────────────────

# Errors that are permanent — no point retrying
_PERMANENT_ERRORS = frozenset(
    {
        "NoSuchKey",
        "NoSuchBucket",
        "AccessDenied",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
    }
)

F = TypeVar("F", bound=Callable)


def _retryable(max_attempts: int = 3, base_delay: float = 0.5) -> Callable[[F], F]:
    """Retry on transient MinIO errors with exponential back-off."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except S3Error as exc:
                    if exc.code in _PERMANENT_ERRORS:
                        raise
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        time.sleep(base_delay * (2**attempt))
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


# ── public API ────────────────────────────────────────────────────────────────


def ensure_bucket() -> None:
    client = _client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


@_retryable()
def upload_bytes(
    object_name: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    _client().put_object(
        settings.minio_bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


@_retryable()
def upload_file(
    object_name: str, file_path: Path, content_type: str = "application/octet-stream"
) -> None:
    _client().fput_object(
        settings.minio_bucket, object_name, str(file_path), content_type=content_type
    )


@_retryable()
def download_bytes(object_name: str) -> bytes:
    response = _client().get_object(settings.minio_bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


@_retryable()
def download_file(object_name: str, dest_path: Path) -> None:
    _client().fget_object(settings.minio_bucket, object_name, str(dest_path))


def object_exists(object_name: str) -> bool:
    try:
        _client().stat_object(settings.minio_bucket, object_name)
        return True
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            return False
        raise  # re-raise permission errors, connectivity failures, etc.


def presigned_url(object_name: str, expires_seconds: int = 3600) -> str:
    from datetime import timedelta

    return _client().presigned_get_object(
        settings.minio_bucket, object_name, expires=timedelta(seconds=expires_seconds)
    )
