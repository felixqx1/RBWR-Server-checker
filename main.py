import hashlib
import flask
import requests
import json
from threading import Thread
from dotenv import load_dotenv
import time
import os
from datetime import datetime, timezone
from werkzeug.exceptions import HTTPException
import traceback

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
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            public_server_ids.clear()
            for server in data.get('data', []):
                public_server_ids.append(server['id'])
            print(f"Updated public server IDs: {public_server_ids}")
            return True
        else:
            print(f"Failed to update public server IDs. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error updating public servers: {e}")
        return False

def pull_server_data():
    url = "https://hydrogen.realisticbwr.org/api/public/servers"
    headers = {
        "User-Agent": "RBWR-Server-Checker/1.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except Exception as e:
        print(f"Error connecting to server API: {e}")
        return False

    if response.status_code == 200:
        current_data = get_data("servers.json")
        found_new_server = False
        resp_json = response.json()
        servers_list = resp_json.get('data', {}).get('servers', [])

        for server in servers_list:
            if server['jobId'] not in server_ids:
                server_ids.append(server['jobId'])
                found_new_server = True

        success = False
        if found_new_server:
            success = update_public_servers()

        rbwr_api_ids = [s['jobId'] for s in servers_list]
        
        if success:
            for job_id in list(current_data.keys()):
                if job_id not in public_server_ids and job_id not in rbwr_api_ids:
                    print(f"deleted {job_id}")
                    del current_data[job_id]
            save_data(current_data, "servers.json")

        latest_server_data.update(resp_json)

        for server in servers_list:
            if public_server_ids and server['jobId'] not in public_server_ids:
                continue

            if server['jobId'] not in current_data:
                current_data[server['jobId']] = {}

            state = server['state'].copy()
            del state["Misc"]

            for unit in ("Unit1", "Unit2"):
                state[unit] = {
                    k: (round(v, 2) if not isinstance(v, (str, bool)) else v)
                    for k, v in state[unit].items()
                    if k not in purge
                }

            current_data[server['jobId']][server['lastHeartbeat']] = state
            save_data(current_data, "servers.json")
        
        global_data = get_data("global.json")
        global_data[str(datetime.now(timezone.utc).isoformat())] = resp_json.get('data', {}).get('stats', {})
        save_data(global_data, "global.json")

        return True
    else:
        return False

def update_thread():
    while True:
        try:
            print("Updating server data...", flush=True)
            pull_server_data()
        except Exception as e:
            print(f"update_thread error: {type(e).__name__}: {e}\n{traceback.format_exc()}", flush=True)
        time.sleep(60)

def convert_ISO_to_secs(timestamp_str):
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_seconds = (now - dt).total_seconds()
        return round(age_seconds)
    except Exception:
        return 0

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

def parse_label_seconds(label, fallback_idx=0):
    try:
        if isinstance(label, (int, float)):
            return float(label)
        return float(str(label).split()[0])
    except Exception:
        return float(fallback_idx)

def compress(labels, values):
    if not labels or not values or len(values) <= 2 or len(labels) != len(values):
        return list(labels), list(values)

    formatted_labels = [parse_label_seconds(label, i) for i, label in enumerate(labels)]

    compressed_labels = [labels[0]]
    compressed_values = [values[0]]

    for i in range(1, len(values) - 1):
        x1, y1 = formatted_labels[i - 1], values[i - 1]
        x2, y2 = formatted_labels[i],     values[i]
        x3, y3 = formatted_labels[i + 1], values[i + 1]

        try:
            cross_product = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
        except Exception:
            cross_product = 1.0

        if abs(cross_product) > 1e-6:
            compressed_values.append(values[i])
            compressed_labels.append(labels[i])

    compressed_labels.append(labels[-1])
    compressed_values.append(values[-1])

    return compressed_labels, compressed_values

def compress_multi(labels, *series_list):
    if not series_list:
        return labels

    num_points = len(labels)
    if num_points <= 2:
        return (list(labels), *(list(s) for s in series_list))

    for s in series_list:
        if len(s) != num_points:
            return (list(labels), *(list(s) for s in series_list))

    formatted_labels = [parse_label_seconds(label, i) for i, label in enumerate(labels)]

    compressed_labels = [labels[0]]
    compressed_series = [[s[0]] for s in series_list]

    for i in range(1, num_points - 1):
        keep_point = False
        for s in series_list:
            x1, y1 = formatted_labels[i - 1], s[i - 1]
            x2, y2 = formatted_labels[i],     s[i]
            x3, y3 = formatted_labels[i + 1], s[i + 1]

            try:
                cross_product = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
            except Exception:
                cross_product = 1.0

            if abs(cross_product) > 1e-6:
                keep_point = True
                break

        if keep_point:
            compressed_labels.append(labels[i])
            for idx, s in enumerate(series_list):
                compressed_series[idx].append(s[i])

    compressed_labels.append(labels[-1])
    for idx, s in enumerate(series_list):
        compressed_series[idx].append(s[-1])

    return (compressed_labels, *compressed_series)

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

    if not snapshots:
        return {
            "job_id": job_id,
            "snapshots": [],
            "charts": [],
        }

    for timestamp, state in sorted(snapshots.items()):
        ordered_snapshots.append({
            "timestamp": timestamp,
            "display_time": f"{convert_ISO_to_secs(timestamp)} seconds ago",
            "state": state,
        })

    for metric, units in metrics.items():
        units_spec = units.split(",")
        unit_type = units_spec[0]
        metric_title = units_spec[1]

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
            elif unit_type == "2":
                unit2_values.append(unit2.get(metric, 0))
            elif unit_type == "1":
                unit1_values.append(unit1.get(metric, 0))
            elif unit_type == "3":
                unit1_values.append(unit1.get(metric, 0))
                unit2_values.append(unit2.get(metric, 0))

        if unit_type == "1":
            labels, unit1_values = compress(labels, unit1_values)
            datasets = [
                {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"}
            ]
        elif unit_type == "2":
            labels, unit2_values = compress(labels, unit2_values)
            datasets = [
                {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"}
            ]
        else:
            labels, unit1_values, unit2_values = compress_multi(labels, unit1_values, unit2_values)
            datasets = [
                {"label": "Unit 1", "data": unit1_values, "borderColor": "#3b82f6"},
                {"label": "Unit 2", "data": unit2_values, "borderColor": "#f59e0b"},
            ]
        
        chart_payload.append({
            "metric": metric_title,
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

    if not snapshots:
        return {
            "snapshots": [],
            "charts": [],
        }

    for timestamp, data in sorted(snapshots.items()):
        ordered_snapshots.append({
            "timestamp": timestamp,
            "display_time": f"{convert_ISO_to_secs(timestamp)} seconds ago",
            "data": data,
        })

    labels = []
    unit1_values = []
    unit2_values = []

    for entry in ordered_snapshots:
        data_entry = entry.get("data", {})
        unit1 = data_entry.get("unit1", {})
        unit2 = data_entry.get("unit2", {})

        labels.append(entry["display_time"])
        unit1_values.append(unit1.get("megawatts", 0))
        unit2_values.append(unit2.get("megawatts", 0))

    if labels:
        labels, unit1_values, unit2_values = compress_multi(labels, unit1_values, unit2_values)

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

def is_api_request():
    return flask.request.path.startswith("/api/") or (
        flask.request.accept_mimetypes.accept_json and not flask.request.accept_mimetypes.accept_html
    )

@app.errorhandler(400)
def bad_request_error(error):
    if is_api_request():
        return flask.jsonify({
            "error": "Bad Request",
            "message": getattr(error, "description", "The request was invalid or malformed."),
            "status_code": 400
        }), 400
    return flask.render_template(
        "error.html",
        status_code=400,
        error_title="Bad Request",
        error_message="The request sent to the server could not be processed due to invalid parameters.",
        error_type="400 - Bad Request"
    ), 400

@app.errorhandler(401)
def unauthorized_error(error):
    if is_api_request():
        return flask.jsonify({
            "error": "Unauthorized",
            "message": getattr(error, "description", "Authentication required or invalid API key."),
            "status_code": 401
        }), 401
    return flask.render_template(
        "error.html",
        status_code=401,
        error_title="Unauthorized Access",
        error_message="Valid authentication credentials (X-API-KEY header) are required to access this resource.",
        error_type="401 - Unauthorized"
    ), 401

@app.errorhandler(403)
def forbidden_error(error):
    if is_api_request():
        return flask.jsonify({
            "error": "Forbidden",
            "message": getattr(error, "description", "You do not have permission to access this resource."),
            "status_code": 403
        }), 403
    return flask.render_template(
        "error.html",
        status_code=403,
        error_title="Access Forbidden",
        error_message="You do not have permission to access this resource.",
        error_type="403 - Forbidden"
    ), 403

@app.errorhandler(404)
def not_found_error(error):
    if is_api_request():
        return flask.jsonify({
            "error": "Not Found",
            "message": getattr(error, "description", "The requested resource could not be found."),
            "status_code": 404
        }), 404
    return flask.render_template(
        "error.html",
        status_code=404,
        error_title="Page or Server Not Found",
        error_message="The requested job ID or page could not be located. It may have expired or has been removed.",
        error_type="404 - Not Found"
    ), 404

@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f"Internal server error: {error}", exc_info=True)
    if is_api_request():
        return flask.jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected server error.",
            "status_code": 500
        }), 500
    return flask.render_template(
        "error.html",
        status_code=500,
        error_title="Internal Server Error",
        error_message="An unexpected issue occurred.",
        error_type="500 - Server Error",
        show_retry=True
    ), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    if isinstance(e, HTTPException):
        return e
    app.logger.error(f"Unhandled exception on {flask.request.path}: {e}", exc_info=True)
    if is_api_request():
        return flask.jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred.",
            "status_code": 500
        }), 500
    return flask.render_template(
        "error.html",
        status_code=500,
        error_title="Internal Server Error",
        error_message="A server exception was encountered while rendering this page.",
        error_type="500 - Exception Caught",
        show_retry=True
    ), 500

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
    
    try:
        payload = build_chart_payload(job_id, snapshots)
    except Exception as e:
        app.logger.error(f"Error building chart payload for job_id {job_id}: {e}", exc_info=True)
        return flask.abort(500)
    
    server = None
    if latest_server_data:
        for s in latest_server_data.get('data', {}).get('servers', []):
            if s.get('jobId') == job_id:
                server = s
                break

    if not server:
        summary = {
            "scram_reason_u1": "N/A",
            "scram_reason_u2": "N/A",
            "time_to_next_demand": 0,
            "next_demand": "N/A",
            "dmandU1": "N/A",
            "dmandU2": "N/A",
        }
        return flask.render_template("server_detail.html", **payload, **summary)
    
    unit1_state = server.get('state', {}).get('Unit1', {})
    unit2_state = server.get('state', {}).get('Unit2', {})

    scram_reasonU1 = unit1_state.get('SCRAMreason', 'N/A')
    scram_reasonU2 = unit2_state.get('SCRAMreason', 'N/A')
    dmand_left_data = unit1_state.get('Demand Time Left', 0)
    dmand_next1 = unit1_state.get('NextDemandU1', 0)
    dmand_next2 = unit2_state.get('NextDemandU2', 0)

    next_demand = dmand_next1 + dmand_next2

    try:
        elapsed = time.time() - datetime.fromisoformat(server['lastHeartbeat'].replace("Z", "+00:00")).timestamp()
    except Exception:
        elapsed = 0

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