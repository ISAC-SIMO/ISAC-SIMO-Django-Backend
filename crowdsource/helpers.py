# UPLOAD & Manage Objects in IBM CLOUD STORAGE via http
import base64
from isac_simo.settings import IBM_BUCKET
from isac_simo import settings
import requests

import ibm_boto3
from ibm_botocore.client import Config, ClientError

# Constants for IBM COS values
COS_ENDPOINT = settings.IBM_BUCKET_ENDPOINT
COS_API_KEY_ID = settings.IBM_BUCKET_TOKEN
COS_INSTANCE_CRN = settings.IBM_BUCKET_CRN

# Create resource
cos = ibm_boto3.resource("s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_INSTANCE_CRN,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)

# UPLOAD
def upload_object(object_key, path):
  try:
    # set 5 MB chunks
    part_size = 1024 * 1024 * 5
    file_threshold = 1024 * 1024 * 15
    transfer_config = ibm_boto3.s3.transfer.TransferConfig(
        multipart_threshold=file_threshold,
        multipart_chunksize=part_size
    )
    with open(path, "rb") as file_data:
        cos.Object(settings.IBM_BUCKET, object_key).upload_fileobj(
            Fileobj=file_data,
            Config=transfer_config
        )
    return True
  except Exception as e:
    print(e)
    return False

# UPLOAD RAW OBJECT
def upload_raw_object(object_key, raw_data):
  try:
    cos.Object(settings.IBM_BUCKET, object_key).put(
        Body=raw_data
    )
    return True
  except Exception as e:
    print(e)
    return False

# DELETE
def delete_object(object_key):
  try:
    cos.Object(settings.IBM_BUCKET, object_key).delete()
    return True
  except Exception as e:
    print(e)
    return False

# MOVE
def move_object(new_object_key, old_object_key):
  try:
    cos.Object(settings.IBM_BUCKET, new_object_key).copy_from(CopySource=(settings.IBM_BUCKET+'/'+old_object_key))
    cos.Object(settings.IBM_BUCKET, old_object_key).delete()
    return True
  except Exception as e:
    print(e)
    return False

# GET OBJECT BINARY
def get_object(object_key):
  try:
    file = cos.Object(settings.IBM_BUCKET, object_key).get()
    # file["Body"].read() # ContentType, ETag, ContentLength, LastModified
    return file
  except Exception as e:
    print(e)
    return False