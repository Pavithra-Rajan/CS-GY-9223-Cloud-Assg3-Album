import json
import os
import logging
import urllib.parse
from datetime import datetime

import boto3
from requests_aws4auth import AWS4Auth 
from requests.auth import HTTPBasicAuth
import requests
from opensearchpy import OpenSearch, RequestsHttpConnection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')

OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '')
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME' ,'')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD','')
REGION = os.environ.get('AWS_REGION', 'us-east-1')
INDEX_NAME = "photos"

def lambda_handler(event, context):
    """Handles S3 PUT events to index photos into OpenSearch."""
    
    # Get S3 Object Info from the event (E1)
    if not event.get('Records'):
        logger.error("No records found in S3 event.")
        return {'statusCode': 400, 'body': 'No S3 records'}

    record = event['Records'][0]
    bucket_name = record['s3']['bucket']['name']
    
    # Decode URL-encoded key (e.g., spaces become '+')
    object_key = urllib.parse.unquote_plus(record['s3']['object']['key'])
    
    # The timestamp will be set as current time
    created_timestamp = datetime.utcnow().isoformat()
    
    logger.info(f"Processing object: {object_key} from bucket: {bucket_name}")

    # Initialize the final labels array (A1)
    labels_array = [] 

    # Retrieving Custom Metadata (x-amz-meta-customLabels) 
    try:
        logger.info(f"RAW EVENT KEY: {record['s3']['object']['key']}")
        logger.info(f"DECODED KEY: {object_key}")

        resp = s3_client.list_objects_v2(Bucket=bucket_name)
        all_keys = [obj['Key'] for obj in resp.get('Contents', [])]
        logger.info(f"AVAILABLE KEYS: {all_keys}")
        head_response = s3_client.head_object(
            Bucket=bucket_name,
            Key=object_key
        )

        custom_labels_header = head_response['Metadata'].get('x-amz-meta-customlabels')
        
        if custom_labels_header:
            custom_labels = [label.strip().lower() for label in custom_labels_header.split(',')]
            labels_array.extend(custom_labels)
            logger.info(f"Added custom labels: {custom_labels}")
            
    except Exception as e:
        logger.error(f"Error retrieving S3 metadata for {object_key}: {e}")

    # Detect Labels using Rekognition 
    try:
        rekognition_response = rekognition_client.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            },
            MaxLabels=15,
            MinConfidence=80 
        )

        detected_labels = [label['Name'].strip().lower() for label in rekognition_response['Labels']]
        labels_array.extend(detected_labels)
        logger.info(f"Added Rekognition labels: {detected_labels}")

    except Exception as e:
        logger.error(f"Error detecting labels with Rekognition for {object_key}: {e}")

    final_labels = list(set([label for label in labels_array if label]))

    if not final_labels:
        logger.warning(f"No labels (custom or detected) found for {object_key}. Skipping index.")
        return {'statusCode': 200, 'body': 'No labels to index'}

    document_body = {
        'objectKey': object_key,
        'bucket': bucket_name,
        'createdTimestamp': created_timestamp,
        'labels': final_labels
    }
    
    # OpenSearch indexing 
    try:
        os_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
        http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
        )
        # https://docs.opensearch.org/latest/clients/python-low-level/
        response = os_client.index(
        index = INDEX_NAME,
        body = document_body,
        refresh = True
    )
    except Exception as e:
        logger.error(f"Error indexing document into OpenSearch for {object_key}: {e}")
        return {'statusCode': 500, 'body': 'Error indexing document'}
            
    return {'statusCode': 200, 'body': 'Indexing process executed'}