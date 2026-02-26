from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient

app = Flask(__name__)

# --- MongoDB Setup ---
# Connect to your local MongoDB instance
client = MongoClient('mongodb+srv://eymohn03_db_user:A8Szpjx4vrMEGoDs@saurontower1.g7ptgmm.mongodb.net/')
db = client['SauronTower1']
devices_collection = db['devices']

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


# --- Homepage Route ---
@app.route('/')
def homepage():
    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sauron IoT Device Management</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f4f4f9; color: #333; margin: 0; padding: 50px; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; margin-top: 0; }
            ul { background: #f8f9fa; padding: 15px 15px 15px 35px; border-radius: 5px; }
            li { margin-bottom: 10px; }
            a { color: #3498db; text-decoration: none; font-weight: bold; }
            a:hover { text-decoration: underline; }
            code { background: #eee; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }

            .query-box { background: #e8f4f8; padding: 20px; border-radius: 5px; margin-top: 20px; border-left: 5px solid #3498db; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; font-size: 1em; }
            button { background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; font-weight: bold; width: 100%;}
            button:hover { background-color: #2980b9; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sauron IoT Device Management</h1>
            <p>Welcome to the central hub for checking your smart home device firmware.</p>

            <div class="query-box">
                <h3>Query a Device Manually</h3>
                <form id="queryForm">
                    <div class="form-group">
                        <label for="device_name">Device Name:</label>
                        <input type="text" id="device_name" required placeholder="e.g. Google Home or Ring Doorbell">
                    </div>
                    <div class="form-group">
                        <label for="firmware_version">Current Firmware Version:</label>
                        <input type="text" id="firmware_version" required placeholder="e.g. 1.71">
                    </div>
                    <button type="submit">Check Firmware</button>
                </form>
            </div>

            <br>
            <h3>Test Links (Click to try!)</h3>
            <ul>
                <li><a href="/device/Google_Home?firmware_version=3.77.510748" target="_blank">Google Home (Matches Dataset - Up to date)</a></li>
                <li><a href="/device/Ring_Doorbell?firmware_version=19.0.0000" target="_blank">Ring Doorbell (Outdated Version - Needs Update)</a></li>
                <li><a href="/device/Apple_TV?firmware_version=17.0" target="_blank">Apple TV (Not in dataset - 404 Error)</a></li>
            </ul>
        </div>

        <script>
            document.getElementById('queryForm').addEventListener('submit', function(e) {
                e.preventDefault(); 
                let deviceName = document.getElementById('device_name').value;
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