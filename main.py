import serial
import csv

# Configuration - Match this to Arduino's port
SERIAL_PORT = 'COM5'
BAUD_RATE = 9600
FILE_NAME = ("baseline.csv")

try:
    # Initialize serial connection
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to {SERIAL_PORT}. Press Ctrl+C to stop.")

    with open(FILE_NAME, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Write CSV Header
        writer.writerow(["Timestamp_ms", "Accel_X", "Accel_Y", "Accel_Z", "Gyro_X", "Gyro_Y", "Gyro_Z"])

        while True:
            # Read one line from Serial
            line = ser.readline().decode('utf-8').strip()

            if line:
                # Split the comma-separated string into a list
                data_points = line.split(',')
                print(f"Recording: {data_points}")

                # Write to CSV file
                writer.writerow(data_points)

except KeyboardInterrupt:
    print("\nLogging stopped by user.")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Serial port closed.")