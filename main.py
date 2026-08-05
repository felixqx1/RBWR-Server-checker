import flask
import requests
import json
from threading import Thread
from dotenv import load_dotenv
import time
import os

load_dotenv(".env")

app = flask.Flask(__name__)

public_server_ids = []


def get_server_data():
    f = open("servers.json", "r")
    data = json.load(f)
    f.close()
    return data

def save_server_data(data):
    f = open("servers.json", "w")
    json.dump(data, f, indent=4)
    f.close()

def update_public_servers():
    url = "https://games.roblox.com/v1/games/11765852158/servers/Public?limit=100"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        public_server_ids.clear()
        for server in data['data']:
            public_server_ids.append(server['id'])
        print(f"Updated public server IDs: {public_server_ids}")
        return True
    else:
        print(f"Failed to update public server IDs. Status code: {response.status_code}")
        return False

def pull_server_data():
    update_public_servers()
    url = "https://hydrogen.realisticbwr.org/api/public/servers"
    headers = {
        "User-Agent": "RBWR-Server-Checker/1.0"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        for server in response.json()['data']['servers']:
            if server['jobId'] not in public_server_ids:
                continue
            current_data = get_server_data()
            if not server['jobId'] in current_data:
                current_data[server['jobId']] = {}

            current_data[server['jobId']][server['lastHeartbeat']]

            current_data[server['jobId']][server['lastHeartbeat']] = server['state']
            save_server_data(current_data)
        return True
    else:
        return None

def update_thread():
    while True:
        print("Updating server data...")
        pull_server_data()
        time.sleep(60)

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

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    thread = Thread(target=update_thread, daemon=True)
    thread.start()
app.run(host="0.0.0.0", port=5000, debug=True)