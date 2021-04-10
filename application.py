# A web application for image manipulation and text extraction from embedded images

# imported libraries
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for, session, logging, request
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
import os
from PIL import Image
from flask_sqlalchemy import SQLAlchemy
import boto3
from boto3.dynamodb.conditions import Key, Attr
from threading import Thread
from time import sleep
from sqs_process_ocr import processOCRQueue
from threading import Thread


# initilization of flask app
application = app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
app.config['SECRET_KEY'] = 'sonia-ghongadi-top-secrete'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
csrf = CSRFProtect()
csrf.init_app(app)

STAGE = None
if 'STAGE_LOCATION' in os.environ:
    # can be either empty or set to ELASTICBEANSTALK
    STAGE = os.environ['STAGE_LOCATION']


dynamodb_resource = boto3.resource('dynamodb',region_name='us-east-1')
table = dynamodb_resource.Table('userdata')
table_product = dynamodb_resource.Table('Product')
REGISTER_PAGE = 'signup.html' 
ADDPRODUCT_PAGE = 'addproduct.html'

# Sets local vs global config 
def isLocal():
    if STAGE:
        print('SoniaDebug: this is elastic beanstalk env')
        return False
    print('SoniaDebug: this is local env we will use sqlite for logins')
    return True


isLocal()
# Image manipulation page
thread = Thread(target = processOCRQueue)
thread.start()

@app.route("/")
def index():
    isLocal()
    if 'user_email' in session:
        return render_template('index.html')
    return redirect(url_for('intro'))
    
@app.route("/intro")
def intro():
    isLocal()
    return render_template('intro.html')


# upload an image and save it to local directory
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
        return render_template("error.html", message="The selected file is not supported"), 400

    # save file
    destination = "/".join([target, filename])
    print("File saved to to:", destination)
    upload.save(destination)

    # forward to processing page
    return render_template("processing.html", image_name=filename)


# rotate the image to the specified degrees
@app.route("/rotate", methods=["POST"])
def rotate():
    # retrieve parameters from html form
    angle = request.form['angle']
    filename = request.form['image']

    # open and process image
    target = os.path.join(APP_ROOT, 'static/images')
    destination = "/".join([target, filename])

    img = Image.open(destination)
    img = img.rotate(-1*int(angle))

    # save and return image
    destination = "/".join([target, 'temp.png'])
    if os.path.isfile(destination):
        os.remove(destination)
    img.save(destination)

    return send_image('temp.png')


# flip filename 'vertical' or 'horizontal'
@app.route("/flip", methods=["POST"])
def flip():

    # retrieve parameters from html form
    if 'horizontal' in request.form['mode']:
        mode = 'horizontal'
    elif 'vertical' in request.form['mode']:
        mode = 'vertical'
    else:
        return render_template("error.html", message="Mode not supported (vertical - horizontal)"), 400
    filename = request.form['image']

    # open and process image
    target = os.path.join(APP_ROOT, 'static/images')
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


# crop filename from (x1,y1) to (x2,y2)
@app.route("/crop", methods=["POST"])
def crop():
    # retrieve parameters from html form
    x1 = int(request.form['x1'])
    y1 = int(request.form['y1'])
    x2 = int(request.form['x2'])
    y2 = int(request.form['y2'])
    filename = request.form['image']

    # open image
    target = os.path.join(APP_ROOT, 'static/images')
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
        return render_template("error.html", message="Crop dimensions not valid"), 400
    return '', 204


# blend filename with stock photo and alpha parameter
@app.route("/blend", methods=["POST"])
def blend():
    # retrieve parameters from html form
    alpha = request.form['alpha']
    filename1 = request.form['image']

    # open images
    target = os.path.join(APP_ROOT, 'static/images')
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
