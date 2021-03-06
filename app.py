#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#


from flask import Flask,flash,Blueprint,render_template,request,redirect,session,url_for,abort,send_file,safe_join
from flask_dance.contrib.twitter import make_twitter_blueprint, twitter
from flask_socketio import SocketIO, emit, send
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
import logging
from logging import Formatter, FileHandler
from forms import *
import os
from models import *
import bcrypt
from werkzeug import secure_filename, FileStorage
from flask_uploads import UploadSet,configure_uploads,IMAGES
from flask_mail import Mail,Message
import datetime
import time
import random
from sqlalchemy.pool import StaticPool
import boto3,botocore
import string
from flask_mongoalchemy import MongoAlchemy
from werkzeug.utils import secure_filename
import config

#-----------------------------------------a-----------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
socketio = SocketIO(app)
bootstrap = Bootstrap(app)
app.config.from_object('config')
app.config.update(dict(
    DEBUG = True,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_PORT = 465,
    MAIL_USE_TLS = False,
    MAIL_USE_SSL = True,
    MAIL_USERNAME = 'skilllauncher7@gmail.com',
    MAIL_PASSWORD = 'skill7launcher'
))
mail = Mail(app)
twitter_blueprint = make_twitter_blueprint(api_key='uQyFwItPPYK9EpXsurufWm52O', api_secret='lpe1StRf9QXhn8hsu2EQfh9KFwAd8hGMmZi7qHzpxZYfwSqh7Y')

# file upload config
photos = UploadSet('photos',IMAGES)
app.config['UPLOADED_PHOTOS_DEST']='static/img'
configure_uploads(app,photos)
app.register_blueprint(twitter_blueprint, url_prefix="/twitter_login")

@app.route('/',methods=['POST','GET'])
def home():
    return redirect(url_for('signin'))

@app.route('/signup',methods=['POST','GET'])
def signup():
    # store hashed password and credentials for POST request
    if request.method == 'POST': # if data is being POSTed
        users = User.query.all()
        for user in users: # looping through the users
            if user.username == request.form['username']:# check if the entered username matches to avoid collisions
                flash('Username already exists. Please pick another one')
                return redirect(url_for('signup'))

            elif len(request.form['password'])<8: # password length check
                flash('Please provide a password which is atleast 8 characters long')
                return redirect(url_for('signup'))

            elif request.form['password']!=request.form['repeat_password']: # check passwords match
                flash('Passwords mismatch. Please try again')
                return redirect(url_for('signup'))
 # if no exception, go here
        hashed_password = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt(10)) # hashing the password with a salt
        user_data= User(email=request.form['email'],username=request.form['username'],password=hashed_password.decode('utf-8'),display_picture="sqr.png")# storing the hashed password in the collection
        user_data.save() # save

        flash('Signup Success!') # flash messages
        return redirect(url_for('signin'))
    # render form for GET
    return render_template('forms/SignUp.html')

@app.route('/signin',methods=['POST','GET'])
def signin():
    # check if hashes match and set session variables
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if bcrypt.hashpw(request.form['password'].encode('utf-8'),user.password.encode('utf-8')) == user.password.encode('utf-8'):
            session['username'] = request.form['username']
            return redirect(url_for('feed'))
        else:
            flash('Incorrect Credentials Entered')
            return redirect(url_for('signin'))
    return render_template('forms/SignIn.html')


@app.route('/twitter')
def twitter_login():
    if not twitter.authorized:
        return redirect(url_for('twitter.login'))
    account_info = twitter.get('account/settings.json')

    if account_info.ok:
        account_info_json = account_info.json()

        return '<h1>Your Twitter name is @{}'.format(account_info_json['screen_name'])

    return '<h1>Request failed!</h1>'


@app.route('/logout')
def logout():
    # clear all session variables
    session.clear()
    return redirect(url_for('signin'))

# Photo Upload route
@app.route('/post',methods=['POST'])
def post():
    # save filename using Upload set object 'photos'
    if request.method == 'POST' and 'photo' in request.files:
        filename = photos.save(request.files['photo'])

        file = request.files['photo']

        if file.filename == '': # check if there's a file enqueued
            return redirect(url_for('feed'))
            flash('No selected photo')
        # save in database
        post = Posts(caption=request.form['caption'],filename=filename,username=session['username'],category=request.form.getlist('category')[0],date=datetime.datetime.utcnow())
        post.save()
        flash('Your new post is up!')
        return redirect(url_for('feed'))
    elif 'photo' not in request.files:
            flash('An error occurred while uploading')
            return redirect(url_for('feed'))

@app.route('/feed')
def feed():
    try:
        if session['username']:
            posts = Posts.query.all() # Get all posts which have been uploaded
            return render_template('pages/feed.html',posts=posts)

    except KeyError:
        flash('You need to login to access your feed')
        return redirect(url_for('signin'))


# Categorization route
@app.route('/category/<category>',methods=['GET','POST'])
def category(category):
    category_posts = Posts.query.filter(Posts.category == category).all()
    return render_template('pages/CategoryPage.html',posts=category_posts,category=category)


#Profile page route
@app.route('/profile/<username>',methods=['POST','GET'])
def profile(username):
    if username == session['username']:
        return redirect(url_for('your_profile'))
    profile_posts = Posts.query.filter(Posts.username == username).all()
    return render_template('pages/Profile.html',posts=profile_posts,username=username)

@app.route('/your_profile',methods=['POST','GET'])
def your_profile():
    posts= Posts.query.filter(Posts.username == session['username']).all()
    return render_template('pages/YourProfile.html',posts=posts,profile_photo=User.query.filter(User.username==session['username']).first().display_picture)

@app.route('/settings',methods=['POST','GET'])
def settings():
    return render_template('pages/settings.html')

#############################################################
#edit profile methods

@app.route('/profile_photo',methods=['POST'])
def profile_photo():
    if request.method =='POST' and 'profilephoto' in request.files:
        filename = photos.save(request.files['profilephoto'])
        file = request.files['profilephoto']
        if file.filename=='':
            flash('Please upload a picture before submission')
            return redirect(url_for('profile_photo'))
        user = User.query.filter(User.username == session['username']).first()
        user.display_picture = filename
        user.save()
        flash('Profile Picture Updated')
        return redirect(url_for('your_profile'))

@app.route('/change_username',methods=['POST'])
def change_username():
    if request.method=='POST':
        if request.form['current_username'] != session['username']:
            flash('Existing username entered incorrectly')
            return redirect(url_for('settings'))
        user = User.query.filter(User.username == session['username']).first()
        posts = Posts.query.filter(Posts.username==session['username']).all()
        for post in posts:
            post.username = request.form['new_username']
            post.save()
        user.username = request.form['new_username']
        user.save()
        session['username'] =  request.form['new_username']
        flash('Username has been changed successfully')
        return redirect(url_for('your_profile'))

@app.route('/change_password',methods=['POST'])
def change_password():
    if request.method=='POST':
        user = User.query.filter(User.username == session['username']).first()
        if bcrypt.hashpw(request.form['current_password'].encode('utf-8'),user.password.encode('utf-8')) == user.password.encode('utf-8'):

            if request.form['new_password'] == request.form['repeat_password']:
                hashed_new_password = bcrypt.hashpw(request.form['new_password'].encode('utf-8'), bcrypt.gensalt(10))
                user.password = hashed_new_password.decode('utf-8')
                user.save()
                flash('Password successfully changed')
                return redirect(url_for('your_profile'))
            else:
                flash('New passwords do not match. Please try again.')
                return redirect(url_for('settings'))

        else:
            flash('Current password has been entered incorrectly')
            return redirect(url_for('settings'))

@app.route('/forgot',methods=['POST','GET'])
def forgot():
    forgot_url = url_for('reset',_external=True)
    if request.method == 'POST':
        users = User.query.all()
        for user in users:
            if user.email == request.form['email']:
                msg = Message('Reset Password',sender='skilllauncher7@gmail.com',recipients=[request.form['email']])
                msg.html = 'Greetings! Follow this link to reset your password'+forgot_url
                mail.send(msg)
                session.clear()
                session['user_email'] = request.form['email']
                flash('A reset confirmation e-mail has been sent to the specified email address')
                return redirect(url_for('home'))
        flash('The provided mail is not a valid email address.')
        return redirect(url_for('forgot'))
    if request.method == 'GET':
        return render_template('forms/forgot.html')

@app.route('/chat',methods=['POST','GET'])
def chat():
    if request.method == 'POST':
        session['interest_current'] = request.form.get('option')
        return render_template('pages/chat.html',messages=Chat.query.filter(Chat.user_interest==request.form.get('option')).all())


@app.route('/chat_interests',methods=['POST','GET'])
def chat_interests():
    return render_template('pages/chat_interests.html')

@app.route('/reset',methods=['POST','GET'])
def reset():
    if request.method=='POST':
        if request.form['password']!=request.form['repeat_password']:
            flash('Passwords do not match')
            return redirect(url_for('reset'))
        hashed_password_new = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt(10))
        data = User.query.filter_by(email=session['email']).first()
        data.password=hashed_password_new
        data.save()
        session.clear()
        flash('Your password has been reset successfully. Please login with the updated credentials.')
        return redirect(url_for('login'))
    else:
        return render_template('forms/reset.html')



##################################
@socketio.on('message')
def handle_message(message):
    print('Message: '+message)
    send(message,broadcast=True)
    message = Chat(message,datetime.datetime.now(),session['username'],session['interest_current'])
    message.save()





###################################
# Error handlers.


@app.errorhandler(500)
def internal_error(error):
    #db_session.rollback()
    return render_template('errors/500.html'), 500


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

if __name__ == '__main__':
    socketio.run(app)

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
