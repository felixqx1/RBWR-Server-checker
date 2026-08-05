import flask
import requests
import json
from dotenv import load_dotenv

load_dotenv(".env")

app = flask.Flask(__name__)

@app.route("/style.css")
def style():
    return flask.send_from_directory("static", "style.css")

@app.route("/", methods=["GET"])
def index():
    return flask.render_template("index.html")

app.run(host="0.0.0.0", port=5000, debug=True)