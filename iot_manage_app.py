from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# --- MongoDB Setup ---
client = MongoClient('mongodb+srv://eymohn03_db_user:A8Szpjx4vrMEGoDs@saurontower1.g7ptgmm.mongodb.net/')
db = client['SauronTower1']
devices_collection = db['devices']
logs_collection = db['device_logs']

# --- Database Seeder ---
if devices_collection.count_documents({}) == 0:
    print("Seeding database with initial devices...")
    initial_devices = [
        {"device_name": "Ring Doorbell", "company": "Amazon", "version": "19.4.2400"},
        {"device_name": "Echo 4th gen", "company": "Amazon", "version": "12584493188"},
        {"device_name": "Google Home", "company": "Google", "version": "3.77.510748"},
        {"device_name": "Nest Outdoor Cam", "company": "Google", "version": "1.71"},
        {"device_name": "Philips Hue Bulb", "company": "Philips", "version": "1.86.7"}
    ]
    devices_collection.insert_many(initial_devices)
    print("Database seeded successfully!")

# --- API Routes ---

@app.route('/api/device/checkin', methods=['POST'])
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
            {
                "$set": {
                    "last_seen": datetime.utcnow(),
                    "status": "online",
                    "last_ip": request.remote_addr
                }
            },
            upsert=True
        )
        return jsonify({"message": "Sauron acknowledges your presence."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/device/update_firmware', methods=['POST'])
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

# --- NEW: Add Device Route ---
@app.route('/api/device/add', methods=['POST'])
def add_device():
    data = request.get_json()
    device_name = data.get("device_name", "").strip()
    version = data.get("version", "").strip()

    # Input Validation
    if not device_name:
        return jsonify({"error": "Device name cannot be empty."}), 400

    # Check for duplicates
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
        return jsonify({"status": "success", "message": f"{device_name} added successfully."}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- NEW: Remove Device Route ---
@app.route('/api/device/remove', methods=['POST'])
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


# --- Homepage Route ---
@app.route('/')
def homepage():
    all_devices = list(devices_collection.find().sort("last_seen", -1))

    def format_time(dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else "Never"

    LATEST_FIRMWARE = {
        "Ring Doorbell": "19.4.2400",
        "Echo 4th gen": "12584493188",
        "Google Home": "3.77.510748",
        "Nest Outdoor Cam": "1.72", 
        "Philips Hue Bulb": "1.86.7"
    }

    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sauron IoT Hub | Live Dashboard</title>
        <style>
            body { font-family: -apple-system, sans-serif; background-color: #f4f4f9; padding: 40px; color: #333; }
            .container { max-width: 1050px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; vertical-align: middle; }
            th { background-color: #3498db; color: white; }
            .status-pill { padding: 5px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
            .online { background: #e8f5e9; color: #2e7d32; }
            .offline { background: #ffebee; color: #c62828; }
            
            .fw-good { color: #27ae60; font-weight: bold; font-size: 0.9em; }
            .fw-bad { color: #e74c3c; font-weight: bold; font-size: 0.9em; }
            .fw-unknown { color: #7f8c8d; font-style: italic; font-size: 0.9em; }
            
            .action-btn { color: white; border: none; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-size: 0.8em; font-weight: bold; margin-top: 5px; display: inline-block; transition: 0.2s; }
            .ota-btn { background-color: #f39c12; }
            .ota-btn:hover { background-color: #e67e22; transform: scale(1.05); }
            .del-btn { background-color: #e74c3c; margin-left: 5px; }
            .del-btn:hover { background-color: #c0392b; transform: scale(1.05); }

            .panel-container { display: flex; gap: 20px; margin-top: 40px; }
            .box { flex: 1; background: #e8f4f8; padding: 20px; border-radius: 5px; border-left: 5px solid #3498db; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; font-size: 1em; }
            button.submit-btn { background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; font-weight: bold; width: 100%;}
            button.submit-btn:hover { background-color: #2980b9; }
        </style>
        <meta http-equiv="refresh" content="10"> 
    </head>
    <body>
        <div class="container">
            <h1>👁️ Sauron Live Status Board</h1>
            <p>Monitoring active IoT devices in real-time. Page auto-refreshes every 10 seconds.</p>

            <table>
                <thead>
                    <tr>
                        <th>Device Name</th>
                        <th>Status</th>
                        <th>Battery</th>
                        <th>Temp</th>
                        <th>Firmware Status</th>
                        <th>Last Seen (UTC)</th>
                        <th>Actions</th>
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
        
        status_class = "online" if status == "online" else "offline"
        target_version = LATEST_FIRMWARE.get(name)
        
        ota_button = ""
        if current_version == 'Unknown' or not target_version:
            fw_display = f"<span class='fw-unknown'>❓ Unknown ({current_version})</span>"
        elif current_version == target_version:
            fw_display = f"<span class='fw-good'>✅ Up to Date ({current_version})</span>"
        else:
            fw_display = f"<span class='fw-bad'>⚠️ Update Req. ({current_version} &rarr; {target_version})</span>"
            ota_button = f"""<button class="action-btn ota-btn" onclick="pushOTAUpdate('{name}', '{target_version}')">🚀 Update</button>"""

        # Add the delete button for every row
        delete_button = f"""<button class="action-btn del-btn" onclick="removeDevice('{name}')">🗑️</button>"""

        html_page += f"""
                    <tr>
                        <td><b>{name}</b></td>
                        <td><span class="status-pill {status_class}">{status.upper()}</span></td>
                        <td>{battery}{'%' if battery != 'N/A' else ''}</td>
                        <td>{temp}{'°F' if temp != 'N/A' else ''}</td>
                        <td>{fw_display}</td>
                        <td><small>{last_seen}</small></td>
                        <td>{ota_button} {delete_button}</td>
                    </tr>
        """

    html_page += """
                </tbody>
            </table>

            <div class="panel-container">
                <div class="box">
                    <h3>➕ Register New Device</h3>
                    <form id="addDeviceForm">
                        <div class="form-group">
                            <label for="new_device_name">Device Name:</label>
                            <input type="text" id="new_device_name" required placeholder="e.g. Smart Lock">
                        </div>
                        <div class="form-group">
                            <label for="new_device_version">Initial Firmware Version:</label>
                            <input type="text" id="new_device_version" placeholder="e.g. 1.0.0">
                        </div>
                        <button type="submit" class="submit-btn">Add Device</button>
                    </form>
                </div>

                <div class="box">
                    <h3>🔍 Query a Device Manually</h3>
                    <form id="queryForm">
                        <div class="form-group">
                            <label for="device_name_input">Device Name:</label>
                            <input type="text" id="device_name_input" required placeholder="e.g. Google Home">
                        </div>
                        <div class="form-group">
                            <label for="firmware_version">Current Firmware Version:</label>
                            <input type="text" id="firmware_version" required placeholder="e.g. 1.71">
                        </div>
                        <button type="submit" class="submit-btn">Check Firmware</button>
                    </form>
                </div>
            </div>
        </div>

        <script>
            // Handle Manual Query
            document.getElementById('queryForm').addEventListener('submit', function(e) {
                e.preventDefault(); 
                let deviceName = document.getElementById('device_name_input').value.replace(/ /g, '_');
                let targetUrl = '/device/' + encodeURIComponent(deviceName) + '?firmware_version=' + encodeURIComponent(document.getElementById('firmware_version').value);
                window.location.href = targetUrl;
            });

            // Handle Add Device
            document.getElementById('addDeviceForm').addEventListener('submit', function(e) {
                e.preventDefault();
                let deviceName = document.getElementById('new_device_name').value;
                let version = document.getElementById('new_device_version').value;

                fetch('/api/device/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ device_name: deviceName, version: version })
                })
                .then(response => response.json())
                .then(data => {
                    if(data.status === 'success') {
                        window.location.reload(); 
                    } else {
                        alert("Error adding device: " + data.error);
                    }
                });
            });

            // Handle OTA Update
            function pushOTAUpdate(deviceName, newVersion) {
                if(confirm("Are you sure you want to deploy firmware v" + newVersion + " to " + deviceName + "?")) {
                    fetch('/api/device/update_firmware', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ device_name: deviceName, new_version: newVersion })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.status === 'success') {
                            window.location.reload(); 
                        } else {
                            alert("Deployment failed: " + data.error);
                        }
                    });
                }
            }

            // Handle Remove Device
            function removeDevice(deviceName) {
                if(confirm("CRITICAL WARNING: Are you sure you want to permanently delete " + deviceName + " from the database?")) {
                    fetch('/api/device/remove', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ device_name: deviceName })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.status === 'success') {
                            window.location.reload(); 
                        } else {
                            alert("Failed to delete: " + data.error);
                        }
                    });
                }
            }
        </script>
    </body>
    </html>
    """
    return html_page

# --- Query Route (Handles both Humans and Machines) ---
@app.route('/device/<device_name>', methods=['GET', 'POST'])
def query_devices(device_name):
    clean_device_name = device_name.replace('_', ' ')
    is_machine = request.method == 'POST' or request.headers.get('Content-Type') == 'application/json'
    
    if request.method == 'GET':
        firmware_version = request.args.get('firmware_version')
    else:
        request_data = request.get_json()
        firmware_version = request_data.get('firmware_version') if request_data else None

    result_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Firmware Result</title><style>body { font-family: sans-serif; background: #f4f4f9; padding: 50px; display: flex; justify-content: center; } .card { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; max-width: 500px; width: 100%; } .status-success { color: #27ae60; } .status-warning { color: #f39c12; } .status-error { color: #e74c3c; } .device-name { font-size: 1.2em; font-weight: bold; margin: 20px 0; padding: 10px; background: #eee; border-radius: 5px; } .back-btn { background-color: #3498db; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; }</style></head>
    <body><div class="card"><h1 class="{{ color_class }}">{{ icon }} {{ title }}</h1><div class="device-name">{{ device }}</div><div class="message">{{ message | safe }}</div><br><br><a href="/" class="back-btn">← Check Another Device</a></div></body>
    </html>
    """

    if not firmware_version:
        if is_machine: return jsonify({"error": "Missing firmware_version parameter"}), 400
        return render_template_string(result_html, color_class="status-error", icon="❌", title="Error", device=clean_device_name, message="Missing firmware_version parameter."), 400

    device_doc = devices_collection.find_one({"device_name": clean_device_name})

    if device_doc:
        current_version = device_doc.get("version")
        if current_version == firmware_version:
            if is_machine: return jsonify({"status": "up_to_date", "current_version": current_version}), 200
            return render_template_string(result_html, color_class="status-success", icon="✅", title="Up to Date!", device=clean_device_name, message=f"Device is running the latest firmware ({current_version})."), 200
        else:
            if is_machine: return jsonify({"status": "update_required", "latest_version": current_version}), 200
            return render_template_string(result_html, color_class="status-warning", icon="⚠️", title="Update Required", device=clean_device_name, message=f"Your version is {firmware_version}, latest is <b>{current_version}</b>."), 200

    if is_machine: return jsonify({"error": f"Device not found."}), 404
    return render_template_string(result_html, color_class="status-error", icon="❓", title="Not Found", device=clean_device_name, message="Device not found in database."), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)