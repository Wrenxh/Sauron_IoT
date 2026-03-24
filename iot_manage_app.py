from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# --- MongoDB Setup ---
# Connect to your local MongoDB instance
client = MongoClient('mongodb+srv://eymohn03_db_user:A8Szpjx4vrMEGoDs@saurontower1.g7ptgmm.mongodb.net/')
db = client['SauronTower1']
devices_collection = db['devices']
logs_collection = db['device_logs']

# --- Database Seeder ---
# Runs once to convert your old list into MongoDB documents
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

@app.route('/api/device/checkin', methods=['POST'])
def device_checkin():
    """
    Endpoint for physical IoT devices to report their status.
    Expects JSON: {"device_name": "...", "battery": 85, "temp": 22}
    """
    data = request.get_json()
    
    if not data or 'device_name' not in data:
        return jsonify({"error": "Missing device_name"}), 400

    device_name = data.get("device_name")
    
    # Create the log entry for history
    checkin_log = {
        "device_name": device_name,
        "battery": data.get("battery"),
        "temperature": data.get("temp"),
        "ip_address": request.remote_addr,
        "timestamp": datetime.utcnow()
    }

    try:
        # 1. Save to history logs
        logs_collection.insert_one(checkin_log)
        
        # 2. Update the Master Device list with 'Last Seen' and current status
        # 'upsert=True' adds the device if it's new to the system
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
        
        return jsonify({
            "message": "Sauron acknowledges your presence.",
            "server_time": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Homepage Route (UPDATED WITH LIVE DASHBOARD) ---
@app.route('/')
def homepage():
    # Fetch all devices from MongoDB, sorted by newest 'last_seen'
    all_devices = list(devices_collection.find().sort("last_seen", -1))

    # Helper function to format the timestamp nicely
    def format_time(dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else "Never"

    # Start building the HTML page (Notice the meta refresh tag!)
    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sauron IoT Hub | Live Dashboard</title>
        <style>
            body { font-family: -apple-system, sans-serif; background-color: #f4f4f9; padding: 40px; color: #333; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #3498db; color: white; }
            .status-pill { padding: 5px 10px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
            .online { background: #e8f5e9; color: #2e7d32; }
            .offline { background: #ffebee; color: #c62828; }
            
            /* Styles for the manual query box at the bottom */
            .query-box { background: #e8f4f8; padding: 20px; border-radius: 5px; margin-top: 40px; border-left: 5px solid #3498db; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; font-size: 1em; }
            button { background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; font-weight: bold; width: 100%;}
            button:hover { background-color: #2980b9; }
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
                        <th>Last Seen (UTC)</th>
                    </tr>
                </thead>
                <tbody>
    """

    # Loop through the database records and create a table row for each
    for dev in all_devices:
        name = dev.get('device_name', 'Unknown')
        status = dev.get('status', 'offline')
        battery = dev.get('battery', 'N/A')
        temp = dev.get('temperature', 'N/A')
        last_seen = format_time(dev.get('last_seen'))
        
        status_class = "online" if status == "online" else "offline"

        html_page += f"""
                    <tr>
                        <td><b>{name}</b></td>
                        <td><span class="status-pill {status_class}">{status.upper()}</span></td>
                        <td>{battery}{'%' if battery != 'N/A' else ''}</td>
                        <td>{temp}{'°F' if temp != 'N/A' else ''}</td>
                        <td><small>{last_seen}</small></td>
                    </tr>
        """

    # Close the table and add back the Manual Query feature
    html_page += """
                </tbody>
            </table>

            <div class="query-box">
                <h3>Query a Device Manually</h3>
                <form id="queryForm">
                    <div class="form-group">
                        <label for="device_name_input">Device Name:</label>
                        <input type="text" id="device_name_input" required placeholder="e.g. Google Home or Ring Doorbell">
                    </div>
                    <div class="form-group">
                        <label for="firmware_version">Current Firmware Version:</label>
                        <input type="text" id="firmware_version" required placeholder="e.g. 1.71">
                    </div>
                    <button type="submit">Check Firmware</button>
                </form>
            </div>
        </div>

        <script>
            document.getElementById('queryForm').addEventListener('submit', function(e) {
                e.preventDefault(); 
                let deviceName = document.getElementById('device_name_input').value;
                let firmwareVersion = document.getElementById('firmware_version').value;
                deviceName = deviceName.replace(/ /g, '_');
                let targetUrl = '/device/' + encodeURIComponent(deviceName) + '?firmware_version=' + encodeURIComponent(firmwareVersion);
                window.location.href = targetUrl;
            });
        </script>
    </body>
    </html>
    """
    return html_page


# --- Query Route (Handles both Humans and Machines) ---
@app.route('/device/<device_name>', methods=['GET', 'POST'])
def query_devices(device_name):
    clean_device_name = device_name.replace('_', ' ')

    is_machine = False
    if request.method == 'GET':
        firmware_version = request.args.get('firmware_version')
    elif request.method == 'POST':
        is_machine = True
        request_data = request.get_json()
        firmware_version = request_data.get('firmware_version') if request_data else None

    result_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Firmware Result</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f4f4f9; padding: 50px; display: flex; justify-content: center; }
            .card { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; max-width: 500px; width: 100%; }
            h1 { margin-top: 0; }
            .status-success { color: #27ae60; }
            .status-warning { color: #f39c12; }
            .status-error { color: #e74c3c; }
            .device-name { font-size: 1.2em; font-weight: bold; color: #555; margin: 20px 0; padding: 10px; background: #eee; border-radius: 5px; }
            .message { font-size: 1.1em; color: #333; margin-bottom: 30px; line-height: 1.5; }
            .back-btn { background-color: #3498db; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; transition: 0.2s; }
            .back-btn:hover { background-color: #2980b9; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1 class="{{ color_class }}">{{ icon }} {{ title }}</h1>
            <div class="device-name">{{ device }}</div>
            <div class="message">{{ message | safe }}</div>
            <a href="/" class="back-btn">← Check Another Device</a>
        </div>
    </body>
    </html>
    """

    if not firmware_version:
        if is_machine:
            return jsonify({"error": "Missing firmware_version parameter"}), 400
        return render_template_string(result_html, color_class="status-error", icon="❌", title="Error",
                                      device=clean_device_name, message="Missing firmware_version parameter."), 400

    # Query MongoDB for the specific device
    device_doc = devices_collection.find_one({"device_name": clean_device_name})

    if device_doc:
        current_version = device_doc.get("version")

        if current_version == firmware_version:
            if is_machine:
                return jsonify({"status": "up_to_date", "current_version": current_version}), 200
            return render_template_string(result_html, color_class="status-success", icon="✅", title="Up to Date!",
                                          device=clean_device_name,
                                          message=f"You're all set! Your device is running the latest firmware ({current_version})."), 200
        else:
            if is_machine:
                return jsonify({"status": "update_required", "latest_version": current_version}), 200
            return render_template_string(result_html, color_class="status-warning", icon="⚠️", title="Update Required",
                                          device=clean_device_name,
                                          message=f"Your version is {firmware_version}, but the latest available is <b>{current_version}</b>. Please update your device!"), 200

    if is_machine:
        return jsonify({"error": f"Device '{clean_device_name}' not found."}), 404

    return render_template_string(result_html, color_class="status-error", icon="❓", title="Not Found",
                                  device=clean_device_name,
                                  message="Sorry, this device was not found in our database. Please check the spelling and try again."), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)