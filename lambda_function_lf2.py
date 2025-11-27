import json
import os
import logging
import boto3
from requests_aws4auth import AWS4Auth 
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lex_client = boto3.client('lexv2-runtime', region_name='us-east-1') 

OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST')
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD') 
LEX_BOT_NAME = os.environ.get('LEX_BOT_NAME') 
LEX_BOT_ALIAS_NAME = os.environ.get('LEX_BOT_ALIAS_NAME') 
REGION = os.environ.get('AWS_REGION', 'us-east-1')

def lambda_handler(event, context):
    """
    Handles a search request from API Gateway:
    1. Extracts query 'q'.
    2. Calls Lex V2 to get keywords.
    3. Searches OpenSearch 'photos' index.
    """
    
    #Fetch the raw query string 'q' from the API Gateway event
    try:
        raw_query_text = event['queryStringParameters']['q']
    except (TypeError, KeyError):
        logger.error("Missing query parameter 'q'.")
        return {
            'statusCode': 400,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps({"message": "Missing search query parameter 'q'"})
        }
        
    logger.info(f"Received query: {raw_query_text}")

    search_keywords = []
    
    #Disambiguate the query using the Amazon Lex V2 bot (i) 
    # Followed https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lexv2-runtime/client/recognize_text.html
    try:
        lex_response = lex_client.recognize_text(
            botId=LEX_BOT_NAME,
            botAliasId=LEX_BOT_ALIAS_NAME,
            localeId="en_US",
            sessionId="api_gateway_user",
            text=raw_query_text
        )

        # Lex V2 response structure requires drilling into 'sessionState'
        session_state = lex_response.get('sessionState', {})
        current_intent = session_state.get('intent', {})
        
        intent_name = current_intent.get('name')
        # Check the state of the intent fulfillment
        fulfillment_state = current_intent.get('state') 

        logger.info(f"Lex V2 Response: Intent={intent_name}, State={fulfillment_state}")
        
        # Lex V2 uses 'ReadyForFulfillment' or 'Fulfilled' when slots are gathered
        if intent_name == 'SearchIntent' and fulfillment_state in ['Fulfilled', 'ReadyForFulfillment']:
            
            slots = current_intent.get('slots', {})
            for slot_key, slot_object in slots.items():
                if slot_object and slot_object.get('value'):
                    # The interpretedValue contains the clean, resolved value
                    interpreted_value = slot_object['value'].get('interpretedValue')
                    
                    if interpreted_value:
                        search_keywords.append(interpreted_value.lower().strip())
        
        # Ensure only unique keywords are kept
        search_keywords = list(set(search_keywords))
        
    except Exception as e:
        logger.error(f"Error communicating with Lex bot: {e}")
        # Proceed with empty keywords if Lex fails

    if not search_keywords:
        logger.info("Lex yielded no keywords. Returning empty array.")
        return {
            'statusCode': 200,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps([])
        }

    # If keywords exist, search the 'photos' ElasticSearch index.
    try:
        credentials = boto3.Session().get_credentials()
        # awsauth = AWS4Auth(
        #     credentials.access_key, 
        #     credentials.secret_key, 
        #     REGION, 
        #     'es', # Service name is 'es' for OpenSearch/ElasticSearch
        #     session_token=credentials.token
        # )
        
        http_auth = (OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
            
            # Define the search endpoint URL 
            # OpenSearch runs on port 9200 by default, but AWS usually uses 443 for HTTPS/Public access
        search_url = f'https://{OPENSEARCH_HOST}/photos/_search'

        # Construct the OpenSearch Query Body 
        query_body = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"labels": keyword}} 
                        for keyword in search_keywords
                    ],
                    "minimum_should_match": 1 
                }
            }
        }
        
        response = requests.post(
            search_url,
            auth=http_auth, # Pass the username/password tuple
            headers={"Content-Type": "application/json"},
            data=json.dumps(query_body)
        )
        response.raise_for_status()

        search_results = response.json()
        
        # Extract the required S3 references (objectKey and bucket)
        photos_found = [
            {
                "objectKey": hit['_source']['objectKey'],
                "bucket": hit['_source']['bucket']
            }
            for hit in search_results['hits']['hits']
        ]
        # print(photos_found)

        # Return the results accordingly
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