import hashlib
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

api_key_hash = "621c0599031a0c2a8bae34f1d70048913bb80a548a5dfe149d19d7a362f7d217"

public_server_ids = []
server_ids = []
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

latest_server_data = {}

DEBUG = False

if DEBUG:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
else:
    DATA_DIR = "/data"

def resolve_data_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    norm_path = path.replace("\\", "/")
    if norm_path.startswith("data/"):
        filename = norm_path[5:]
        return os.path.join(DATA_DIR, filename)
    return os.path.join(DATA_DIR, norm_path)

def get_data(path: str, max_retries: int = 5):
    filepath = resolve_data_path(path)
    if not os.path.exists(filepath):
        return {}
    for attempt in range(max_retries):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(0.05)
    return {}

def save_data(data, path: str):
    filepath = resolve_data_path(path)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f)

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
    url = "https://hydrogen.realisticbwr.org/api/public/servers"
    headers = {
        "User-Agent": "RBWR-Server-Checker/1.0"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        current_data = get_data("servers.json")
        found_new_server = False
        for server in response.json()['data']['servers']:
            if server['jobId'] not in server_ids:
                server_ids.append(server['jobId'])
                found_new_server = True

        success = False
        if found_new_server:
            success = update_public_servers()
        
        if success:
            for job_id in list(current_data.keys()):
                if job_id not in public_server_ids:
                    print(f"deleted {job_id}")
                    del current_data[job_id]
            save_data(current_data, "servers.json")

        latest_server_data.update(response.json())

        for server in response.json()['data']['servers']:
            if server['jobId'] not in public_server_ids:
                continue
            current_data = get_data("servers.json")
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
            save_data(current_data, "servers.json")
        current_data = get_data("global.json")
        current_data[str(datetime.now(timezone.utc).isoformat())] = response.json()['data']['stats']
        save_data(current_data, "global.json")


        return True
    else:
        return False

def update_thread():
    while True:
        try:
            print("Updating server data...", flush=True)
            pull_server_data()
        except Exception as e:
            print("update_thread error:", e, flush=True)
        time.sleep(60)

def convert_ISO_to_secs(timestamp_str):
    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    age_seconds = (now - dt).total_seconds()
    return round(age_seconds)

def get_server_state(job_id):
    data = get_data("servers.json")
    if job_id in data:
        return data[job_id]
    return None

def build_server_cards(data):
    cards = []

    if not data:
        return cards

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

def compress(labels, values):
    if len(values) <= 2:
        return list(labels), list(values)

    formatted_labels = [int(label.split()[0]) for label in labels]

    compressed_labels = [labels[0]]
    compressed_values = [values[0]]

    for i in range(1, len(max(formatted_labels, values)) - 1):
        x1, y1 = formatted_labels[i - 1], values[i - 1]
        x2, y2 = formatted_labels[i],     values[i]
        x3, y3 = formatted_labels[i + 1], values[i + 1]

        cross_product = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
        if abs(cross_product) > 1e-6:
            compressed_values.append(values[i])
            compressed_labels.append(labels[i])

    compressed_labels.append(labels[-1])
    compressed_values.append(values[-1])

    return compressed_labels, compressed_values

def build_chart_payload(job_id, snapshots):
    metrics = {
        "APRM": "3,APRM",
        "RTP": "2,RTP",
        "Pressure": "3,Pressure",
        "Reactor Temp": "3,Reactor Temp",
        "ReactorLevel": "3,Reactor Level",
        "Deareator Level": "3,Deareator Level",
        "Hotwell Level": "3,Hotwell Level",
        "TurbineHealth": "2,Turbine Health",
        "GeneratorTemperature": "2,Generator Temperature",
        "Demand": "3,Demand"
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
        units = units.split(",")
        labels = []
        unit1_values = []
        unit2_values = []

        for entry in ordered_snapshots:

            unit1 = entry["state"].get("Unit1", {})
            unit2 = entry["state"].get("Unit2", {})
            labels.append(entry["display_time"])

            if metric == "Demand":
                unit1_values.append(unit1.get("DemandU1", 0))
                unit2_values.append(unit2.get("DemandU2", 0))
            elif units[0] == "2":
                unit2_values.append(unit2.get(metric, 0))
            elif units[0] == "1":
                unit1_values.append(unit1.get(metric, 0))
            elif units[0] == "3":
                unit1_values.append(unit1.get(metric, 0))
                unit2_values.append(unit2.get(metric, 0))

        labels, unit2_values = compress(labels, unit2_values)
        labels, unit1_values = compress(labels, unit1_values) 
        
        if units[0] == "1":
            datasets = [
                {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"}
            ]
        elif units[0] == "2":
            datasets = [
                {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"}
            ]
        else:
            datasets = [
                {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"},
                {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"},
            ]
        
        chart_payload.append({
            "metric": units[1],
            "labels": labels,
            "datasets": datasets,
        })

    return {
        "job_id": job_id,
        "snapshots": ordered_snapshots,
        "charts": chart_payload,
    }

def build_global_chart_payload(snapshots):
    chart_payload = []
    ordered_snapshots = []

    for timestamp, data in sorted(snapshots.items()):
        ordered_snapshots.append({
            "timestamp": timestamp,
            "display_time": f"{convert_ISO_to_secs(timestamp)} seconds ago",
            "data": data,
        })

    labels = []
    unit1_values = []
    unit2_values = []

    datasets = []
    for entry in ordered_snapshots:
        unit1 = entry["data"].get("unit1", {})
        unit2 = entry["data"].get("unit2", {})

        labels.append(entry["display_time"])

        unit1_values.append(unit1.get("megawatts", 0))
        unit2_values.append(unit2.get("megawatts", 0))

        labels, unit2_values = compress(labels, unit2_values)
        labels, unit1_values = compress(labels, unit1_values) 
        
        datasets = [
            {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"},
            {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"},
        ]        

    chart_payload.append({
        "metric": "global MW",
        "labels": labels,
        "datasets": datasets,
    })

    return {
        "snapshots": ordered_snapshots,
        "charts": chart_payload,
    }

@app.route("/servers")
def servers():
    data = get_data("servers.json")
    return flask.render_template("servers.html", servers=build_server_cards(data))

@app.route("/api/servers/refresh", methods=["POST"])
def refresh_servers():
    request_api_key = flask.request.headers.get("X-API-KEY")

    if not request_api_key:
        return flask.abort(401)
    
    hashed_api_key = hashlib.sha256(request_api_key.encode()).hexdigest()
    
    if hashed_api_key != api_key_hash:
        return flask.abort(401)
    
    success = pull_server_data()
    return flask.jsonify({"success": success})

@app.route("/api/servers/latest", methods=["GET"])
def get_latest_server_data():
    request_api_key = flask.request.headers.get("X-API-KEY")

    if not request_api_key:
        return flask.abort(401)
    
    hashed_api_key = hashlib.sha256(request_api_key.encode()).hexdigest()
    
    if hashed_api_key != api_key_hash:
        return flask.abort(401)
    
    if not latest_server_data:
        return flask.jsonify({"success": False, "data": None})
    
    return flask.jsonify(latest_server_data)

@app.route("/servers/<job_id>")
def server_detail(job_id):
    data = get_data("servers.json")
    snapshots = data.get(job_id)
    if snapshots is None:
        return flask.abort(404)
    payload = build_chart_payload(job_id, snapshots)
    
    server = {}

    if latest_server_data:
        for server in latest_server_data['data']['servers']:
            if server['jobId'] == job_id:
                break

    if not server:
        summary = {
            "scram_reason_u1": "N/A",
            "scram_reason_u2": "N/A",
            "time_to_next_demand": 0,
        }
        return flask.render_template("server_detail.html", **payload, **summary)
    
    scram_reasonU1 = server['state']['Unit1']['SCRAMreason']
    scram_reasonU2 = server['state']['Unit2']['SCRAMreason']
    dmand_left_data = server['state']['Unit1']['Demand Time Left']
    dmand_next1 = server['state']['Unit1']['NextDemandU1']
    dmand_next2 = server['state']['Unit2']['NextDemandU2']

    next_demand = dmand_next1 + dmand_next2

    elapsed = time.time() - datetime.fromisoformat(server['lastHeartbeat']).timestamp()

    dmand_left = max(0.0, dmand_left_data - elapsed)

    summary = {
        "scram_reason_u1": scram_reasonU1,
        "scram_reason_u2": scram_reasonU2,
        "time_to_next_demand": dmand_left,
        "next_demand": next_demand,
        "dmandU1": dmand_next1,
        "dmandU2": dmand_next2,
    }

    return flask.render_template("server_detail.html", **payload, **summary)

@app.route("/", methods=["GET"])
def index():
    data = get_data("global.json")
    if data is None:
        return flask.abort(404)
    payload = build_global_chart_payload(data)
    return flask.render_template("index.html", **payload)

@app.context_processor
def inject_now():
    return {'now': datetime.now(tz=timezone.utc)}


if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    thread = Thread(target=update_thread, daemon=True)
    thread.start()
elif not DEBUG:
    thread = Thread(target=update_thread, daemon=True)
    thread.start()

app.run(host="0.0.0.0", port=5000, debug=DEBUG)