import os
import re
import secrets
from flask import Flask, request, jsonify, session, redirect, url_for
from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix  # NEW: Handles NGINX IP routing
from apscheduler.schedulers.background import BackgroundScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Load Secrets ---
load_dotenv() 

MONGO_URI = os.getenv("MONGO_URI")
API_KEY = os.getenv("SAURON_API_KEY", "fallback_key_if_missing")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_cookie_secret")

# NEW: Tell Flask to trust the real IPs forwarded by NGINX
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- Initialize Rate Limiter ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# --- MongoDB Setup ---
client = MongoClient(MONGO_URI)
db = client['SauronTower1']
devices_collection = db['devices']
logs_collection = db['device_logs']
firmware_collection = db['firmware_versions']
commands_collection = db['command_queue'] 
users_collection = db['users'] 
system_state = db['system_state'] 
probe_tokens_collection = db['probe_tokens'] 

# --- Admin Seeder ---
if users_collection.count_documents({}) == 0:
    print("Initializing default admin user...")
    admin_pass = os.getenv("SAURON_ADMIN_PWD", secrets.token_urlsafe(16))
    users_collection.insert_one({
        "username": "admin",
        "password": generate_password_hash(admin_pass) 
    })
    print("\n[*] CRITICAL: Default admin provisioned.")
    print("[*] USERNAME: admin")
    print(f"[*] PASSWORD: {admin_pass}")
    print("[*] SAVE THIS PASSWORD. It will not be displayed again.\n")


# --- Security Bouncers ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get("X-Api-Key")
        
        if provided_key == API_KEY:
            return f(*args, **kwargs)
            
        if probe_tokens_collection.find_one({"token": provided_key, "status": "active"}):
            return f(*args, **kwargs)
            
        return jsonify({"error": "Unauthorized. Token invalid or revoked."}), 401
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- NEW: LANDING PAGE ROUTE ---
@app.route('/')
def landing_page():
    if 'user' in session:
        return redirect(url_for('dashboard'))
        
    html_page = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Sauron Hub | Secure Your Smart Home</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <style>
            :root {
                --bg-void: #090814;
                --surface: #14122b;
                --primary-purple: #9d4edd;
                --glow-purple: 0 0 30px rgba(157, 78, 221, 0.4);
                --text-muted: #8b87a8;
            }
            body { 
                background-color: var(--bg-void); 
                color: #f8f9fa; 
                font-family: 'Inter', sans-serif; 
                overflow-x: hidden;
                background-image: radial-gradient(circle at top right, rgba(157, 78, 221, 0.15), transparent 50%),
                                  radial-gradient(circle at bottom left, rgba(157, 78, 221, 0.05), transparent 40%);
            }
            .navbar { padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,0.05); backdrop-filter: blur(10px); }
            .hero-section { padding: 100px 0 60px; text-align: center; }
            .hero-title { font-size: 4rem; font-weight: 800; letter-spacing: -1.5px; margin-bottom: 20px; text-transform: uppercase; }
            .hero-subtitle { color: var(--text-muted); font-size: 1.15rem; max-width: 650px; margin: 0 auto 40px; line-height: 1.6; }
            
            .feature-card { 
                background: rgba(20, 18, 43, 0.6); 
                border: 1px solid #2b2757; 
                border-radius: 12px; 
                padding: 40px; 
                transition: 0.3s;
                height: 100%;
                backdrop-filter: blur(10px);
            }
            .feature-card:hover { transform: translateY(-10px); border-color: var(--primary-purple); box-shadow: var(--glow-purple); }
            .feature-icon { color: var(--primary-purple); font-size: 2.5rem; margin-bottom: 20px; display: block; }
            
            .btn-cyber { 
                background-color: var(--primary-purple); 
                color: white; 
                font-weight: 800; 
                padding: 15px 40px; 
                border-radius: 4px; 
                text-transform: uppercase; 
                letter-spacing: 2px;
                box-shadow: var(--glow-purple);
                transition: 0.3s;
                text-decoration: none;
                display: inline-block;
            }
            .btn-cyber:hover { background-color: #b166eb; color: white; transform: scale(1.05); }
            .btn-cyber-outline { background: transparent; border: 1px solid var(--primary-purple); color: var(--primary-purple); padding: 10px 25px; border-radius: 4px; font-weight: 700; letter-spacing: 1px; text-decoration: none; transition: 0.3s; text-transform: uppercase; }
            .btn-cyber-outline:hover { background: var(--primary-purple); color: white; box-shadow: var(--glow-purple); }
            
            .impact-section { background-color: rgba(0,0,0,0.4); border-top: 1px solid #2b2757; border-bottom: 1px solid #2b2757; padding: 80px 0; margin-top: 60px; }
        </style>
    </head>
    <body>
        <nav class="navbar sticky-top">
            <div class="container d-flex justify-content-between align-items-center">
                <span class="fw-bold" style="font-size: 1.2rem; letter-spacing: 1px;"><i class="bi bi-hexagon-fill me-2" style="color: var(--primary-purple);"></i>SAURON HUB</span>
                <div>
                    <a href="/login" class="btn-cyber-outline me-3">Login</a>
                    <a href="/register" class="text-white text-decoration-none fw-bold" style="font-size: 0.9rem;">Sign Up &rarr;</a>
                </div>
            </div>
        </nav>

        <section class="hero-section container">
            <h1 class="hero-title">Total Visibility. <br><span style="color: var(--primary-purple);">Unmatched Privacy.</span></h1>
            <p class="hero-subtitle">Your smart home shouldn't be a black box. Sauron Hub is an enterprise-grade IoT management platform built to monitor the health, verify the integrity, and secure the data of your everyday devices.</p>
            <a href="/register" class="btn-cyber">Establish Security</a>
        </section>

        <section class="impact-section">
            <div class="container">
                <div class="row align-items-center g-5">
                    <div class="col-lg-6">
                        <h2 class="fw-bold mb-4" style="color: white; letter-spacing: -1px;">Protecting Your Day-to-Day.</h2>
                        <div class="d-flex mb-4">
                            <i class="bi bi-shield-lock-fill fs-3 me-3" style="color: var(--primary-purple);"></i>
                            <div>
                                <h5 class="fw-bold mb-1">Peace of Mind</h5>
                                <p class="text-muted small mb-0">Know exactly what firmware your interior cameras and smart locks are running, ensuring zero-day exploits can't compromise your privacy.</p>
                            </div>
                        </div>
                        <div class="d-flex mb-4">
                            <i class="bi bi-activity fs-3 me-3" style="color: var(--primary-purple);"></i>
                            <div>
                                <h5 class="fw-bold mb-1">Automated Defense</h5>
                                <p class="text-muted small mb-0">Stop checking forums for vulnerabilities. Our global threat intelligence engine automatically flags devices that require critical OTA patches.</p>
                            </div>
                        </div>
                        <div class="d-flex">
                            <i class="bi bi-wifi-off fs-3 me-3" style="color: var(--primary-purple);"></i>
                            <div>
                                <h5 class="fw-bold mb-1">Network Hygiene</h5>
                                <p class="text-muted small mb-0">Deploy local reconnaissance agents to sweep your subnet, instantly identifying rogue hardware hogging bandwidth or sniffing your traffic.</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card p-4 border-secondary" style="background: rgba(20, 18, 43, 0.4);">
                            <div class="terminal-box" style="font-family: 'Roboto Mono', monospace; font-size: 0.85rem; color: #00ff88; line-height: 1.8;">
                                > INITIALIZING SUBNET SWEEP...<br>
                                > PINGING 192.168.1.0/24...<br>
                                > 3 DEVICES DETECTED.<br>
                                <span class="text-danger">> WARNING: 1 DEVICE FIRMWARE OUTDATED.</span><br>
                                > DEPLOYING PATCH PROTOCOL...
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </body>
    </html>
    """
    return html_page


# --- AUTHENTICATION ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute") 
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    error_msg = ""
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_record = users_collection.find_one({"username": username})
        
        if user_record and check_password_hash(user_record['password'], password):
            session['user'] = username 
            return redirect(url_for('dashboard'))
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
            <div class="text-center mt-3">
                <a href="/" class="text-white text-decoration-none small">&larr; Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html_page

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('dashboard'))

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
            return redirect(url_for('dashboard'))

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
            <div class="text-center mt-3">
                <a href="/" class="text-white text-decoration-none small">&larr; Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    """
    return html_page

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('landing_page'))


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

@app.route('/api/device/add', methods=['POST'])
@require_api_key
def add_device():
    data = request.get_json()
    device_name = data.get("device_name", "").strip()
    version = data.get("version", "").strip()
    owner = session.get('user')
    
    if not owner:
        return jsonify({"error": "You must be logged in."}), 403
    if not device_name:
        return jsonify({"error": "Device name cannot be empty."}), 400
    if devices_collection.find_one({"device_name": device_name, "owner": owner}):
        return jsonify({"error": "You already have a device with this name."}), 409

    try:
        devices_collection.insert_one({
            "device_name": device_name,
            "owner": owner, 
            "version": version if version else "Unknown",
            "status": "offline", 
            "battery": "N/A", 
            "temperature": "N/A"
        })
        if not firmware_collection.find_one({"model": device_name}):
            firmware_collection.insert_one({"model": device_name, "latest_version": version if version else "1.0.0"})
        return jsonify({"status": "success", "message": f"{device_name} added."}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/device/remove', methods=['POST'])
@require_api_key
def remove_device():
    data = request.get_json()
    device_name = data.get("device_name")
    owner = session.get('user')

    if not device_name or not owner:
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        result = devices_collection.delete_one({"device_name": device_name, "owner": owner})
        if result.deleted_count == 1:
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"error": "Not found or lack clearance."}), 404
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


# --- SCAN MANAGEMENT ROUTES ---

@app.route('/api/probe/download')
@login_required
def download_probe():
    server_url = "https://sauroniot.com"
    unique_probe_token = f"sauron_pt_{secrets.token_hex(16)}"
    
    probe_tokens_collection.insert_one({
        "token": unique_probe_token,
        "issued_by": session.get('user'),
        "issued_at": datetime.utcnow(),
        "status": "active"
    })
    
    probe_code = f"""import requests
import time
import subprocess
import re
import socket
import threading
import platform

# --- PROBE CONFIGURATION ---
C2_SERVER = "{server_url}" 
API_KEY = "{unique_probe_token}"

HEADERS = {{"Content-Type": "application/json", "X-Api-Key": API_KEY}}

# Expanded with a few more common Google MAC Prefixes
IOT_VENDORS = {{
    "f4:f5:d8": "Google Device",
    "da:a1:19": "Google Home",
    "d8:bd:b9": "Nest Cam",
    "20:df:b9": "Google Device", 
    "f8:8a:5e": "Google Device", 
    "1c:f2:9a": "Google Device",
    "48:b4:23": "Google Device",
    "44:65:0d": "Amazon Echo",
    "74:c2:46": "Amazon Ring",
    "00:17:88": "Philips Hue",
    "b8:27:eb": "Raspberry Pi", 
    "e8:db:84": "Tuya Smart Plug"
}}

def update_c2_status(message):
    print(f"[*] {{message}}")
    try:
        requests.post(f"{{C2_SERVER}}/api/probe/update_status", json={{"message": message}}, headers=HEADERS)
    except Exception:
        pass

def get_local_subnet():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "192.168.1.1"
    finally:
        s.close()
    return '.'.join(ip.split('.')[:-1])

def ping_host(ip):
    sys_name = platform.system().lower()
    if sys_name == 'windows':
        param, timeout_param, timeout_val = '-n', '-w', '1000'
    elif sys_name == 'darwin':
        param, timeout_param, timeout_val = '-c', '-W', '1000'
    else:
        param, timeout_param, timeout_val = '-c', '-W', '1'
        
    subprocess.run(['ping', param, '1', timeout_param, timeout_val, ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def active_ping_sweep():
    subnet = get_local_subnet()
    update_c2_status(f"WARNING: Initiating ACTIVE aggressive ping sweep on {{subnet}}.0/24...")
    
    threads = []
    for i in range(1, 255):
        ip = f"{{subnet}}.{{i}}"
        t = threading.Thread(target=ping_host, args=(ip,))
        t.start()
        threads.append(t)
        time.sleep(0.005) # Stagger threads to prevent macOS dropping them
    
    for t in threads:
        t.join()
        
    update_c2_status("Active sweep complete. ARP cache heavily populated.")

def scan_lan():
    active_ping_sweep()
    update_c2_status("Extracting topology from ARP tables...")
    
    # Use -an to prevent slow DNS lookups and ensure consistent formatting
    sys_name = platform.system().lower()
    arp_flag = '-a' if sys_name == 'windows' else '-an'
    result = subprocess.run(['arp', arp_flag], capture_output=True, text=True)
    
    # Bulletproof Regex: Hunts strictly for IP and MAC patterns, ignoring surrounding text
    ip_pattern = re.compile(r'([0-9]{{1,3}}\.[0-9]{{1,3}}\.[0-9]{{1,3}}\.[0-9]{{1,3}})')
    mac_pattern = re.compile(r'([0-9a-fA-F]{{1,2}}[:-][0-9a-fA-F]{{1,2}}[:-][0-9a-fA-F]{{1,2}}[:-][0-9a-fA-F]{{1,2}}[:-][0-9a-fA-F]{{1,2}}[:-][0-9a-fA-F]{{1,2}})')

    iot_count = 0
    for line in result.stdout.splitlines():
        ip_match = ip_pattern.search(line)
        mac_match = mac_pattern.search(line)
        
        if ip_match and mac_match:
            ip = ip_match.group(1)
            raw_mac = mac_match.group(1).replace('-', ':')
            
            # MAC OS FIX: Pad single digits with zeros (e.g. 'a:b:c' -> '0a:0b:0c')
            padded_mac = ':'.join([p.zfill(2) for p in raw_mac.split(':')])
            mac_prefix = padded_mac[:8].lower()
            
            # Ignore broadcast MACs
            if padded_mac == "ff:ff:ff:ff:ff:ff":
                continue
                
            print(f"    [Local Debug] Found IP: {{ip}} -> MAC: {{padded_mac}}")
            
            if mac_prefix in IOT_VENDORS:
                iot_count += 1
                device_type = IOT_VENDORS[mac_prefix]
                device_name = f"Discovered {{device_type}} ({{ip}})"
                update_c2_status(f"Found IoT: {{device_name}} [MAC: {{padded_mac}}]")

                payload = {{"device_name": device_name, "version": "1.0.0"}}
                try:
                    r = requests.post(f"{{C2_SERVER}}/api/device/add", json=payload, headers=HEADERS, timeout=5)
                    if r.status_code == 201:
                        update_c2_status(f"Uploaded {{device_type}} to Sauron Cloud")
                except Exception:
                    pass

    update_c2_status(f"Recon phase complete. Uploaded {{iot_count}} devices.")
    time.sleep(2)
    update_c2_status("Returning to stealth mode.")
    try:
        requests.post(f"{{C2_SERVER}}/api/probe/stop_scan", headers=HEADERS)
    except Exception:
        pass

def start_beacon():
    print("=== SAURON PROBE ONLINE ===")
    print(f"Targeting C2 Server: {{C2_SERVER}}")
    while True:
        try:
            response = requests.get(f"{{C2_SERVER}}/api/probe/poll", headers=HEADERS, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("command") == "scan_lan":
                    print("\\n[!] CRITICAL: LAN SCAN COMMAND RECEIVED FROM C2")
                    scan_lan()
            elif response.status_code == 401:
                print("[-] CRITICAL ERROR: Access Token Revoked or Invalid. Terminating.")
                break
        except Exception:
            pass
        
        time.sleep(3) 

if __name__ == "__main__":
    try:
        start_beacon()
    except KeyboardInterrupt:
        print("\\nProbe disconnected.")
"""
    return app.response_class(
        probe_code,
        mimetype='text/x-python',
        headers={'Content-Disposition': 'attachment;filename=sauron_probe.py'}
    )

@app.route('/api/probe/trigger_scan', methods=['POST'])
@require_api_key
def trigger_scan():
    try:
        system_state.update_one(
            {"setting": "scan_status"}, 
            {"$set": {"is_scanning": True, "scan_message": "Initializing subnet sweep. Awaiting probe check-in..."}}, 
            upsert=True
        )
        commands_collection.update_one(
            {"target": "lan_probe"}, 
            {"$set": {"action": "scan_lan", "timestamp": datetime.utcnow()}},
            upsert=True
        )
        return jsonify({"status": "success", "message": "Scan command queued."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/probe/stop_scan', methods=['POST'])
@require_api_key
def stop_scan():
    try:
        system_state.update_one({"setting": "scan_status"}, {"$set": {"is_scanning": False, "scan_message": ""}}, upsert=True)
        commands_collection.delete_many({"target": "lan_probe", "action": "scan_lan"})
        return jsonify({"status": "success", "message": "Scan aborted."}), 200
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

@app.route('/api/probe/update_status', methods=['POST'])
@require_api_key
def update_probe_status():
    try:
        data = request.get_json()
        message = data.get("message", "Mapping subnet...")
        system_state.update_one({"setting": "scan_status"}, {"$set": {"scan_message": message}}, upsert=True)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/probe/get_status', methods=['GET'])
@login_required
def get_probe_status():
    try:
        scan_doc = system_state.find_one({"setting": "scan_status"})
        message = scan_doc.get("scan_message", "Awaiting telemetry...") if scan_doc else ""
        return jsonify({"message": message}), 200
    except Exception:
        return jsonify({"message": "Link lost..."}), 500


# --- Dashboard Routes (Human-facing, protected by Session) ---

@app.route('/dashboard')
@login_required  
def dashboard():
    operator_name = session.get('user', 'Operator').upper()
    
    all_devices = list(devices_collection.find({"owner": session.get('user')}).sort("last_seen", -1))
    firmware_docs = firmware_collection.find()
    LATEST_FIRMWARE = {doc['model']: doc['latest_version'] for doc in firmware_docs}

    dropdown_options = ""
    for model in sorted(LATEST_FIRMWARE.keys()):
        dropdown_options += f'<option value="{model}">{model}</option>'
    
    scan_doc = system_state.find_one({"setting": "scan_status"})
    is_scanning = scan_doc.get("is_scanning", False) if scan_doc else False
    current_scan_message = scan_doc.get("scan_message", "Awaiting telemetry...") if scan_doc else "Awaiting telemetry..."

    if is_scanning:
        scan_btn_html = """
            <button class="btn btn-danger me-3" onclick="stopLanScan()" style="font-weight: 700; letter-spacing: 1px; font-size: 0.8rem; box-shadow: 0 0 20px rgba(255, 51, 102, 0.4);">
                <i class="bi bi-stop-circle me-2"></i> ABORT SCAN
            </button>
        """
        scan_banner_html = f"""
            <div class="alert mb-4 d-flex align-items-center" style="background-color: rgba(157, 78, 221, 0.1); border: 1px solid var(--primary-purple); color: white; border-radius: 6px;">
                <span class="spinner-grow spinner-grow-sm me-3" style="color: var(--primary-purple);" role="status"></span>
                <div>
                    <strong style="color: var(--primary-purple); letter-spacing: 1px;">ACTIVE RECONNAISSANCE:</strong> <span id="live-scan-status" style="font-family: 'Roboto Mono', monospace;">{current_scan_message}</span>
                </div>
            </div>
        """
    else:
        scan_btn_html = """
            <a href="#provision-card" class="btn btn-cyber me-2" style="font-size: 0.8rem;">
                <i class="bi bi-plus-lg me-2"></i> PROVISION DEVICE
            </a>
            <button class="btn btn-cyber-outline me-3" data-bs-toggle="modal" data-bs-target="#lanScanModal" title="Requires Local Agent" style="padding: 10px 15px;">
                <i class="bi bi-radar"></i>
            </button>
        """
        scan_banner_html = ""

    def format_time(dt):
        return dt.strftime('%b %d, %H:%M:%S') if dt else "Never"

    # FIXED: The <meta http-equiv="refresh" content="10"> tag has been deleted from the <head> block below!
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
                <a class="navbar-brand d-flex align-items-center" href="/">
                    <i class="bi bi-hexagon-fill me-2" style="color: var(--primary-purple); text-shadow: var(--glow-purple);"></i>
                    SAURON PLATFORM
                </a>
                
                <div class="d-flex align-items-center">
                    <span class="small fw-bold me-4" style="color: #aeb2b8; letter-spacing: 1px;">
                        <i class="bi bi-person-bounding-box me-2" style="color: #9d4edd;"></i>USER: <span class="text-white">{operator_name}</span>
                    </span>
                    {scan_btn_html}
                    <a href="/logout" class="btn btn-cyber-outline"><i class="bi bi-box-arrow-right me-1"></i> DISCONNECT</a>
                </div>
            </div>
        </nav>

        <div class="container-fluid px-5">
            {scan_banner_html}
            
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

    if not all_devices:
        html_page += """
                            <tr>
                                <td colspan="6" class="text-center py-5">
                                    <i class="bi bi-hdd-network" style="font-size: 3rem; color: #2b2757;"></i>
                                    <h4 class="mt-3 fw-bold" style="letter-spacing: 1px; color: #aeb2b8;">NO ENDPOINTS DETECTED</h4>
                                    <p class="mb-4" style="color: #aeb2b8;">Sauron's Eye is currently monitoring 0 active devices.</p>
                                    
                                    <div class="d-flex flex-column align-items-center justify-content-center gap-3 mt-4">
                                        <a href="#provision-card" class="btn btn-cyber px-5 py-2" style="font-size: 0.9rem;">
                                            <i class="bi bi-terminal me-2"></i> MANUALLY PROVISION ENDPOINT
                                        </a>
                                        <button class="btn btn-link text-muted text-decoration-none" data-bs-toggle="modal" data-bs-target="#lanScanModal" style="font-size: 0.75rem; letter-spacing: 0.5px;">
                                            <i class="bi bi-radar me-1"></i> Run Advanced LAN Scan (Requires Local Agent)
                                        </button>
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
                                    <input type="text" class="form-control" id="new_device_name" required placeholder="e.g. Google Home">
                                </div>
                                <div class="mb-4">
                                    <label for="new_device_version" class="form-label">BASELINE FIRMWARE</label>
                                    <input type="text" class="form-control" id="new_device_version" placeholder="e.g. 1.0.0">
                                </div>
                                
                                <div class="p-3 mb-4 rounded" style="background-color: rgba(157, 78, 221, 0.05); border: 1px dashed #2b2757;">
                                    <p class="mb-0" style="font-size: 0.8rem; color: #aeb2b8; line-height: 1.5;">
                                        <i class="bi bi-info-circle me-2" style="color: var(--primary-purple);"></i>
                                        <strong>Quick Tip:</strong> If you don't know your device's current firmware version, feel free to ask it directly! <em>(e.g., "Hey Google, what is your firmware version?")</em>
                                    </p>
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
                                    <select class="form-control mb-3" id="device_name_input" required style="appearance: auto;">
                                    <option value="" disabled selected>Select a device model...</option>
                                    {dropdown_options}
                                    </select>
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

        <div class="modal fade" id="lanScanModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content" style="background-color: #14122b; border: 1px solid #ff3366; box-shadow: 0 0 30px rgba(255, 51, 102, 0.2);">
                    <div class="modal-header" style="border-bottom: 1px solid #2b2757;">
                        <h5 class="modal-title fw-bold" style="color: #ff3366; letter-spacing: 1px;"><i class="bi bi-exclamation-triangle-fill me-2"></i> SECURITY CLEARANCE REQUIRED</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body p-4">
                        <p style="color: #f8f9fa;">You are requesting the deployment of the <strong>Sauron C2 Agent</strong> to your local machine.</p>
                        
                        <div class="p-3 mb-4 rounded" style="background-color: rgba(255, 51, 102, 0.1); border: 1px solid rgba(255, 51, 102, 0.3);">
                            <p class="mb-0 fw-bold" style="font-size: 0.85rem; color: #ff3366;">
                                <i class="bi bi-shield-x me-2"></i>WARNING: Run this script ONLY on a network you own or have explicit authorization to audit. Do not leave the agent running indefinitely. Immediately delete `sauron_probe.py` once your reconnaissance is complete.
                            </p>
                        </div>
                        
                        <ol style="color: #aeb2b8; font-size: 0.9rem;">
                            <li class="mb-2">Download the Python agent below.</li>
                            <li class="mb-2">Install the required network library: <code style="color: #9d4edd; background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 3px;">pip3 install requests</code></li>
                            <li class="mb-2">Run the script in your local terminal:<br>
                                <span class="text-muted small">Mac/Linux:</span> <code style="color: #9d4edd; background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 3px;">python3 sauron_probe.py</code><br>
                                <span class="text-muted small">Windows:</span> <code style="color: #9d4edd; background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 3px;">python sauron_probe.py</code>
                            </li>
                            <li>Once the agent says "ONLINE", click "Initiate Target Scan".</li>
                        </ol>
                    </div>
                    <div class="modal-footer" style="border-top: 1px solid #2b2757;">
                        <a href="/api/probe/download" class="btn btn-cyber-outline me-auto" style="border-color: #aeb2b8; color: #aeb2b8;"><i class="bi bi-download me-2"></i> 1. DOWNLOAD AGENT</a>
                        <button type="button" class="btn btn-danger" onclick="triggerLanScan()" style="box-shadow: 0 0 15px rgba(255, 51, 102, 0.4);"><i class="bi bi-radar me-2"></i> 2. INITIATE SCAN</button>
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

            if(document.getElementById('live-scan-status')) {{
                setInterval(() => {{
                    fetch('/api/probe/get_status')
                    .then(res => res.json())
                    .then(data => {{
                        document.getElementById('live-scan-status').innerText = data.message;
                    }});
                }}, 1500); 
            }}

            function triggerLanScan() {{
                fetch('/api/probe/trigger_scan', {{ method: 'POST', headers: API_HEADERS }})
                .then(() => window.location.reload());
            }}

            function stopLanScan() {{
                fetch('/api/probe/stop_scan', {{ method: 'POST', headers: API_HEADERS }})
                .then(() => window.location.reload());
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

    def build_audit_html(text_color, icon, title, message, threat_box=""):
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Audit Result | Sauron Hub</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
            <style>
                body {{ background-color: #090814; color: #f8f9fa; font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                .card {{ background-color: #14122b; border: 1px solid #2b2757; border-radius: 8px; max-width: 500px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
                .terminal-box {{ background-color: rgba(0,0,0,0.3); border: 1px solid #2b2757; border-radius: 4px; padding: 15px; font-family: 'Roboto Mono', monospace; margin-bottom: 20px;}}
                .btn-cyber {{ background-color: transparent; color: #fff; border: 1px solid #2b2757; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; padding: 12px; transition: 0.3s; }}
                .btn-cyber:hover {{ background-color: rgba(255,255,255,0.05); color: #fff; border-color: #8b87a8;}}
            </style>
        </head>
        <body>
            <div class="card p-5 text-center">
                <div class="mb-4">{icon}</div>
                <h2 class="fw-bold mb-3" style="color: {text_color}; text-transform: uppercase; letter-spacing: 2px;">{title}</h2>
                <div class="terminal-box fw-bold text-secondary">{clean_device_name.upper()}</div>
                <p class="mb-4 fs-6" style="color: #aeb2b8;">{message}</p>
                {threat_box}
                <a href="/dashboard" class="btn-cyber w-100 text-decoration-none d-block mt-4"><i class="bi bi-arrow-left me-2"></i>Return to Platform</a>
            </div>
        </body>
        </html>
        """

    if not firmware_version:
        if is_machine:
            return jsonify({"error": "Missing firmware_version parameter"}), 400
        return build_audit_html("#ff3366", '<i class="bi bi-x-hexagon-fill" style="font-size: 4rem; color: #ff3366;"></i>', "System Error", "Missing firmware_version parameter."), 400

    safe_device_name = re.escape(clean_device_name)
    fw_doc = firmware_collection.find_one({"model": {"$regex": f"^{safe_device_name}$", "$options": "i"}})

    if fw_doc:
        true_baseline = fw_doc.get("latest_version")
        
        if true_baseline == firmware_version:
            if is_machine:
                return jsonify({"status": "up_to_date", "current_version": true_baseline}), 200
            return build_audit_html("#00ff88", '<i class="bi bi-shield-fill-check" style="font-size: 4rem; color: #00ff88; text-shadow: 0 0 20px rgba(0,255,136,0.4);"></i>', "Integrity Verified", f"Target is running the latest authorized baseline (v{true_baseline})."), 200
        else:
            if is_machine:
                return jsonify({"status": "update_required", "latest_version": true_baseline}), 200
            
            severity = fw_doc.get("severity", "WARNING")
            notes = fw_doc.get("release_notes", "No additional context available.")
            threat_box = f"""
            <div class="alert text-start p-3" style="background-color: rgba(255, 51, 102, 0.05); border: 1px solid rgba(255, 51, 102, 0.3); border-radius: 4px;">
                <div style="color: #ff3366; font-size: 0.75rem; font-weight: 800; letter-spacing: 1px; margin-bottom: 5px;"><i class="bi bi-bug-fill me-1"></i> THREAT INTEL: SEVERITY {severity}</div>
                <div style="color: #f8f9fa; font-size: 0.85rem; font-family: 'Roboto Mono', monospace;">{notes}</div>
            </div>
            """

            return build_audit_html("#ff9d00", '<i class="bi bi-shield-fill-exclamation" style="font-size: 4rem; color: #ff9d00; text-shadow: 0 0 20px rgba(255,157,0,0.4);"></i>', "Vulnerability Detected", f"Reported version is v{firmware_version}, but the secure baseline is <b>v{true_baseline}</b>. Immediate patching advised.", threat_box), 200

    if is_machine:
        return jsonify({"error": "Device not found."}), 404
    return build_audit_html("#f8f9fa", '<i class="bi bi-question-square" style="font-size: 4rem; color: #2b2757;"></i>', "Unknown Target", "Target identity not found in the Sauron registry."), 404

# --- AUTOMATED THREAT INTEL ENGINE ---
def fetch_global_threat_intel():
    """
    Background job that runs every 24 hours to pull new CVEs and firmware baselines.
    Simulating a comprehensive feed of the most common consumer IoT devices.
    """
    print("\n[SAURON INTEL] Waking up. Polling global threat feeds...")
    
    try:
        simulated_live_feed = [
            {"model": "Google Home", "latest_version": "3.80.1111", "severity": "CRITICAL", "release_notes": "URGENT: Patches zero-day buffer overflow in mDNS responder (CVE-2026-1094)."},
            {"model": "Google Nest Hub", "latest_version": "Fuchsia 14.20230831.4", "severity": "MEDIUM", "release_notes": "Resolves minor UI thread locking and patches Cast protocol memory leak."},
            {"model": "Echo 4th gen", "latest_version": "v12584499999", "severity": "MEDIUM", "release_notes": "Routine security patch addressing Bluetooth LE pairing vulnerabilities."},
            {"model": "Apple HomePod mini", "latest_version": "AudioOS 17.4.1", "severity": "HIGH", "release_notes": "Addresses a WebKit vulnerability that could allow arbitrary code execution via malicious audio streams."},
            {"model": "Nest Outdoor Cam", "latest_version": "v1.72", "severity": "CRITICAL", "release_notes": "Fixes cryptographic downgrade attack forcing unencrypted video broadcast."},
            {"model": "Ring Video Doorbell", "latest_version": "v3.1.5", "severity": "HIGH", "release_notes": "Mitigates Wi-Fi deauthentication attack vector designed to blind the camera."},
            {"model": "Wyze Cam v3", "latest_version": "4.36.11.8391", "severity": "CRITICAL", "release_notes": "Patches an unauthenticated remote access flaw allowing camera feed hijacking."},
            {"model": "Arlo Pro 4", "latest_version": "1.080.20.1", "severity": "LOW", "release_notes": "Improves battery optimization and fixes a minor DNS resolution delay."},
            {"model": "Nest Learning Thermostat", "latest_version": "6.2-27", "severity": "MEDIUM", "release_notes": "Patches a localized DoS vulnerability that could force the device into a reboot loop."},
            {"model": "Ecobee SmartThermostat", "latest_version": "4.7.5.352", "severity": "LOW", "release_notes": "Fixes integration timeouts with third-party HVAC monitoring APIs."},
            {"model": "Philips Hue Bridge", "latest_version": "v1.108.2", "severity": "HIGH", "release_notes": "Patches a Zigbee buffer overflow that could allow the bridge to be used as a persistent pivot point."},
            {"model": "TP-Link Kasa Smart Plug", "latest_version": "1.0.8 Build 231115", "severity": "MEDIUM", "release_notes": "Secures local network API endpoints against unauthorized toggle commands."},
            {"model": "Wemo Smart Plug", "latest_version": "v2.00.11420", "severity": "CRITICAL", "release_notes": "Addresses a severe UPnP vulnerability allowing remote arbitrary command execution."},
            {"model": "Eero Pro 6", "latest_version": "v7.1.1-16", "severity": "HIGH", "release_notes": "Patches WPA3 downgrade vulnerability and improves mesh routing encryption."},
            {"model": "Google Nest WiFi", "latest_version": "14150.376.32", "severity": "MEDIUM", "release_notes": "Resolves guest network isolation bypass under specific routing conditions."}
        ]

        updates_applied = 0
        for intel in simulated_live_feed:
            result = firmware_collection.update_one(
                {"model": intel["model"]},
                {"$set": {
                    "latest_version": intel["latest_version"],
                    "severity": intel["severity"],
                    "release_notes": intel["release_notes"],
                    "last_updated": datetime.utcnow()
                }},
                upsert=True
            )
            if result.modified_count > 0 or result.upserted_id:
                updates_applied += 1

        print(f"[SAURON INTEL] Polling complete. Registry updated with {updates_applied} firmware baselines.\n")

    except Exception as e:
        print(f"[SAURON INTEL] Error reaching threat feeds: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=fetch_global_threat_intel, trigger="interval", hours=24, next_run_time=datetime.utcnow())
scheduler.start()

# We leave this here so you can test locally, but Gunicorn ignores it in production!
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)