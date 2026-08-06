import flask
import requests
import json
from threading import Thread
from dotenv import load_dotenv
import time
import os
from datetime import datetime, timezone

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
    "Demand Time Left",
    "CasingTemperature",
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

            for unit in ("Unit1", "Unit2"):
                state[unit] = {
                    k: (round(v, 2) if not isinstance(v, (str, bool)) else v)
                    for k, v in state[unit].items()
                    if k not in purge
                }

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

def convert_ISO_to_secs(timestamp_str):
    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    age_seconds = (now - dt).total_seconds()
    return round(age_seconds)

def get_server_state(job_id):
    data = get_server_data()
    if job_id in data:
        return data[job_id]
    return None

def build_server_cards(data):
    cards = []
    for job_id, snapshots in sorted(data.items()):
        if not snapshots:
            continue
        latest_timestamp = max(snapshots.keys())
        latest_state = snapshots[latest_timestamp]
        unit1 = latest_state.get("Unit1", {})
        unit2 = latest_state.get("Unit2", {})
        cards.append({
            "job_id": job_id,
            "latest_timestamp": f"{convert_ISO_to_secs(latest_timestamp)} seconds ago",
            "snapshot_count": len(snapshots),
            "unit1": {
                "demand_time_left": unit1.get("Demand Time Left", 0),
                "aprm": unit1.get("APRM", 0),
                "reactor_temp": unit1.get("Reactor Temp", 0),
            },
            "unit2": {
                "demand_time_left": unit2.get("Demand Time Left", 0),
                "aprm": unit2.get("APRM", 0),
                "reactor_temp": unit2.get("Reactor Temp", 0),
            },
        })
    return cards

def build_chart_payload(job_id, snapshots):
    metrics = {
        "APRM": 3,
        "RTP": 2,
        "Pressure": 3,
        "Reactor Temp": 3,
        "ReactorLevel": 3,
        "Deareator Level": 3,
        "Hotwell Level": 3,
        "TurbineHealth": 2,
        "GeneratorTemperature": 2,
    }
    chart_payload = []
    ordered_snapshots = []

    for timestamp, state in sorted(snapshots.items()):
        ordered_snapshots.append({
            "timestamp": timestamp,
            "display_time": f"{convert_ISO_to_secs(timestamp)} seconds ago",
            "state": state,
        })

    for metric, units in metrics.items():
        labels = []
        unit1_values = []
        unit2_values = []
        
        for entry in ordered_snapshots:
            unit1 = entry["state"].get("Unit1", {})
            unit2 = entry["state"].get("Unit2", {})
            labels.append(entry["display_time"])
            if units == 2:
                unit2_values.append(unit2.get(metric, 0))
            elif units == 1:
                unit1_values.append(unit1.get(metric, 0))
            else:
                unit1_values.append(unit1.get(metric, 0))
                unit2_values.append(unit2.get(metric, 0))

        if units == 1:
            datasets = [
                {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"}
            ]
        elif units == 2:
            datasets = [
                {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"}
            ]
        else:
            datasets = [
                {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"},
                {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"},
            ]
        
        chart_payload.append({
            "metric": metric,
            "labels": labels,
            "datasets": datasets,
        })

    return {
        "job_id": job_id,
        "snapshots": ordered_snapshots,
        "charts": chart_payload,
    }

@app.route("/api/servers/<job_id>")
def server_data(job_id):
    state = get_server_state(job_id)
    if state is None:
        return flask.jsonify({"error": "Server not found"}), 404
    return flask.jsonify(state)


@app.route("/servers")
def servers():
    data = get_server_data()
    return flask.render_template("servers.html", servers=build_server_cards(data))

@app.route("/servers/<job_id>")
def server_detail(job_id):
    data = get_server_data()
    snapshots = data.get(job_id)
    if snapshots is None:
        return flask.abort(404)
    payload = build_chart_payload(job_id, snapshots)
    return flask.render_template("server_detail.html", **payload)

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