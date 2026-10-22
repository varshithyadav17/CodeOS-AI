import boto3
from moto import mock_aws
from app.storage.s3 import S3Storage
from app.config import settings


async def test_boto3_archive_round_trip_checksum_metadata_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(settings,"S3_BUCKET","codeos-test-archives")
    with mock_aws():
        client = boto3.client("s3",region_name="us-east-1",aws_access_key_id="test",aws_secret_access_key="test")
        client.create_bucket(Bucket=settings.S3_BUCKET)
        storage = S3Storage(client=client)
        source = tmp_path/"source.zip"
        source.write_bytes(b"archive bytes")
        await storage.put_archive("repo/source.zip",source,"checksum")
        head = client.head_object(Bucket=settings.S3_BUCKET,Key="repo/source.zip")
        assert head["Metadata"]["sha256"] == "checksum"
        assert head["ServerSideEncryption"] == "AES256"
        output = tmp_path/"download.zip"
        await storage.get_archive("repo/source.zip",output)
        assert output.read_bytes() == source.read_bytes()
        await storage.ping()
        await storage.delete("repo/source.zip")
        await storage.delete("repo/source.zip")
        assert client.list_objects_v2(Bucket=settings.S3_BUCKET).get("KeyCount",0) == 0


async def test_s3_delete_removes_historical_versions(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"S3_BUCKET","codeos-versioned-test")
    with mock_aws():
        client=boto3.client("s3",region_name="us-east-1",aws_access_key_id="test",aws_secret_access_key="test")
        client.create_bucket(Bucket=settings.S3_BUCKET)
        client.put_bucket_versioning(Bucket=settings.S3_BUCKET,VersioningConfiguration={"Status":"Enabled"})
        storage=S3Storage(client=client)
        file=tmp_path/"archive.zip"
        for content in (b"one",b"two"):
            file.write_bytes(content)
            await storage.put_archive("repo/source.zip",file,"sha")
        client.put_object(Bucket=settings.S3_BUCKET,Key="other/source.zip",Body=b"keep")
        await storage.delete("repo/source.zip")
        versions=client.list_object_versions(Bucket=settings.S3_BUCKET,Prefix="repo/source.zip")
        assert not versions.get("Versions") and not versions.get("DeleteMarkers")
        assert client.get_object(Bucket=settings.S3_BUCKET,Key="other/source.zip")["Body"].read()==b"keep"
