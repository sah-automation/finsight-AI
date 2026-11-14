"""PresignedUpload convenience wrapper (behaves as a string and carries the key)."""

from __future__ import annotations


class PresignedUpload(str):
    """A presigned URL that also exposes ``.url`` and ``.key`` attributes."""

    url: str
    key: str | None

    def __new__(cls, url: str, key: str | None = None) -> PresignedUpload:
        obj = super().__new__(cls, url)
        obj.url = url
        obj.key = key
        return obj


__all__ = ['PresignedUpload']
