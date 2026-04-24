import os
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# --- Load Secrets ---
load_dotenv() 

MONGO_URI = os.getenv("MONGO_URI")
API_KEY = os.getenv("SAURON_API_KEY", "fallback_key_if_missing")

app = Flask(__name__)
# --- Flask Session Security Key ---
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_cookie_secret")

# --- MongoDB Setup ---
client = MongoClient(MONGO_URI)
db = client['SauronTower1']
devices_collection = db['devices']
logs_collection = db['device_logs']
firmware_collection = db['firmware_versions']
commands_collection = db['command_queue'] 
users_collection = db['users'] 

# --- Database Seeders ---
# NOTE: The fake device seeder has been permanently removed for production!

if users_collection.count_documents({}) == 0:
    print("Initializing default admin user...")
    users_collection.insert_one({
        "username": "admin",
        "password": generate_password_hash("Sauron2026!") 
    })


# --- Security Bouncers ---

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get("X-Api-Key") == API_KEY:
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Unauthorized. Sauron does not recognize this key."}), 401
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- AUTHENTICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('homepage'))

    error_msg = ""
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_record = users_collection.find_one({"username": username})
        
        if user_record and check_password_hash(user_record['password'], password):
            session['user'] = username 
            return redirect(url_for('homepage'))
        else:
            error_msg = '<div class="alert alert-danger" style="background-color: rgba(255, 51, 102, 0.1); border: 1px solid #ff3366; color: #ff3366; padding: 10px; border-radius: 4px; font-size: 0.85rem; font-weight: 600; margin-bottom: 20px;">ACCESS DENIED: Invalid Credentials</div>'

    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-4M4H383ZT1"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', 'G-4M4H383ZT1');
        </script>
        <title>Sauron Hub | Authenticate</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <style>
            body {{ background-color: #090814; color: #f8f9fa; font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; background-image: radial-gradient(circle at center, rgba(157, 78, 221, 0.1), transparent 50%);}}
            .card {{ background-color: #14122b; border: 1px solid #2b2757; border-radius: 8px; max-width: 400px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
            .form-control {{ background-color: rgba(0,0,0,0.3) !important; border: 1px solid #2b2757 !important; color: white !important; font-family: 'Roboto Mono', monospace; }}
            .form-control:focus {{ box-shadow: 0 0 0 0.25rem rgba(157, 78, 221, 0.25) !important; border-color: #9d4edd !important; }}
            .form-label {{ color: #8b87a8; font-size: 0.75rem; letter-spacing: 1px; text-transform: uppercase; font-weight: 700; margin-bottom: 8px;}}
            .btn-cyber {{ background-color: #9d4edd; color: white; border: none; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; border-radius: 4px; padding: 12px; box-shadow: 0 0 20px rgba(157, 78, 221, 0.4); width: 100%; transition: all 0.3s; }}
            .btn-cyber:hover {{ background-color: #b166eb; color: white; box-shadow: 0 0 30px rgba(157, 78, 221, 0.6); transform: translateY(-1px); }}
            a.cyber-link {{ color: #8b87a8; text-decoration: none; font-size: 0.8rem; font-weight: 600; letter-spacing: 1px; transition: 0.2s; }}
            a.cyber-link:hover {{ color: #9d4edd; }}
        </style>
    </head>
    <body>
        <div class="card p-5">
            <div class="text-center mb-4">
                <i class="bi bi-hexagon-fill" style="color: #9d4edd; font-size: 3rem; text-shadow: 0 0 20px rgba(157, 78, 221, 0.4);"></i>
                <h3 class="fw-bold mt-3 text-white" style="letter-spacing: 2px;">SAURON LOGIN</h3>
                <p class="small" style="color: #aeb2b8;">AUTHORIZED PERSONNEL ONLY</p>
            </div>
            
            {error_msg}

            <form method="POST" action="/login">
                <div class="mb-3">
                    <label class="form-label">USERNAME</label>
                    <input type="text" name="username" class="form-control" required autocomplete="off">
                </div>
                <div class="mb-4">
                    <label class="form-label">PASSWORD</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-cyber mb-4">AUTHENTICATE</button>
            </form>
            
            <div class="text-center border-top border-secondary pt-3 mt-2">
                <a href="/register" class="cyber-link">CREATE ACCOUNT &rarr;</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html_page

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('homepage'))

    error_msg = ""
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if users_collection.find_one({"username": username}):
            error_msg = '<div class="alert alert-warning" style="background-color: rgba(255, 157, 0, 0.1); border: 1px solid #ff9d00; color: #ff9d00; padding: 10px; border-radius: 4px; font-size: 0.85rem; font-weight: 600; margin-bottom: 20px;">USERNAME ALREADY IN USE</div>'
        else:
            users_collection.insert_one({
                "username": username,
                "password": generate_password_hash(password)
            })
            session['user'] = username 
            return redirect(url_for('homepage'))

    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-4M4H383ZT1"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', 'G-4M4H383ZT1');
        </script>
        <title>Sauron Hub | Create Account</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <style>
            body {{ background-color: #090814; color: #f8f9fa; font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; background-image: radial-gradient(circle at center, rgba(157, 78, 221, 0.1), transparent 50%);}}
            .card {{ background-color: #14122b; border: 1px solid #2b2757; border-radius: 8px; max-width: 400px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
            .form-control {{ background-color: rgba(0,0,0,0.3) !important; border: 1px solid #2b2757 !important; color: white !important; font-family: 'Roboto Mono', monospace; }}
            .form-control:focus {{ box-shadow: 0 0 0 0.25rem rgba(157, 78, 221, 0.25) !important; border-color: #9d4edd !important; }}
            .form-label {{ color: #8b87a8; font-size: 0.75rem; letter-spacing: 1px; text-transform: uppercase; font-weight: 700; margin-bottom: 8px;}}
            .btn-cyber {{ background-color: transparent; border: 1px solid #9d4edd; color: #9d4edd; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; border-radius: 4px; padding: 12px; width: 100%; transition: all 0.3s; }}
            .btn-cyber:hover {{ background-color: #9d4edd; color: white; box-shadow: 0 0 20px rgba(157, 78, 221, 0.4); transform: translateY(-1px); }}
            a.cyber-link {{ color: #8b87a8; text-decoration: none; font-size: 0.8rem; font-weight: 600; letter-spacing: 1px; transition: 0.2s; }}
            a.cyber-link:hover {{ color: #9d4edd; }}
        </style>
    </head>
    <body>
        <div class="card p-5">
            <div class="text-center mb-4">
                <i class="bi bi-person-plus-fill" style="color: #9d4edd; font-size: 3rem; text-shadow: 0 0 20px rgba(157, 78, 221, 0.4);"></i>
                <h3 class="fw-bold mt-3 text-white" style="letter-spacing: 2px;">CREATE ACCOUNT</h3>
                <p class="small" style="color: #aeb2b8;">REQUEST PLATFORM ACCESS</p>
            </div>
            
            {error_msg}

            <form method="POST" action="/register">
                <div class="mb-3">
                    <label class="form-label">NEW USERNAME</label>
                    <input type="text" name="username" class="form-control" required autocomplete="off">
                </div>
                <div class="mb-4">
                    <label class="form-label">CREATE PASSWORD</label>
                    <input type="password" name="password" class="form-control" required minlength="6">
                </div>
                <button type="submit" class="btn btn-cyber mb-4">REGISTER</button>
            </form>
            
            <div class="text-center border-top border-secondary pt-3 mt-2">
                <a href="/login" class="cyber-link">&larr; RETURN TO LOGIN</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html_page

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


# --- API Routes (Machine-facing, protected by API Key) ---

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
    except Exception:
        return jsonify({"error": "Server error"}), 500


# --- Dashboard Routes (Human-facing, protected by Session) ---

@app.route('/')
@login_required  
def homepage():
    all_devices = list(devices_collection.find().sort("last_seen", -1))
    firmware_docs = firmware_collection.find()
    LATEST_FIRMWARE = {doc['model']: doc['latest_version'] for doc in firmware_docs}
    
    operator_name = session.get('user', 'Operator').upper()

    def format_time(dt):
        return dt.strftime('%b %d, %H:%M:%S') if dt else "Never"

    html_page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-4M4H383ZT1"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', 'G-4M4H383ZT1');
        </script>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sauron Hub | Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <meta http-equiv="refresh" content="10"> 
        <style>
            :root {{
                --bg-void: #090814;
                --surface: #14122b;
                --surface-hover: #1c193b;
                --border-color: #2b2757;
                --primary-purple: #9d4edd;
                --glow-purple: 0 0 20px rgba(157, 78, 221, 0.4);
                --text-main: #f8f9fa;
                --text-muted: #8b87a8;
                --success-green: #00ff88;
                --warning-orange: #ff9d00;
                --danger-red: #ff3366;
            }}

            body {{ background-color: var(--bg-void); color: var(--text-main); font-family: 'Inter', sans-serif; min-height: 100vh; 
                   background-image: radial-gradient(circle at top right, rgba(157, 78, 221, 0.1), transparent 40%); }}
            
            .navbar {{ background-color: rgba(20, 18, 43, 0.8) !important; backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color); padding: 15px 0; }}
            .navbar-brand {{ color: #fff !important; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; }}
            
            .card {{ background-color: var(--surface); border: 1px solid var(--border-color); box-shadow: 0 8px 32px rgba(0,0,0,0.3); border-radius: 6px; scroll-margin-top: 100px; }}
            .card-header {{ background-color: transparent; border-bottom: 1px solid var(--border-color); padding: 15px 20px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 1px; font-size: 0.9rem; }}
            
            .table-container {{ padding: 0; }}
            .table {{ color: var(--text-main); margin-bottom: 0; }}
            .table th {{ background-color: rgba(0,0,0,0.2); color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid var(--border-color); border-top: none; padding: 15px 20px;}}
            .table td {{ vertical-align: middle; padding: 15px 20px; border-bottom: 1px solid var(--border-color); }}
            .table-hover tbody tr:hover {{ background-color: var(--surface-hover); color: #fff; }}
            .device-name {{ font-weight: 600; color: #fff; letter-spacing: 0.5px; }}
            
            .badge {{ padding: 6px 10px; font-weight: 700; letter-spacing: 0.5px; font-size: 0.7rem; border-radius: 4px; }}
            .badge-online {{ background-color: rgba(0, 255, 136, 0.1); color: var(--success-green); border: 1px solid rgba(0, 255, 136, 0.2); }}
            .badge-offline {{ background-color: rgba(255, 51, 102, 0.1); color: var(--danger-red); border: 1px solid rgba(255, 51, 102, 0.2); }}
            
            .btn-cyber {{ background-color: var(--primary-purple); color: white; border: none; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; font-size: 0.8rem; border-radius: 4px; padding: 10px 20px; box-shadow: var(--glow-purple); transition: all 0.3s ease; }}
            .btn-cyber:hover {{ background-color: #b166eb; color: white; box-shadow: 0 0 30px rgba(157, 78, 221, 0.6); transform: translateY(-1px); }}
            .btn-cyber-outline {{ background-color: transparent; color: var(--text-main); border: 1px solid var(--border-color); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; transition: all 0.3s; text-decoration: none; display: inline-block; padding: 10px 20px; border-radius: 4px;}}
            .btn-cyber-outline:hover {{ background-color: rgba(255,255,255,0.05); color: white; border-color: var(--text-muted); }}
            
            .form-control {{ background-color: rgba(0,0,0,0.3) !important; border: 1px solid var(--border-color) !important; color: white !important; border-radius: 4px; padding: 12px; font-family: 'Roboto Mono', monospace; font-size: 0.9rem; }}
            .form-control::placeholder {{ color: #504b72; }}
            .form-control:focus {{ box-shadow: 0 0 0 0.25rem rgba(157, 78, 221, 0.25) !important; border-color: var(--primary-purple) !important; }}
            .form-label {{ color: var(--text-muted); font-size: 0.75rem; letter-spacing: 1px; text-transform: uppercase; font-weight: 700; margin-bottom: 8px;}}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg mb-5 sticky-top">
            <div class="container-fluid px-5">
                <a class="navbar-brand d-flex align-items-center" href="#">
                    <i class="bi bi-hexagon-fill me-2" style="color: var(--primary-purple); text-shadow: var(--glow-purple);"></i>
                    SAURON PLATFORM
                </a>
                
                <div class="d-flex align-items-center">
                    <span class="small fw-bold me-4" style="color: #aeb2b8; letter-spacing: 1px;">
                        <i class="bi bi-person-bounding-box me-2" style="color: #9d4edd;"></i>USER: <span class="text-white">{operator_name}</span>
                    </span>
                    <button class="btn btn-cyber me-3" onclick="triggerLanScan()">
                        <i class="bi bi-radar me-2"></i> INITIATE LAN SCAN
                    </button>
                    <a href="/logout" class="btn btn-cyber-outline"><i class="bi bi-box-arrow-right me-1"></i> DISCONNECT</a>
                </div>
            </div>
        </nav>

        <div class="container-fluid px-5">
            <div class="card mb-5">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span><i class="bi bi-hdd-stack text-muted me-2"></i>Endpoint Telemetry</span>
                    <span class="text-muted" style="font-size: 0.75rem;"><i class="bi bi-broadcast me-1" style="color: var(--primary-purple);"></i> LIVE LINK ACTIVE</span>
                </div>
                <div class="card-body table-container table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th class="ps-4">Endpoint Alias</th>
                                <th>Network State</th>
                                <th>Vitals (PWR / TMP)</th>
                                <th>Firmware Policy</th>
                                <th>Last Check-In (UTC)</th>
                                <th class="text-end pe-4">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
    """

    # NEW: The sleek Empty State UI
    if not all_devices:
        html_page += """
                            <tr>
                                <td colspan="6" class="text-center py-5">
                                    <i class="bi bi-radar" style="font-size: 3rem; color: #2b2757;"></i>
                                    <h4 class="text-white mt-3 fw-bold" style="letter-spacing: 1px;">NO ENDPOINTS DETECTED</h4>
                                    <p class="text-muted mb-4">The Sauron Hub is currently monitoring 0 active devices.</p>
                                    <div class="d-flex justify-content-center gap-3">
                                        <button class="btn btn-cyber" onclick="triggerLanScan()">
                                            <i class="bi bi-search me-2"></i> INITIATE LAN SCAN
                                        </button>
                                        <a href="#provision-card" class="btn btn-cyber-outline">
                                            <i class="bi bi-terminal me-2"></i> MANUAL PROVISION
                                        </a>
                                    </div>
                                </td>
                            </tr>
        """
    else:
        for dev in all_devices:
            name = dev.get('device_name', 'Unknown')
            status = dev.get('status', 'offline')
            battery = dev.get('battery', 'N/A')
            temp = dev.get('temperature', 'N/A')
            current_version = dev.get('version', 'Unknown')
            last_seen = format_time(dev.get('last_seen'))
            
            if status == "online":
                status_badge = '<span class="badge badge-online"><i class="bi bi-circle-fill me-1" style="font-size: 6px; vertical-align: middle;"></i> ONLINE</span>'
            else:
                status_badge = '<span class="badge badge-offline"><i class="bi bi-circle-fill me-1" style="font-size: 6px; vertical-align: middle;"></i> OFFLINE</span>'

            target_version = LATEST_FIRMWARE.get(name)
            
            ota_button = ""
            if current_version == 'Unknown' or not target_version:
                fw_display = f'<span class="text-muted fw-bold" style="font-size: 0.85rem;"><i class="bi bi-dash-circle me-1"></i> UNKNOWN ({current_version})</span>'
            elif current_version == target_version:
                fw_display = f'<span style="color: var(--success-green); font-weight: 700; font-size: 0.85rem;"><i class="bi bi-shield-check me-1"></i> COMPLIANT</span> <span class="text-muted ms-1" style="font-size: 0.75rem;">v{current_version}</span>'
            else:
                fw_display = f'<span style="color: var(--danger-red); font-weight: 700; font-size: 0.85rem;"><i class="bi bi-shield-exclamation me-1"></i> VULNERABLE</span> <span class="text-muted ms-1" style="font-size: 0.75rem;">({current_version} &rarr; {target_version})</span>'
                ota_button = f'<button class="btn btn-sm btn-cyber me-2" style="padding: 5px 10px; font-size: 0.7rem;" onclick="pushOTAUpdate(\'{name}\', \'{target_version}\')" title="Push Update">PATCH OTA</button>'

            delete_button = f'<button class="btn btn-sm btn-cyber-outline" style="padding: 5px 10px;" onclick="removeDevice(\'{name}\')" title="Revoke Device"><i class="bi bi-trash3"></i></button>'

            telemetry = f'<span class="me-3" style="font-family: \'Roboto Mono\', monospace; font-size: 0.85rem;"><i class="bi bi-lightning-charge-fill text-muted me-1"></i>{battery}{"%" if battery != "N/A" else ""}</span>'
            telemetry += f'<span style="font-family: \'Roboto Mono\', monospace; font-size: 0.85rem;"><i class="bi bi-thermometer-half text-muted me-1"></i>{temp}{"°F" if temp != "N/A" else ""}</span>'

            html_page += f"""
                                <tr>
                                    <td class="ps-4 device-name">{name}</td>
                                    <td>{status_badge}</td>
                                    <td>{telemetry}</td>
                                    <td>{fw_display}</td>
                                    <td style="font-family: 'Roboto Mono', monospace; font-size: 0.85rem; color: var(--text-muted);">{last_seen}</td>
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

            <div class="row g-4 mb-5">
                <div class="col-md-6">
                    <div class="card h-100" id="provision-card">
                        <div class="card-header"><i class="bi bi-terminal me-2"></i>Provision Endpoint</div>
                        <div class="card-body p-4">
                            <form id="addDeviceForm">
                                <div class="mb-4">
                                    <label for="new_device_name" class="form-label">ENDPOINT ALIAS</label>
                                    <input type="text" class="form-control" id="new_device_name" required placeholder="e.g. SRV-GARAGE-01">
                                </div>
                                <div class="mb-5">
                                    <label for="new_device_version" class="form-label">BASELINE FIRMWARE</label>
                                    <input type="text" class="form-control" id="new_device_version" placeholder="1.0.0">
                                </div>
                                <button type="submit" class="btn btn-cyber-outline w-100 py-2">REGISTER TO HUB</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header"><i class="bi bi-search me-2"></i>Manual Integrity Audit</div>
                        <div class="card-body p-4">
                            <form id="queryForm">
                                <div class="mb-4">
                                    <label for="device_name_input" class="form-label">TARGET IDENTIFIER</label>
                                    <input type="text" class="form-control" id="device_name_input" required placeholder="e.g. Google Home">
                                </div>
                                <div class="mb-5">
                                    <label for="firmware_version" class="form-label">REPORTED VERSION</label>
                                    <input type="text" class="form-control" id="firmware_version" required placeholder="e.g. 1.71">
                                </div>
                                <button type="submit" class="btn btn-cyber-outline w-100 py-2">EXECUTE AUDIT</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            const API_HEADERS = {{ 
                'Content-Type': 'application/json',
                'X-Api-Key': '{API_KEY}' 
            }};

            function triggerLanScan() {{
                fetch('/api/probe/trigger_scan', {{ method: 'POST', headers: API_HEADERS }})
                .then(() => alert("[COMMAND SENT] Sauron Probe activated. Awaiting remote telemetry..."));
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
                    else alert("Provisioning Error: " + data.error);
                }});
            }});

            function pushOTAUpdate(deviceName, newVersion) {{
                if(confirm("CRITICAL ACTION: Deploy emergency patch v" + newVersion + " to " + deviceName + "?")) {{
                    fetch('/api/device/update_firmware', {{
                        method: 'POST',
                        headers: API_HEADERS,
                        body: JSON.stringify({{ device_name: deviceName, new_version: newVersion }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if(data.status === 'success') window.location.reload(); 
                        else alert("Patch Failed: " + data.error);
                    }});
                }}
            }}

            function removeDevice(deviceName) {{
                if(confirm("AUTHORIZATION REQUIRED: Purge " + deviceName + " from the mainframe registry?")) {{
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

@app.route('/device/<device_name>', methods=['GET', 'POST'])
def query_devices(device_name):
    is_machine = request.method == 'POST' or request.headers.get('Content-Type') == 'application/json'
    if not is_machine and 'user' not in session:
        return redirect(url_for('login'))

    clean_device_name = device_name.replace('_', ' ')
    
    if request.method == 'GET':
        firmware_version = request.args.get('firmware_version')
    else:
        request_data = request.get_json()
        firmware_version = request_data.get('firmware_version') if request_data else None

    result_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Audit Result</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <style>
            body { background-color: #090814; color: #f8f9fa; font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
            .card { background-color: #14122b; border: 1px solid #2b2757; border-radius: 8px; max-width: 500px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
            .terminal-box { background-color: rgba(0,0,0,0.3); border: 1px solid #2b2757; border-radius: 4px; padding: 15px; font-family: 'Roboto Mono', monospace; margin-bottom: 20px;}
            .btn-cyber { background-color: transparent; color: #fff; border: 1px solid #2b2757; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; padding: 12px; transition: 0.3s; }
            .btn-cyber:hover { background-color: rgba(255,255,255,0.05); color: #fff; border-color: #8b87a8;}
        </style>
    </head>
    <body>
        <div class="card p-5 text-center">
            <div class="mb-4">{{ icon }}</div>
            <h2 class="fw-bold mb-3" style="color: {{ text_color }}; text-transform: uppercase; letter-spacing: 2px;">{{ title }}</h2>
            <div class="terminal-box fw-bold text-secondary">{{ device }}</div>
            <p class="text-muted mb-5 fs-6">{{ message | safe }}</p>
            <a href="/" class="btn-cyber w-100 text-decoration-none d-block"><i class="bi bi-arrow-left me-2"></i>Return to Platform</a>
        </div>
    </body>
    </html>
    """

    if not firmware_version:
        if is_machine: 
            return jsonify({"error": "Missing firmware_version parameter"}), 400
        return render_template_string(result_html, text_color="#ff3366", icon='<i class="bi bi-x-hexagon-fill" style="font-size: 4rem; color: #ff3366;"></i>', title="System Error", device=clean_device_name, message="Missing firmware_version parameter."), 400

    device_doc = devices_collection.find_one({"device_name": clean_device_name})

    if device_doc:
        current_version = device_doc.get("version")
        if current_version == firmware_version:
            if is_machine: 
                return jsonify({"status": "up_to_date", "current_version": current_version}), 200
            return render_template_string(result_html, text_color="#00ff88", icon='<i class="bi bi-shield-fill-check" style="font-size: 4rem; color: #00ff88; text-shadow: 0 0 20px rgba(0,255,136,0.4);"></i>', title="Integrity Verified", device=clean_device_name, message=f"Target is running the latest authorized baseline (v{current_version})."), 200
        else:
            if is_machine: 
                return jsonify({"status": "update_required", "latest_version": current_version}), 200
            return render_template_string(result_html, text_color="#ff9d00", icon='<i class="bi bi-shield-fill-exclamation" style="font-size: 4rem; color: #ff9d00; text-shadow: 0 0 20px rgba(255,157,0,0.4);"></i>', title="Vulnerability Detected", device=clean_device_name, message=f"Reported version is v{firmware_version}, but the secure baseline is <b>v{current_version}</b>. Immediate patching advised."), 200

    if is_machine: 
        return jsonify({"error": "Device not found."}), 404
    return render_template_string(result_html, text_color="#8b87a8", icon='<i class="bi bi-question-square" style="font-size: 4rem; color: #8b87a8;"></i>', title="Unknown Target", device=clean_device_name, message="Target identity not found in the Sauron registry."), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)