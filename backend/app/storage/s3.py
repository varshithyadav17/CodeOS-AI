"""Durable original archives. Temporary files are owned by request/job contexts."""
from __future__ import annotations
from pathlib import Path
import boto3
from botocore.config import Config
from ..config import settings
from ..utils import blocking


class S3Storage:
    def __init__(self, client=None):
        self.client = client or boto3.client("s3", region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(connect_timeout=10, read_timeout=30, retries={"max_attempts": 3, "mode": "standard"}, s3={"addressing_style": "path"}))
        self.bucket = settings.S3_BUCKET

    @staticmethod
    def key(user_id, repo_id):
        return f"repositories/{user_id}/{repo_id}/source.zip"

    async def put_archive(self, key: str, path: Path, sha256: str):
        extra = {"ContentType": "application/zip", "Metadata": {"sha256": sha256}}
        if settings.S3_ENCRYPTION:
            extra["ServerSideEncryption"] = settings.S3_ENCRYPTION
        # put_object avoids orphaned multipart uploads for our bounded archive size.
        def put():
            with path.open("rb") as stream:
                self.client.put_object(Bucket=self.bucket, Key=key, Body=stream, **extra)
        await blocking(put)

    async def get_archive(self, key: str, path: Path):
        def download():
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            try:
                if response.get("ContentLength", 0) > settings.MAX_ARCHIVE_BYTES:
                    raise ValueError("Stored archive exceeds the configured size limit.")
                total = 0
                with path.open("wb") as output:
                    for block in body.iter_chunks(1024 * 1024):
                        total += len(block)
                        if total > settings.MAX_ARCHIVE_BYTES:
                            raise ValueError("Stored archive exceeds the configured size limit.")
                        output.write(block)
            finally:
                body.close()
        await blocking(download)

    async def delete(self, key: str):
        def remove():
            # Erase historical versions and delete markers as well as the current object.
            # A plain delete_object leaves retained bytes in a versioned AWS bucket.
            paginator = self.client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=key):
                objects = [{"Key": item["Key"], "VersionId": item["VersionId"]}
                    for item in page.get("Versions", []) + page.get("DeleteMarkers", []) if item["Key"] == key]
                for offset in range(0, len(objects), 1000):
                    result = self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects[offset:offset+1000], "Quiet": True})
                    if result.get("Errors"):
                        raise RuntimeError("Some archive versions could not be removed.")
            self.client.delete_object(Bucket=self.bucket, Key=key)
            # With versioning enabled, the last delete created a marker. Remove it too.
            response = self.client.list_object_versions(Bucket=self.bucket, Prefix=key)
            for item in response.get("DeleteMarkers", []):
                if item["Key"] == key:
                    self.client.delete_object(Bucket=self.bucket, Key=key, VersionId=item["VersionId"])
        await blocking(remove)

    async def ping(self):
        await blocking(self.client.head_bucket, Bucket=self.bucket)
