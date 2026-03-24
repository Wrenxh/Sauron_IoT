import requests
import time
import random

# Your EC2 Public IP base URL
SERVER_URL = "http://13.56.200.180:5005"
CHECKIN_ENDPOINT = f"{SERVER_URL}/api/device/checkin"
LIST_ENDPOINT = f"{SERVER_URL}/api/device/list"

def get_active_devices():
    """Fetches the live list of devices from the Sauron hub."""
    try:
        response = requests.get(LIST_ENDPOINT, timeout=5)
        if response.status_code == 200:
            return response.json().get("devices", [])
        else:
            print(f"⚠️ Failed to fetch devices. Server returned: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Could not connect to server to get device list: {e}")
    return []

def send_checkin(device_name):
    """Simulates realistic IoT data for a specific device."""
    payload = {
        "device_name": device_name,
        "battery": random.randint(10, 100),
        "temp": random.randint(60, 80) # Fahrenheit
    }
    
    try:
        response = requests.post(CHECKIN_ENDPOINT, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ [{device_name}] Check-in successful: {response.json().get('message', 'OK')}")
        else:
            print(f"❌ [{device_name}] Failed with status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Connection Error: {e}")

if __name__ == "__main__":
    print("🚀 Starting DYNAMIC Sauron Mock Device Simulator...")
    try:
        while True:
            # 1. Ask the server for the current list of devices
            current_devices = get_active_devices()
            
            # 2. Check if the database is empty
            if not current_devices:
                print("⚠️ No devices found in database. Waiting 5 seconds...")
                time.sleep(5)
                continue
                
            # 3. Pick a random device from the dynamic list and send a check-in
            target = random.choice(current_devices)
            send_checkin(target)
            
            # 4. Wait 5 seconds before the next "ping"
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopping simulator. Sauron's eye closes.")