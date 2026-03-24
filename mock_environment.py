import requests
import time
import random

# Your EC2 Public IP and the new endpoint we just created
SERVER_URL = "http://13.56.200.180:5005/api/device/checkin"

# A list of devices to simulate
DEVICES = [
    "Ring Doorbell",
    "Echo 4th gen",
    "Google Home",
    "Nest Outdoor Cam",
    "Philips Hue Bulb"
]

def send_checkin(device_name):
    # Simulate realistic IoT data
    payload = {
        "device_name": device_name,
        "battery": random.randint(10, 100),
        "temp": random.randint(60, 80) # Fahrenheit
    }
    
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ [{device_name}] Check-in successful: {response.json()['message']}")
        else:
            print(f"❌ [{device_name}] Failed with status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Connection Error: {e}")

if __name__ == "__main__":
    print("🚀 Starting Sauron Mock Device Simulator...")
    try:
        while True:
            # Pick a random device and send a check-in
            target = random.choice(DEVICES)
            send_checkin(target)
            
            # Wait 5 seconds before the next "ping"
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopping simulator. Sauron's eye closes.")