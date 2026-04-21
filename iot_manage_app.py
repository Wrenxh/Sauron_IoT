import os
from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

# --- Load Secrets ---
load_dotenv() 

MONGO_URI = os.getenv("MONGO_URI")
API_KEY = os.getenv("SAURON_API_KEY", "fallback_key_if_missing")

app = Flask(__name__)

# --- MongoDB Setup ---
client = MongoClient(MONGO_URI)
db = client['SauronTower1']
devices_collection = db['devices']
logs_collection = db['device_logs']
firmware_collection = db['firmware_versions']
commands_collection = db['command_queue'] 

# --- API Authentication Bouncer ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get("X-Api-Key") == API_KEY:
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Unauthorized. Sauron does not recognize this key."}), 401
    return decorated_function

# --- API Routes ---

@app.route('/api/device/checkin', methods=['POST'])
@require_api_key
def device_checkin():
    data = request.get_json()
    if not data or 'device_name' not in data:
        return jsonify({"error": "Missing device_name"}), 400

    device_name = data.get("device_name")
    
    checkin_log = {
        "device_name": device_name,
        "battery": data.get("battery"),
        "temperature": data.get("temp"),
        "ip_address": request.remote_addr,
        "timestamp": datetime.utcnow()
    }

    try:
        logs_collection.insert_one(checkin_log)
        devices_collection.update_one(
            {"device_name": device_name},
            {"$set": {"last_seen": datetime.utcnow(), "status": "online", "last_ip": request.remote_addr}},
            upsert=True
        )
        return jsonify({"message": "Sauron acknowledges your presence."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/device/list', methods=['GET'])
@require_api_key
def get_device_list():
    try:
        all_devices = list(devices_collection.find({}, {"_id": 0, "device_name": 1}))
        device_names = [doc["device_name"] for doc in all_devices if "device_name" in doc]
        return jsonify({"devices": device_names}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/device/update_firmware', methods=['POST'])
@require_api_key
def update_firmware():
    data = request.get_json()
    device_name = data.get("device_name")
    new_version = data.get("new_version")

    if not device_name or not new_version:
        return jsonify({"error": "Missing data"}), 400

    try:
        devices_collection.update_one(
            {"device_name": device_name},
            {"$set": {"version": new_version}}
        )
        return jsonify({"status": "success", "message": f"{device_name} updated to {new_version}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/device/add', methods=['POST'])
@require_api_key
def add_device():
    data = request.get_json()
    device_name = data.get("device_name", "").strip()
    version = data.get("version", "").strip()

    if not device_name:
        return jsonify({"error": "Device name cannot be empty."}), 400

    if devices_collection.find_one({"device_name": device_name}):
        return jsonify({"error": "A device with this name already exists."}), 409

    try:
        new_device = {
            "device_name": device_name,
            "version": version if version else "Unknown",
            "status": "offline",
            "battery": "N/A",
            "temperature": "N/A"
        }
        devices_collection.insert_one(new_device)
        
        if not firmware_collection.find_one({"model": device_name}):
            firmware_collection.insert_one({
                "model": device_name, 
                "latest_version": version if version else "1.0.0"
            })

        return jsonify({"status": "success", "message": f"{device_name} added successfully."}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/device/remove', methods=['POST'])
@require_api_key
def remove_device():
    data = request.get_json()
    device_name = data.get("device_name")

    if not device_name:
        return jsonify({"error": "Missing device_name"}), 400

    try:
        result = devices_collection.delete_one({"device_name": device_name})
        if result.deleted_count == 1:
            return jsonify({"status": "success", "message": f"{device_name} removed."}), 200
        else:
            return jsonify({"error": "Device not found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/probe/trigger_scan', methods=['POST'])
@require_api_key
def trigger_scan():
    try:
        commands_collection.update_one(
            {"target": "lan_probe"}, 
            {"$set": {"action": "scan_lan", "timestamp": datetime.utcnow()}},
            upsert=True
        )
        return jsonify({"status": "success", "message": "Scan command queued."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/probe/poll', methods=['GET'])
@require_api_key
def poll_commands():
    try:
        cmd = commands_collection.find_one_and_delete({"target": "lan_probe", "action": "scan_lan"})
        if cmd:
            return jsonify({"command": "scan_lan"}), 200
        else:
            return jsonify({"command": "sleep"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Homepage Route ---
@app.route('/')
def homepage():
    all_devices = list(devices_collection.find().sort("last_seen", -1))
    firmware_docs = firmware_collection.find()
    LATEST_FIRMWARE = {doc['model']: doc['latest_version'] for doc in firmware_docs}

    def format_time(dt):
        return dt.strftime('%b %d, %H:%M:%S') if dt else "Never"

    html_page = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sauron Hub | Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <meta http-equiv="refresh" content="10"> 
        <style>
            body { background-color: #f4f6f9; color: #333; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
            .navbar { background-color: #2c3e50; }
            .navbar-brand { color: #ecf0f1 !important; font-weight: 600; letter-spacing: 1px; }
            .card { border: none; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 24px; }
            .card-header { background-color: white; border-bottom: 1px solid #edf2f7; padding: 15px 20px; border-radius: 10px 10px 0 0 !important; font-weight: 600; color: #2c3e50; }
            .table-container { padding: 0; }
            .table th { background-color: #f8fafc; color: #64748b; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #e2e8f0; }
            .table td { vertical-align: middle; padding: 12px 20px; }
            .device-name { font-weight: 600; color: #1e293b; }
            .badge { padding: 6px 10px; font-weight: 600; letter-spacing: 0.3px; }
            .btn-action { transition: all 0.2s; }
            .btn-action:hover { transform: translateY(-2px); }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg mb-4">
            <div class="container-fluid px-4">
                <a class="navbar-brand" href="#"><i class="bi bi-eye-fill me-2 text-info"></i>Sauron Command Center</a>
                <button class="btn btn-info btn-sm text-white fw-bold btn-action" onclick="triggerLanScan()">
                    <i class="bi bi-radar me-1"></i> Run LAN Scan
                </button>
            </div>
        </nav>

        <div class="container-fluid px-4">
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><i class="bi bi-hdd-network me-2"></i>Active IoT Devices</span>
                    <span class="badge bg-secondary text-light fw-normal"><i class="bi bi-arrow-repeat me-1"></i>Auto-refreshing</span>
                </div>
                <div class="card-body table-container table-responsive">
                    <table class="table table-hover mb-0">
                        <thead>
                            <tr>
                                <th class="ps-4">Device Target</th>
                                <th>Status</th>
                                <th>Telemetry</th>
                                <th>Firmware Integrity</th>
                                <th>Last Ping (UTC)</th>
                                <th class="text-end pe-4">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
    """

    for dev in all_devices:
        name = dev.get('device_name', 'Unknown')
        status = dev.get('status', 'offline')
        battery = dev.get('battery', 'N/A')
        temp = dev.get('temperature', 'N/A')
        current_version = dev.get('version', 'Unknown')
        last_seen = format_time(dev.get('last_seen'))
        
        # Status styling
        if status == "online":
            status_badge = '<span class="badge bg-success-subtle text-success border border-success-subtle rounded-pill"><i class="bi bi-circle-fill me-1" style="font-size: 8px;"></i>ONLINE</span>'
        else:
            status_badge = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle rounded-pill"><i class="bi bi-circle-fill me-1" style="font-size: 8px;"></i>OFFLINE</span>'

        target_version = LATEST_FIRMWARE.get(name)
        
        # Firmware styling
        ota_button = ""
        if current_version == 'Unknown' or not target_version:
            fw_display = f'<span class="text-secondary fst-italic small"><i class="bi bi-question-circle me-1"></i>Unknown ({current_version})</span>'
        elif current_version == target_version:
            fw_display = f'<span class="text-success fw-bold small"><i class="bi bi-shield-check me-1"></i>Up to date ({current_version})</span>'
        else:
            fw_display = f'<span class="text-danger fw-bold small"><i class="bi bi-shield-exclamation me-1"></i>Outdated ({current_version} &rarr; {target_version})</span>'
            ota_button = f'<button class="btn btn-warning btn-sm btn-action me-1" onclick="pushOTAUpdate(\'{name}\', \'{target_version}\')" title="Deploy Update"><i class="bi bi-cloud-arrow-up"></i></button>'

        delete_button = f'<button class="btn btn-outline-danger btn-sm btn-action" onclick="removeDevice(\'{name}\')" title="Remove Device"><i class="bi bi-trash3"></i></button>'

        # Telemetry combining
        telemetry = f'<span class="me-2" title="Battery"><i class="bi bi-battery-half text-secondary me-1"></i>{battery}{"%" if battery != "N/A" else ""}</span>'
        telemetry += f'<span title="Temperature"><i class="bi bi-thermometer-half text-secondary me-1"></i>{temp}{"°F" if temp != "N/A" else ""}</span>'

        html_page += f"""
                            <tr>
                                <td class="ps-4 device-name">{name}</td>
                                <td>{status_badge}</td>
                                <td>{telemetry}</td>
                                <td>{fw_display}</td>
                                <td class="text-muted small">{last_seen}</td>
                                <td class="text-end pe-4">
                                    {ota_button}
                                    {delete_button}
                                </td>
                            </tr>
        """

    html_page += f"""
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header"><i class="bi bi-plus-circle me-2"></i>Provision New Device</div>
                        <div class="card-body">
                            <form id="addDeviceForm">
                                <div class="mb-3">
                                    <label for="new_device_name" class="form-label text-muted small fw-bold">DEVICE ALIAS</label>
                                    <input type="text" class="form-control bg-light" id="new_device_name" required placeholder="e.g. Smart Garage Door">
                                </div>
                                <div class="mb-4">
                                    <label for="new_device_version" class="form-label text-muted small fw-bold">FACTORY FIRMWARE VERSION</label>
                                    <input type="text" class="form-control bg-light" id="new_device_version" placeholder="e.g. 1.0.0">
                                </div>
                                <button type="submit" class="btn btn-primary w-100 fw-bold">Initialize Device</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header"><i class="bi bi-search me-2"></i>Manual Firmware Audit</div>
                        <div class="card-body">
                            <form id="queryForm">
                                <div class="mb-3">
                                    <label for="device_name_input" class="form-label text-muted small fw-bold">TARGET DEVICE</label>
                                    <input type="text" class="form-control bg-light" id="device_name_input" required placeholder="e.g. Google Home">
                                </div>
                                <div class="mb-4">
                                    <label for="firmware_version" class="form-label text-muted small fw-bold">REPORTED VERSION</label>
                                    <input type="text" class="form-control bg-light" id="firmware_version" required placeholder="e.g. 1.71">
                                </div>
                                <button type="submit" class="btn btn-secondary w-100 fw-bold text-white">Execute Audit</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        
        <script>
            const API_HEADERS = {{ 
                'Content-Type': 'application/json',
                'X-Api-Key': '{API_KEY}' 
            }};

            function triggerLanScan() {{
                fetch('/api/probe/trigger_scan', {{ method: 'POST', headers: API_HEADERS }})
                .then(() => alert("Sauron Probe activated. LAN Scan command queued."));
            }}

            document.getElementById('queryForm').addEventListener('submit', function(e) {{
                e.preventDefault(); 
                let deviceName = document.getElementById('device_name_input').value.replace(/ /g, '_');
                let targetUrl = '/device/' + encodeURIComponent(deviceName) + '?firmware_version=' + encodeURIComponent(document.getElementById('firmware_version').value);
                window.location.href = targetUrl;
            }});

            document.getElementById('addDeviceForm').addEventListener('submit', function(e) {{
                e.preventDefault();
                let deviceName = document.getElementById('new_device_name').value;
                let version = document.getElementById('new_device_version').value;

                fetch('/api/device/add', {{
                    method: 'POST',
                    headers: API_HEADERS,
                    body: JSON.stringify({{ device_name: deviceName, version: version }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if(data.status === 'success') window.location.reload(); 
                    else alert("Audit Failure: " + data.error);
                }});
            }});

            function pushOTAUpdate(deviceName, newVersion) {{
                if(confirm("AUTHORIZATION REQUIRED: Deploy firmware v" + newVersion + " to " + deviceName + "?")) {{
                    fetch('/api/device/update_firmware', {{
                        method: 'POST',
                        headers: API_HEADERS,
                        body: JSON.stringify({{ device_name: deviceName, new_version: newVersion }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if(data.status === 'success') window.location.reload(); 
                        else alert("Deployment Error: " + data.error);
                    }});
                }}
            }}

            function removeDevice(deviceName) {{
                if(confirm("CRITICAL WARNING: Irreversibly purge " + deviceName + " from the mainframe?")) {{
                    fetch('/api/device/remove', {{
                        method: 'POST',
                        headers: API_HEADERS,
                        body: JSON.stringify({{ device_name: deviceName }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if(data.status === 'success') window.location.reload(); 
                        else alert("Purge Failed: " + data.error);
                    }});
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html_page

# --- Query Route ---
@app.route('/device/<device_name>', methods=['GET', 'POST'])
def query_devices(device_name):
    clean_device_name = device_name.replace('_', ' ')
    is_machine = request.method == 'POST' or request.headers.get('Content-Type') == 'application/json'
    
    if request.method == 'GET':
        firmware_version = request.args.get('firmware_version')
    else:
        request_data = request.get_json()
        firmware_version = request_data.get('firmware_version') if request_data else None

    # Revamped the Result Page with Bootstrap too!
    result_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Audit Result</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <style>body { background-color: #f4f6f9; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }</style>
    </head>
    <body>
        <div class="card shadow-sm border-0" style="max-width: 500px; width: 100%;">
            <div class="card-body text-center p-5">
                <div class="mb-4">{{ icon }}</div>
                <h2 class="fw-bold {{ text_class }} mb-3">{{ title }}</h2>
                <div class="bg-light p-3 rounded mb-4 fw-bold text-secondary">{{ device }}</div>
                <p class="text-muted mb-4 fs-5">{{ message | safe }}</p>
                <a href="/" class="btn btn-outline-secondary w-100 fw-bold"><i class="bi bi-arrow-left me-2"></i>Return to Hub</a>
            </div>
        </div>
    </body>
    </html>
    """

    if not firmware_version:
        if is_machine: 
            return jsonify({"error": "Missing firmware_version parameter"}), 400
        return render_template_string(result_html, text_class="text-danger", icon='<i class="bi bi-x-circle-fill text-danger" style="font-size: 4rem;"></i>', title="System Error", device=clean_device_name, message="Missing firmware_version parameter."), 400

    device_doc = devices_collection.find_one({"device_name": clean_device_name})

    if device_doc:
        current_version = device_doc.get("version")
        if current_version == firmware_version:
            if is_machine: 
                return jsonify({"status": "up_to_date", "current_version": current_version}), 200
            return render_template_string(result_html, text_class="text-success", icon='<i class="bi bi-check-circle-fill text-success" style="font-size: 4rem;"></i>', title="Integrity Verified", device=clean_device_name, message=f"Device is running the latest authorized firmware ({current_version})."), 200
        else:
            if is_machine: 
                return jsonify({"status": "update_required", "latest_version": current_version}), 200
            return render_template_string(result_html, text_class="text-warning", icon='<i class="bi bi-exclamation-triangle-fill text-warning" style="font-size: 4rem;"></i>', title="Vulnerability Detected", device=clean_device_name, message=f"Reported version is {firmware_version}, but the secure baseline is <b>{current_version}</b>."), 200

    if is_machine: 
        return jsonify({"error": "Device not found."}), 404
    return render_template_string(result_html, text_class="text-danger", icon='<i class="bi bi-question-circle-fill text-danger" style="font-size: 4rem;"></i>', title="Target Not Found", device=clean_device_name, message="Device not found in the Sauron database."), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)