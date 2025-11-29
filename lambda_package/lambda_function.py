import json
import os
import logging
import boto3
from requests_aws4auth import AWS4Auth 
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lex_client = boto3.client('lex-runtime') 

# Environment Variables
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', 'search-photos-tfffekr76irojpbah7hl6oou4u.us-east-1.es.amazonaws.com')
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME' ,'elastic')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD','Test@1234') 
LEX_BOT_NAME = os.environ.get('LEX_BOT_NAME', 'SearchIntent') 
REGION = os.environ.get('AWS_REGION', 'us-east-1')

def lambda_handler(event, context):
    """
    Handles a search request from API Gateway:
    """
    
    # 1. Get the raw query string 'q' from the API Gateway event
    try:
        # Expected structure from API Gateway GET /search?q={query text}
        raw_query_text = event['queryStringParameters']['q']
    except (TypeError, KeyError):
        logger.error("Missing query parameter 'q'.")
        return {
            'statusCode': 400,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps({"message": "Missing search query parameter 'q'"})
        }
        
    logger.info(f"Received query: {raw_query_text}")

    # Initialize the array to hold extracted keywords
    search_keywords = []
    
    # --- 2. Disambiguate the query using the Amazon Lex bot (i) ---
    try:
        # Call the Amazon Lex PostText API
        lex_response = lex_client.post_text(
            botName=LEX_BOT_NAME,
            botAlias='$LATEST',
            userId='api_gateway_user', # Arbitrary unique ID for the session
            inputText=raw_query_text
        )
        
        # Lex returns the intent and its current state
        intent_name = lex_response.get('intentName')
        dialog_state = lex_response.get('dialogState')

        logger.info(f"Lex response: Intent={intent_name}, State={dialog_state}")
        
        # We assume the intent is configured to be Fulfilled once slots are gathered
        if intent_name == 'SearchIntent' and dialog_state == 'Fulfilled':
            slots = lex_response.get('slots', {})
            
            # Extract all non-empty slot values (keywords K1...Kn)
            for slot_value in slots.values():
                if slot_value:
                    # Convert to lowercase to match the indexed labels
                    search_keywords.append(slot_value.lower().strip())
        
        # Ensure only unique keywords are kept
        search_keywords = list(set(search_keywords))
        
    except Exception as e:
        logger.error(f"Error communicating with Lex bot: {e}")
        # Proceed with empty keywords if Lex fails

    # --- 3. Search ElasticSearch for Results (ii, iii) ---
    if not search_keywords:
        # iii. If no keywords are yielded, return an empty array.
        logger.info("Lex yielded no keywords. Returning empty array.")
        return {
            'statusCode': 200,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps([])
        }

    # ii. If keywords exist, search the 'photos' ElasticSearch index.
    try:
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key, 
            credentials.secret_key, 
            REGION, 
            'es', # Service name is 'es' for OpenSearch/ElasticSearch
            session_token=credentials.token
        )
        
        # Define the search endpoint URL
        search_url = f'https://{OPENSEARCH_HOST}/photos/_search'

        # Construct the OpenSearch Query Body (Boolean OR query for the 'labels' field)
        query_body = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"labels": keyword}} 
                        for keyword in search_keywords
                    ],
                    "minimum_should_match": 1 # Match if ANY label matches
                }
            }
        }
        
        # Execute the search request
        response = requests.post(
            search_url,
            auth=awsauth,
            headers={"Content-Type": "application/json"},
            data=json.dumps(query_body)
        )
        response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)

        search_results = response.json()
        
        # Extract the required S3 references (objectKey and bucket)
        photos_found = [
            {
                "objectKey": hit['_source']['objectKey'],
                "bucket": hit['_source']['bucket']
            }
            for hit in search_results['hits']['hits']
        ]

        # Return the results accordingly (as per the API spec)
        return { 
            'statusCode': 200,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps(photos_found) 
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"OpenSearch Search Failed: {e}")
        return { 
            'statusCode': 500,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps({"error": "Failed to execute search query."}) 
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return { 
            'statusCode': 500,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps({"error": "Internal server error."}) 
        }