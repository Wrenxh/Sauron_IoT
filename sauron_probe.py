import subprocess
import re
import requests
import time

SERVER_URL = "http://13.56.200.180:5005/api/device/add"
POLL_URL = "http://13.56.200.180:5005/api/probe/poll"

API_KEY = "super_secret_cyber_key_2026"
HEADERS = {"X-Api-Key": API_KEY}

IOT_VENDORS = {
    "f4:f5:d8": "Google Device",
    "da:a1:19": "Google Home",
    "d8:bd:b9": "Nest Cam",
    "44:65:0d": "Amazon Echo",
    "74:c2:46": "Amazon Ring",
    "00:17:88": "Philips Hue",
    "b8:27:eb": "Raspberry Pi", 
    "e8:db:84": "Tuya Smart Plug"
}

def scan_lan():
    print("\n⚡ [COMMAND RECEIVED] Commencing local network scan...")
    result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
    pattern = re.compile(r'\((.*?)\)\s+at\s+([0-9a-f:]+)')
    found_devices = pattern.findall(result.stdout)

    iot_count = 0
    for ip, mac in found_devices:
        mac_prefix = mac[:8].lower()
        if mac_prefix in IOT_VENDORS:
            iot_count += 1
            device_type = IOT_VENDORS[mac_prefix]
            device_name = f"Discovered {device_type} ({ip})"
            print(f"  -> Found IoT: {device_name} [MAC: {mac}]")

            payload = {"device_name": device_name, "version": "1.0.0"}
            try:
                # INTEGRATED: Added headers=HEADERS here
                r = requests.post(SERVER_URL, json=payload, headers=HEADERS, timeout=5)
                
                if r.status_code == 201:
                    print("     ✅ Uploaded to Sauron Cloud")
                elif r.status_code == 409:
                    print("     ⚡ Already known to Cloud")
                elif r.status_code == 401:
                    print("     🛑 Blocked by Cloud Bouncer (Invalid API Key!)")
            except Exception as e:
                print(f"     ❌ Failed to upload: {e}")

    print(f"🏁 Scan complete. Uploaded {iot_count} devices to the cloud.\n")

def listen_for_commands():
    print("🎧 Sauron Probe Active. Listening for C2 commands from AWS...")
    while True:
        try:
            response = requests.get(POLL_URL, headers=HEADERS, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("command") == "scan_lan":
                    scan_lan()
                    print("🎧 Resuming listening protocol...")
            elif response.status_code == 401:
                print("🛑 Polling Blocked (Invalid API Key!). Check your .env setup.")
                
        except Exception:
            # Fail silently so the loop doesn't crash if the Wi-Fi drops momentarily
            pass
        
        # Sleep for 3 seconds before asking again to avoid spamming the server
        time.sleep(3)

if __name__ == "__main__":
    try:
        listen_for_commands()
    except KeyboardInterrupt:
        print("\nProbe disconnected.")