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
purge = [
    "Reactor Scram State",
    "Startup XFMR",
    "DoAutoScramU1",
    "DieselRPM",
    "Turbine RPM",
    "FWP1",
    "FWP2",
    "Recirc1",
    "Recirc2",
    "APRM Setpoint",
    "AutoPressure",
    "NextDemandU1",
    "BypassTurbineAutoTrip",
    "Vibrations",
    "Fuel Burn (default 0.54)",
    "Avg. Rod",
    "TurbineTrip",
    "TotalPowerGenerated",
    "Offsite Power",
    "StartupUnit1",
    "BusA",
    "BusB",
    "TurbineTrip",
    "Disk Ruptured",
    "RPS Trip State B",
    "RPS Trip State A",
    "Turbine RPM",
    "AutoPressure",
    "TRIPreason",
    "PointsPerSecond",
    "DCBus",
    "StartupUnit2",
    "SCRAMreason",
    "DiffPressure",
    "NextDemandU2",
    "DoAutoScramU2",
]

def get_server_data():
    if not os.path.exists("servers.json"):
        return {}
    with open("servers.json", "r") as f:
        data = json.load(f)
    return data

def save_server_data(data):
    with open("servers.json", "w") as f:
        json.dump(data, f, indent=4)

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

            state = server['state']
            del state["Misc"]

            for key, var in state["Unit1"].items():
                if isinstance(var, (str, bool)):
                    continue
                state["Unit1"][key] = round(var, 2)
            for key, var in state["Unit2"].items():
                if isinstance(var, (str, bool)):
                    continue
                state["Unit2"][key] = round(var, 2)

            for key in purge:
                if key in state["Unit1"]:
                    del state["Unit1"][key]
                if key in state["Unit2"]:
                    del state["Unit2"][key]

            current_data[server['jobId']][server['lastHeartbeat']] = state
            save_server_data(current_data)
        return True
    else:
        return None

def update_thread():
    while True:
        print("Updating server data...")
        pull_server_data()
        time.sleep(60)

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