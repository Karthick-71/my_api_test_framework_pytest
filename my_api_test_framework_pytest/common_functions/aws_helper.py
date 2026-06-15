"""
S3 helper — used by data-driven tests to fetch the test-cases file
and to upload run artifacts (reports, failure dumps) after a run.

Lazy-imports boto3 so the framework still runs when AWS isn't installed
(e.g., in a minimal CI matrix).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class S3Helper:
    """Thin wrapper around boto3 S3 client. Only created on demand."""

    def __init__(self, bucket: str, region: str = "ap-south-1"):
        self.bucket = bucket
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def download(self, key: str, dest: Path) -> Path:
        """Pull an object from S3 into a local file."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(dest))
        logger.info("S3 download: s3://%s/%s → %s", self.bucket, key, dest)
        return dest

    def upload(self, src: Path, key: str, content_type: Optional[str] = None) -> str:
        """Push a local file to S3. Returns the s3:// URI."""
        extra = {"ContentType": content_type} if content_type else {}
        self.client.upload_file(str(src), self.bucket, key, ExtraArgs=extra)
        uri = f"s3://{self.bucket}/{key}"
        logger.info("S3 upload: %s → %s", src, uri)
        return uri

    def list_keys(self, prefix: str = "") -> list[str]:
        """List keys under a prefix — pagination handled."""
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys
