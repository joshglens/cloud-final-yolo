import base64
import io

from flask import Flask, Response, render_template, request, url_for, redirect, flash, abort, jsonify
from markupsafe import escape
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import os

import pandas as pd
import random
import matplotlib
#matplotlib.use('Agg')
matplotlib.rcParams['figure.figsize'] = (14, 10)
import matplotlib.pyplot as plt
import numpy as np
import time
import os
import seaborn as sns
from ultralytics import YOLO
from PIL import Image
import cv2

# Extended from https://www.geeksforgeeks.org/how-to-add-authentication-to-your-app-with-flask-login/
# Additional resources: Flask documentation

current_directory = os.getcwd()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SECRET_KEY"] = "abc"
db = SQLAlchemy()

login_manager = LoginManager()
login_manager.init_app(app)


class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)


db.init_app(app)

with app.app_context():
    db.create_all()

metrics = {
    'Total Inference Time': 0,
    'Total Inference Count': 0,
    'Total Objects Spotted': 0,
    'Times User Data Reset': 0,
    'Times User Data Streamed': 0,
    'Times Admin Data Streamed': 0,
    'Times Metrics Streamed': 0
}


def add_service_user():
    # Check if the service user exists
    if Users.query.filter_by(username="admin").first() is None:
        user = Users(username="admin", password="password")
        db.session.add(user)
        db.session.commit()
        print("Service user created!")
    else:
        print("Service user already exists.")

def populate_tracking(all_users, base_df):
    for user in all_users:
        new_row = {col: 0 for col in base_df.columns}
        new_row["user"] = user.username
        base_df.loc[len(base_df)] = new_row

@login_manager.user_loader
def loader_user(user_id):
    return Users.query.get(user_id)

@app.route('/register', methods=["GET", "POST"])
def register():
    global main_df
    if request.method == "POST":
        username = request.form.get("username")

        user = Users(username=username,
                     password=request.form.get("password"))

        existing_user = Users.query.filter_by(username=username).first()

        if existing_user:
            # Username already exists, redirect to invalid page
            flash('Username already exists, please choose another one.', 'error')
            return render_template("invalid.html", message='Username already exists, please choose another one.')

        new_row = {col: 0 for col in main_df.columns}
        new_row["user"] = user.username
        main_df.loc[len(main_df)] = new_row
        print(main_df)

        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("sign_up.html")




@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Users.query.filter_by(
            username=request.form.get("username")).first()
        if user and user.password == request.form.get("password"):
            login_user(user)
            return redirect(url_for("home"))
        else:
            return render_template("invalid.html", message='Invalid username or password!')
    return render_template("login.html")




@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/")
def home():
    if current_user.is_authenticated:
        greeting = f"Welcome, {current_user.username}!"
    else:
        greeting = "Welcome, Guest!"
    return render_template("home.html", greeting=greeting)

@app.route('/special-service-page')
@login_required
def special_service_page():
    if current_user.is_authenticated:
        if current_user.username=="admin":
            return render_template('service_user_page.html')
        else:
            abort(403)
    abort(403)

@app.route('/stream_admin')
@login_required
def stream_admin():
    global main_df
    if current_user.is_authenticated and current_user.username == "admin":
        def generate():
            while True:
                all_tracks = main_df.to_html().replace('\n', '').replace("\r", "")
                yield f"data:{all_tracks}\n\n"
                metrics['Times Admin Data Streamed'] += 1
                time.sleep(1)
        return Response(generate(), mimetype='text/event-stream')
    else:
        abort(403)

@app.route('/stream_metrics')
@login_required
def stream_metrics():
    if current_user.is_authenticated and current_user.username == "admin":
        def generate():
            while True:
                metrics['Times Metrics Streamed'] += 1
                if metrics['Total Objects Spotted'] > 0:
                    metrics['Average Inference Time'] = metrics['Total Inference Time'] / metrics['Total Inference Count']
                yield f"data:{metrics}\n\n"
                time.sleep(1)
        return Response(generate(), mimetype='text/event-stream')
    else:
        abort(403)

@app.route('/stream_user')
@login_required
def stream_user():
    global main_df
    if current_user.is_authenticated:
        username = current_user.username
        def generate():
            while True:
                user_full_df = main_df.loc[main_df.user == username]
                user_df = user_full_df.loc[:, (user_full_df != 0).all()]
                user_tracks = user_df.to_html().replace('\n', '').replace("\r", "")
                yield f"data:{user_tracks}\n\n"
                metrics['Times User Data Streamed'] += 1
                time.sleep(1)
        return Response(generate(), mimetype='text/event-stream')
    else:
        abort(403)

@app.route('/reset_data')
@login_required
def reset_data():
    global main_df
    if current_user.is_authenticated:
        username = current_user.username
        clear_row = {col: 0 for col in main_df.columns}
        clear_row["user"] = username
        main_df.loc[main_df["user"]==username, clear_row.keys()] = list(clear_row.values())
        metrics['Times User Data Reset'] += 1
        return jsonify({'status': 'success'})
    else:
        abort(403)

def update_record(user, detections, df):
    for detect in detections:
        metrics['Total Objects Spotted'] += 1
        df.loc[df['user'] == user, detect] = int(df.loc[df['user'] == user, detect].item()) + 1

@app.route('/upload', methods=['POST'])
def upload():
    global main_df
    image = request.files['image']
    if image:
        image_bytes = image.read()
        image_pil = Image.open(io.BytesIO(image_bytes))
        #image_np = np.array(image_pil)
        time_before = time.time()
        results = model.track(image_pil, save=False, imgsz=640, conf=0.2,
                              persist=True)
        time_after = time.time()
        metrics['Total Inference Time'] += time_after - time_before
        metrics['Total Inference Count'] += 1
        annotated_frame = results[0].plot()
        tracks = results[0].boxes.cls.tolist()

        detections = list(map(results[0].names.get, tracks))

        if current_user.is_authenticated:
            update_record(current_user.username, detections, main_df)

        annotated_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        image_pil_processed = Image.fromarray(annotated_frame)
        buffered = io.BytesIO()
        image_pil_processed.save(buffered, format="PNG")
        encoded_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return jsonify({"image": encoded_image, "text": f"{detections}"})

    return jsonify({'status': 'success'})

@app.route('/track')
@login_required
def track():
    return render_template('track.html')



model = YOLO('yolov8s.pt')
baseline_results = model.track('https://images.hgmsites.net/hug/traffic_100183617_h.jpg', save=False, imgsz=320, conf=0.2, tracker="bytetrack.yaml")

main_df = pd.DataFrame(columns=(["user"] + list(baseline_results[0].names.values())))
print(main_df.head())


with app.app_context():
    add_service_user()
    all_users = Users.query.all()
    populate_tracking(all_users, main_df)

print(main_df.head())
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
