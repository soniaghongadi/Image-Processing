import logging
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
import botocore
import uuid

class S3Utils:
    
    @staticmethod
    def get_S3_client(region=None):
        config = Config(signature_version=botocore.UNSIGNED)
        config.signature_version = botocore.UNSIGNED
        if region is None:
            s3_client = boto3.client('s3')
        else:
            s3_client = boto3.client('s3',config = Config(signature_version=botocore.UNSIGNED),  region_name=region)
        return s3_client
        
    @staticmethod
    def create_bucket(bucket_name, region=None):

        # Create bucket
        try:
            if region is None:
                s3_client = S3Utils.get_S3_client(region)
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client = S3Utils.get_S3_client(region)
                location = {'LocationConstraint': region}
                s3_client.create_bucket(Bucket=bucket_name,
                                    CreateBucketConfiguration=location)
        except ClientError as e:
            logging.error(e)
            return False
        return True
    
    

    @staticmethod
    def list_buckets():
        # Retrieve the list of existing buckets
        s3_client = S3Utils.get_S3_client()
        response = s3_client.list_buckets()

        # Output the bucket names
        print('Existing buckets:')
        for bucket in response['Buckets']:
            print('\t', bucket["Name"])
        
        return response
    
    

    # get a UUID - URL safe, Base64
    @staticmethod
    def get_a_Uuid():
        return uuid.uuid4().hex

    @staticmethod
    def upload_file(bucket, file_name, object_name=None):

        # If S3 object_name was not specified, use file_name
        if object_name is None:
            object_name = file_name

        # Upload the file
        s3_client = S3Utils.get_S3_client()
        try:
            random_hash = S3Utils.get_a_Uuid()
            response = s3_client.upload_file(file_name, bucket, random_hash + object_name, ExtraArgs={'ACL': 'public-read'})
            url_with_query = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket,
                    'Key': random_hash + object_name 
                }
            )
            url = url_with_query.split('?', 1)[0]
            return url
        except ClientError as e:
            logging.error(e)
            return False
        return True
        
        
    @staticmethod
    def get_object(bucket_name, object_key):
        try:
            s3_client = S3Utils.get_S3_client()
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            return response
        
        except ClientError as e:
            logging.error(e)
            return None
        
    
    
    @staticmethod
    def list_objects_from_a_bucket(bucket_name):
        
        items = []
        try:
            s3_client = S3Utils.get_S3_client()
            response = s3_client.list_objects_v2(Bucket=bucket_name)
        
         
            if response['KeyCount'] !=0 :
                #print('The objects in', bucket_name, 'are: ')
                for content in response['Contents']:
                    #object_key = content['Key']
                    #print('\t\t', object_key)
                    items.append(content)
            #else:
                #print('The bucket', bucket_name, 'is empty')
    
        except ClientError as e:
            logging.error(e)
            return []
        
        return items    
    
        
    
    """
        TASK2: download an S3 object to a file
    """
    @staticmethod
    def download_object(bucket_name, object_key, filename):
        #Download a given object to a file
        try:
            s3_client = S3Utils.get_S3_client()
            #print('\nDownloading', object_key, 'from S3 bucket', bucket_name, 'to file', filename, '...')
            s3_client.download_file(bucket_name, object_key, filename)
    
        except ClientError as e:
            logging.error(e)
            return False
        return True 
  
     
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('bucket_name', help='The name of the bucket to create.')
    parser.add_argument('--file_name', help='The name of the file to upload.')
    parser.add_argument('--object_key', help='The object key')
    parser.add_argument('--keep_bucket', help='Keeps the created bucket. When not specified, the bucket is deleted', action='store_true')
 
    args = parser.parse_args()
    region = 'us-east-1'
    S3Utils.create_bucket(args.bucket_name)
    S3Utils.list_buckets()
 


if __name__ == '__main__':
    main()
