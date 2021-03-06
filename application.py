# A web application for image manipulation and text extraction from embedded images

# imported libraries
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for, session, logging, request
from flask_restful import Resource, Api
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
import os
from PIL import Image
from flask_sqlalchemy import SQLAlchemy
import boto3
from boto3.dynamodb.conditions import Key, Attr
from time import sleep
from sqs_process_ocr import processOCRQueue
from threading import Thread
import uuid
from s3_helper import S3Utils
import json
import atexit
from credential_helper import get_secret 
from flask_wtf.csrf import CSRFProtect



application = app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)
api = Api(application)

REGISTER_PAGE = 'signup.html' 
ERROR_PAGE = "error.html"
STATIC_IMAGE = 'static/images'

class CropImage(Resource):
    # def get(self):
    #     return {'hello': 'world'}
    def crop(x1, y1, x2, y2, filename):

    # open image
        target = os.path.join(APP_ROOT, STATIC_IMAGE)
        destination = "/".join([target, filename])
    
        img = Image.open(destination)
        width = img.size[0]
        height = img.size[1]
    
        # check for valid crop parameters
        [x1, y1, x2, y2] = [int(x1), int(y1), int(x2), int(y2)]
    
        crop_possible = True
    
        while True:
            if not 0 <= x1 < width:
                crop_possible = False
                break
            if not 0 < x2 <= width:
                crop_possible = False
                break
            if not 0 <= y1 < height:
                crop_possible = False
                break
            if not 0 < y2 <= height:
                crop_possible = False
                break
            if not x1 < x2:
                crop_possible = False
                break
            if not y1 < y2:
                crop_possible = False
                break
            break

    # process image
        if crop_possible:
            img = img.crop((x1, y1, x2, y2))
        else:
            return render_template(ERROR_PAGE, message="Crop dimensions not valid"), 400
    
        # save and return image
        destination = "/".join([target, 'temp.png'])
        if os.path.isfile(destination):
            os.remove(destination)
        img.save(destination)

        return send_image('temp.png')

api.add_resource(CropImage, '/crop')

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
app.config['SECRET_KEY'] = 'sonia-ghongadi-top-secrete'


STAGE = None
if 'STAGE_LOCATION' in os.environ:
    # can be either empty or set to ELASTICBEANSTALK
    STAGE = os.environ['STAGE_LOCATION']

# DynamoDB functionality
dynamodb_resource = boto3.resource('dynamodb',region_name='us-east-1')
table = dynamodb_resource.Table('userdata')
ocr_table = dynamodb_resource.Table('OCR')

# S3 functionality
UPLOAD_FOLDER = "uploads"
BUCKET = "image-processing-sonia"
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
S3Utils.create_bucket(BUCKET)

SQSQueue = 'OCRQueue.fifo'
get_secret()
thread = Thread(target=processOCRQueue, args=[SQSQueue])
thread.start()

# Sets local vs global config 
def isLocal():
    global SQSQueue
    if STAGE:
        
        SQSQueue = 'OCRQueue.fifo'
        print('SoniaDebug: this is elastic beanstalk env')
        return False
    SQSQueue = 'OCRQueue-cloud9.fifo'
    print('SoniaDebug: this is local env')
    return True


class OCRItem:
  def __init__(self, imageTag, imageURL, status, extracted_text):
    self.imageTag = imageTag
    self.imageURL = imageURL
    self.status = status
    self.extracted_text = extracted_text

# Home Page
@app.route("/")
def index():
    isLocal()
    if 'user_email' in session:
        db_result = ocr_table.scan(
            FilterExpression=Attr("owner").eq(session['user_email'])
        )
        items = db_result['Items']
        ocrqueue = [];
        for item in items:
            imageTag = OCRItem(item['imageTag'], item['imageURL'], item['status'], item['text']);
            ocrqueue.append(imageTag)
        return render_template('index.html', ocrqueue = ocrqueue)
    return redirect(url_for('intro'))

# Home Page    
@app.route("/intro")
def intro():
    isLocal()
    return render_template('intro.html')


# Upload an image and save it to local directory
@app.route("/upload", methods=["POST"])
def upload():
    target = os.path.join(APP_ROOT, 'static/images/')

    # create image directory if not found
    if not os.path.isdir(target):
        os.mkdir(target)

    # retrieve file from html file-picker
    upload = request.files.getlist("file")[0]
    print("File name: {}".format(upload.filename))
    filename = upload.filename

    # file support verification
    ext = os.path.splitext(filename)[1]
    if (ext == ".jpg") or (ext == ".png") or (ext == ".bmp"):
        print("File accepted")
    else:
        return render_template(ERROR_PAGE, message="The selected file is not supported"), 400

    # save file
    destination = "/".join([target, filename])
    print("File saved to to:", destination)
    upload.save(destination)
    
    
    # forward to processing page
    return render_template("processing.html", image_name=filename, )

# Add Image to OCR 
@app.route("/addocr", methods=["GET"])
def addocr():
    # retrieve parameters from html form
    filename = request.args.get('image')
    # open and process image
    target = os.path.join(APP_ROOT, STATIC_IMAGE)
    destination = "/".join([target, filename])
    
    imageID= uuid.uuid4().hex
    object_url = S3Utils.upload_file(BUCKET, destination, filename)
    # add to queue
    sqs = boto3.resource('sqs', region_name='us-east-1')
    # Get the queue
    queue = sqs.get_queue_by_name(QueueName='OCRQueue.fifo')
    data = {
        'imageTag': imageID,
        'imageURL':object_url,
        'owner': session['user_email'],
    }
    queue.send_message(MessageBody=json.dumps(data),MessageGroupId='SimpleOCRGroup', MessageDeduplicationId=uuid.uuid4().hex)
    
    # Add a record in dynamo db 
    ocr_table.put_item(Item= {
        'imageTag': imageID,
        'imageURL':object_url, 
        'status': 'In queue', 
        'owner': session['user_email'],
        'text': ''
    })

    return redirect(url_for('index'))

# Rotate the image to the specified degrees
@app.route("/rotate", methods=["POST"])
def rotate():
    # retrieve parameters from html form
    angle = request.form['angle']
    filename = request.form['image']

    # open and process image
    target = os.path.join(APP_ROOT, STATIC_IMAGE)
    destination = "/".join([target, filename])

    img = Image.open(destination)
    img = img.rotate(-1*int(angle))

    # save and return image
    destination = "/".join([target, 'temp.png'])
    if os.path.isfile(destination):
        os.remove(destination)
    img.save(destination)

    return send_image('temp.png')


# Flip image 'vertical' or 'horizontal'
@app.route("/flip", methods=["POST"])
def flip():

    # retrieve parameters from html form
    if 'horizontal' in request.form['mode']:
        mode = 'horizontal'
    elif 'vertical' in request.form['mode']:
        mode = 'vertical'
    else:
        return render_template(ERROR_PAGE, message="Mode not supported (vertical - horizontal)") 
    filename = request.form['image']

    # open and process image
    target = os.path.join(APP_ROOT, STATIC_IMAGE)
    destination = "/".join([target, filename])

    img = Image.open(destination)

    if mode == 'horizontal':
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    else:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # save and return image
    destination = "/".join([target, 'temp.png'])
    if os.path.isfile(destination):
        os.remove(destination)
    img.save(destination)

    return send_image('temp.png')


# Crop image from (x1,y1) to (x2,y2)
@app.route("/crop", methods=["POST"])
def crop():
    # retrieve parameters from html form
    x1 = int(request.form['x1'])
    y1 = int(request.form['y1'])
    x2 = int(request.form['x2'])
    y2 = int(request.form['y2'])
    filename = request.form['image']

    # open image
    target = os.path.join(APP_ROOT, STATIC_IMAGE)
    destination = "/".join([target, filename])

    img = Image.open(destination)

    # check for valid crop parameters
    width = img.size[0]
    height = img.size[1]

    crop_possible = True
    if not 0 <= x1 < width:
        crop_possible = False
    if not 0 < x2 <= width:
        crop_possible = False
    if not 0 <= y1 < height:
        crop_possible = False
    if not 0 < y2 <= height:
        crop_possible = False
    if not x1 < x2:
        crop_possible = False
    if not y1 < y2:
        crop_possible = False

    # crop image and show
    if crop_possible:
        img = img.crop((x1, y1, x2, y2))

        # save and return image
        destination = "/".join([target, 'temp.png'])
        if os.path.isfile(destination):
            os.remove(destination)
        img.save(destination)
        return send_image('temp.png')
    else:
        return render_template(ERROR_PAGE, message="Crop dimensions not valid") 


# Blend image with stock photo and alpha parameter
@app.route("/blend", methods=["POST"])
def blend():
    # retrieve parameters from html form
    alpha = request.form['alpha']
    filename1 = request.form['image']

    # open images
    target = os.path.join(APP_ROOT, STATIC_IMAGE)
    filename2 = 'blend.jpg'
    destination1 = "/".join([target, filename1])
    destination2 = "/".join([target, filename2])

    img1 = Image.open(destination1)
    img2 = Image.open(destination2)

    # resize images to max dimensions
    width = max(img1.size[0], img2.size[0])
    height = max(img1.size[1], img2.size[1])

    img1 = img1.resize((width, height), Image.ANTIALIAS)
    img2 = img2.resize((width, height), Image.ANTIALIAS)

    # if image in gray scale, convert stock image to monochrome
    if len(img1.mode) < 3:
        img2 = img2.convert('L')

    # blend and show image
    img = Image.blend(img1, img2, float(alpha)/100)

    # save and return image
    destination = "/".join([target, 'temp.png'])
    if os.path.isfile(destination):
        os.remove(destination)
    img.save(destination)

    return send_image('temp.png')


# retrieve file from 'static/images' directory
@app.route('/static/images/<filename>')
def send_image(filename):
    return send_from_directory("static/images", filename)


# Route to registration page to add a new user
@app.route('/register', methods=["GET", "POST"])
def register():
    # Look for a session value
    if 'user_email' in session:
        return redirect(url_for('show_all'))
    session.pop('_flashes', None)

    # Validation on user's details
    if request.method == "POST":
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']

        if not request.form['firstname'] or not request.form['lastname'] or not request.form['email'] or not request.form['password']:
            flash('Please enter all the fields')
            return render_template(REGISTER_PAGE)
        else:
            # Add to database
            response = table.query(
                KeyConditionExpression=Key('email').eq(email))
            abc_array = []

            if response['Items']:
                flash('Email is already taken, please select a new one')
                return render_template(REGISTER_PAGE)

            hash_pass = generate_password_hash(password)
            table.put_item(Item={'firstname': firstname,
                                 'lastname': lastname,
                                 'email': email,
                                 'password': hash_pass})
            session['user_email'] = email
        return redirect(url_for('index'))
    return render_template(REGISTER_PAGE)
    
@app.route("/login",methods=["GET","POST"])
def login():
    # Look for a session value
    if 'user_email' in session:
        return redirect(url_for('index'))
    
    # Validation for user's email and password 
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        table = dynamodb_resource.Table('userdata')
        response = table.query(
                KeyConditionExpression=Key('email').eq(email))
        print(response['Items'][0]['password'])
        if not response or not check_password_hash(response['Items'][0]['password'],request.form['password']):
            flash('Invalid username or password')
            return render_template('login.html')
    
        session['user_email'] = request.form['email']
        return redirect(url_for('index'))
    return render_template('login.html')
    
# Route to logput page
@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('intro'))



#look for a main module
if __name__ == "__main__":
        my_port = int(os.environ.get("PORT", 8080)) 
        app.run(host=os.environ['IP'], port = my_port, debug = True)