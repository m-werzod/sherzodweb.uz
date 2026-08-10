"""Minimal MinIO/S3 client for the montage worker.

The agents service had no object-storage client (the web owns putObject). The
montage worker needs to pull the user's uploaded clip and push the rendered MP4,
so this mirrors apps/web/src/lib/storage/s3.ts with the same env contract.

The agents container MUST be able to reach the MinIO endpoint and have the S3_*
env vars set — same bucket the web writes uploads into.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any
from urllib.parse import quote

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]


def _bucket() -> str:
    return os.getenv("S3_BUCKET", "smm-media")


@lru_cache(maxsize=1)
def _client() -> Any:
    access = os.getenv("S3_ACCESS_KEY_ID")
    secret = os.getenv("S3_SECRET_ACCESS_KEY")
    if not access or not secret:
        raise RuntimeError("S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY not set for montage worker")
    path_style = os.getenv("S3_FORCE_PATH_STYLE", "true") == "true"
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://minio:9000"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if path_style else "auto"},
        ),
    )


def download_object(key: str, dst_path: str) -> None:
    _client().download_file(_bucket(), key, dst_path)


def upload_object(key: str, src_path: str, *, content_type: str = "video/mp4") -> None:
    _client().upload_file(
        src_path,
        _bucket(),
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=604800, immutable",
        },
    )


def delete_object(key: str) -> None:
    """Delete a single object — used to reclaim a superseded final_render so a
    re-render doesn't orphan its predecessor in the bucket. S3 delete is
    idempotent (no error if the key is already gone)."""
    _client().delete_object(Bucket=_bucket(), Key=key)


def media_url(key: str) -> str:
    """Browser-facing proxy path — mirror of the web's mediaUrl()."""
    safe = "/".join(quote(part) for part in key.split("/"))
    return f"/api/media/{safe}"
