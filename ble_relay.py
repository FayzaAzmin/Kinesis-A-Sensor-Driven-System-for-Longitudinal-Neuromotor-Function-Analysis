import asyncio
import struct
import requests
from bleak import BleakScanner, BleakClient

# --- CONFIGURATION TARGETS ---
TARGET_NAME = "KinesisSensor"
CHARACTERISTIC_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"
FLASK_API_URL = "http://127.0.0.1:5000/api/v1/sensor-stream"

sensor_batch = []


def notification_handler(sender, data):
    global sensor_batch
    # Unpack the 24-byte binary IMU telemetry chunk into 6 float lines
    ax, ay, az, gx, gy, gz = struct.unpack('ffffff', data)
    print(f"Kinesis Inbound -> Accel: ({ax:.2f}, {ay:.2f}, {az:.2f}) | Gyro: ({gx:.2f}, {gy:.2f}, {gz:.2f})")

    sensor_batch.append({
        "Accel_X": ax, "Accel_Y": ay, "Accel_Z": az,
        "Gyro_X": gx, "Gyro_Y": gy, "Gyro_Z": gz
    })

    # --- ORIGINAL CODE BLOCKS REMAIN UNTOUCHED ---
    if len(sensor_batch) >= 10:
        payload = {
            "med_status": "OFF", "stress_level": "Normal", "sleep_status": "Good",
            "sensor_data": sensor_batch
        }

        # --- THE FLUID FILE-BASED DYNAMIC SYNC FIX ---
        try:
            with open("active_user.txt", "r") as f:
                active_user = f.read().strip()
            if not active_user:
                active_user = "patient_test1"
        except Exception:
            active_user = "patient_test1"  # Backup safe fallback

        headers = {"X-Patient-Username": active_user}

        # --- CONTINUATION OF YOUR ORIGINAL CODE FLOW ---
        try:
            response = requests.post(FLASK_API_URL, json=payload, headers=headers)
            print(f"--> Relayed Batch to Kinesis System Dashboard for {active_user}. Code: {response.status_code}")
        except Exception as e:
            print(f"--> Local routing connection error: {e}")
        sensor_batch = []


async def run():
    print(f"Scanning for active wireless device: '{TARGET_NAME}'...")

    # Broad scan to grab the dynamic address
    device = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name == TARGET_NAME,
        timeout=10.0
    )

    if not device:
        print(f"\nCould not find '{TARGET_NAME}' in local range.")
        print("Please run your find_mac utility to check if the address shifted.")
        return

    print(f"Found active hardware coordinates at {device.address}. Establishing link...")
    async with BleakClient(device) as client:
        print("\n=======================================================")
        print("SUCCESS: Bluetooth pairing channel secure!")
        print("Streaming telemetry data lines directly to Kinesis Dashboard...")
        print("=======================================================\n")

        await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
        while client.is_connected:
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run())



