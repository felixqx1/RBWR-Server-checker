import flask
import requests
import json
from dotenv import load_dotenv

load_dotenv(".env")

app = flask.Flask(__name__)

def pull_server_data():
    url = "https://hydrogen.realisticbwr.org/api/public/servers"
    headers = {
        "User-Agent": "RBWR-Server-Checker/1.0"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        FO
    else:
        return None


@app.route("/api/servers", methods=["GET"])
def api_servers():
    data = pull_server_data()
    if data is not None:
        return flask.jsonify(data)
    else:
        return flask.jsonify({"error": "Failed to fetch server data"}), 500

@app.route("/style.css")
def style():
    return flask.send_from_directory("static", "style.css")

@app.route("/", methods=["GET"])
def index():
    return flask.render_template("index.html")

app.run(host="0.0.0.0", port=5000, debug=True)