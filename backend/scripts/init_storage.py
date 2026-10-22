"""Create the local development S3 bucket. Production buckets are provisioned separately."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.storage.s3 import S3Storage
from app.config import settings

storage = S3Storage()
for attempt in range(30):
    try:
        try:
            storage.client.head_bucket(Bucket=storage.bucket)
        except Exception:
            kwargs={"Bucket":storage.bucket}
            if settings.AWS_REGION != "us-east-1":
                kwargs["CreateBucketConfiguration"]={"LocationConstraint":settings.AWS_REGION}
            storage.client.create_bucket(**kwargs)
        print("Archive bucket is ready.")
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(2)
