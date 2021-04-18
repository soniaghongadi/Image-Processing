import boto3 
from time import sleep
import requests
import json
import ocrspace
from google.oauth2 import service_account

def detect_text_uri(uri, credentials):
    """Detects text in the file located in Google Cloud Storage or on the Web.
    """
    from google.cloud import vision
    client = vision.ImageAnnotatorClient(credentials=credentials)
    image = vision.Image()
    image.source.image_uri = uri

    response = client.text_detection(image=image)
    texts = response.text_annotations
    parsed_text = ''
    for text in texts:
        parsed_text = text.description
        break;
    if response.error.message:
        return response.error.message
    return parsed_text


ocr_space_key = 'e40860ac2688957'
api = ocrspace.API(ocr_space_key, ocrspace.Language.Croatian)

def ocr_with_library(url):
    api.ocr_url(url)

def ocr_space_url(url):
    payload = {'url': url,
               'apikey': ocr_space_key,
               'filetype': 'png'
               }
    r = requests.post('https://api.ocr.space/parse/image',
                      data=payload,
                      )
    return r.content.decode()

def processOCRQueue(queue_name):
    # Get the service resource
    sqs = boto3.resource('sqs',  region_name='us-east-1')
    credentials = service_account.Credentials. from_service_account_file('creds.json')
    # Get the queue
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    dynamodb_resource = boto3.resource('dynamodb',region_name='us-east-1')
    ocr_table = dynamodb_resource.Table('OCR')

    # Process messages by printing out body and optional author name
    while(True):
        for message in queue.receive_messages(MessageAttributeNames=['Author']):
            print('new message available')
            print('Detected message in queue with following content in message: {}', message.body)
            message_body = json.loads(message.body)
            # Let the queue know that the message is processed
            extracted_text = detect_text_uri(message_body['imageURL'], credentials)
            ocr_table.put_item(Item= {
                'imageTag': message_body['imageTag'],
                'imageURL':message_body['imageURL'], 
                'status': 'Completed', 
                'text': extracted_text,
                'owner': message_body['owner'],
            })
            print('::::{}::::',extracted_text)
            print('message is written succesfully')
            message.delete()
        sleep(1)