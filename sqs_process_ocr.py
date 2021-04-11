import boto3 
from time import sleep

def detect_text_uri(uri):
    """Detects text in the file located in Google Cloud Storage or on the Web.
    """
    from google.cloud import vision
    client = vision.ImageAnnotatorClient()
    image = vision.Image()
    image.source.image_uri = uri

    response = client.text_detection(image=image)
    texts = response.text_annotations
    print('Texts:')

    for text in texts:
        print('\n"{}"'.format(text.description))

        vertices = (['({},{})'.format(vertex.x, vertex.y)
                    for vertex in text.bounding_poly.vertices])

        print('bounds: {}'.format(','.join(vertices)))

    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))

def processOCRQueue():
    # Get the service resource
    sqs = boto3.resource('sqs',  region_name='us-east-1')
    # Get the queue
    queue = sqs.get_queue_by_name(QueueName='OCRQueue.fifo')
    # Process messages by printing out body and optional author name
    while(True):
        for message in queue.receive_messages(MessageAttributeNames=['Author']):
            print('new message available')
            # Get the custom author message attribute if it was set
            author_text = ''
            if message.message_attributes is not None:
                author_name = message.message_attributes.get('Author').get('StringValue')
                if author_name:
                    author_text = ' ({0})'.format(author_name)
        
            # Print out the body and author (if set)
            print('Hello, {0}!{1}'.format(message.body, author_text))
        
            # Let the queue know that the message is processed
            message.delete()
        sleep(1)