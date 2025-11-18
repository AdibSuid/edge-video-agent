# Video Chunking Feature

This file describes the draft/template for cloud integration for video chunk uploads.

## Expected Usage

When a motion-triggered chunk is saved (see streamer.py), call:

    _upload_chunk_to_cloud(chunk_path, chunk_id)

## Template Implementation

- This function currently logs the intended upload and SQS message.
- Replace with real S3 upload and SQS send when ready.

## Expected Parameters

- chunk_path: Path to the saved video chunk (mp4)
- chunk_id: Unique chunk identifier
- stream_id: Camera stream identifier

## Example S3/SQS Integration (to be implemented)

```python
import boto3

def upload_chunk_to_s3(chunk_path, s3_bucket, s3_key):
    s3 = boto3.client('s3')
    s3.upload_file(str(chunk_path), s3_bucket, s3_key)

def send_sqs_message(sqs_url, stream_id, chunk_id, s3_key):
    sqs = boto3.client('sqs')
    msg = {
        'stream_id': stream_id,
        'chunk_id': chunk_id,
        's3_key': s3_key
    }
    sqs.send_message(QueueUrl=sqs_url, MessageBody=json.dumps(msg))
```

## Next Steps
- Fill in S3 bucket/key and SQS URL when available.
- Replace the template in streamer.py with real calls.
