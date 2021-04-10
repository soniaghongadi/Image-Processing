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
        """Create an S3 bucket in a specified region

        If a region is not specified, the bucket is created in the S3 default region (us-east-1).

        :param bucket_name: Bucket to create
        :param region: String region to create bucket in, e.g., 'us-west-2'
        :return: True if bucket created, else False
        """

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
        """Upload a file to an S3 bucket

        :param file_name: File to upload
        :param bucket: Bucket to upload to
        :param object_name: S3 object name. If not specified then file_name is used
        :return: True if file was uploaded, else False
        """

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
        """Retrieves a given object from a S3 bucket
    
        :param bucket_name: the name of the bucket to retrieve the object from
        :param object_key: the key of the object to retrieve (the key uniquely identifies the object in a bucket)
        :return: True if operation successful, otherwise False
        """
        try:
            s3_client = S3Utils.get_S3_client()
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            return response
        
        except ClientError as e:
            logging.error(e)
            return None
        
    
    
    @staticmethod
    def list_objects_from_a_bucket(bucket_name):
        """List/Display all the objects from a given S3 bucket
    
        :param bucket_name: the name of the bucket
        :return: True if operation successful, otherwise False
        """
        
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
        """Download a given object to a file
    
        :param bucket_name: the name of the bucket to download from
        :param object_key: the key of the object to download (the key uniquely identifies the object in a bucket)
        :param filename: the name of the file (including complete path to the file) to download to
        :return: True if operation successful, otherwise False
        """
    
        
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
