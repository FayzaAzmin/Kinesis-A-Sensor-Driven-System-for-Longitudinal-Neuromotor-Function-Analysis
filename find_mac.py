import asyncio
from bleak import BleakScanner

async def main():
    print("Scanning for all local hardware addresses... Please wait 5 seconds...")
    devices = await BleakScanner.discover(timeout=5.0)
    print("\n--- FOUND DEVICES ---")
    for d in devices:
        print(f"Device Name: {d.name}  --->  Address/MAC: {d.address}")
    print("----------------------\nScan complete.")

if __name__ == "__main__":
    asyncio.run(main())