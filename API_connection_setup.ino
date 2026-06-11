#include <ArduinoBLE.h>
#include <Arduino_LSM6DSOX.h>

// Initialize BLE Service and Characteristics
BLEService imuService("19B10000-E8F2-537E-4F6C-D104768A1214");
BLECharacteristic imuDataChar("19B10001-E8F2-537E-4F6C-D104768A1214", BLERead | BLENotify, 24); // 24 bytes for 6 floats

void setup() {
  // 1. Give the hardware power rails 1.5 seconds to stabilize on boot
  delay(1500); 

  Serial.begin(115200);
  
  // 2. Initialize Hardware Components safely
  if (!IMU.begin() || !BLE.begin()) {
    Serial.println("Hardware initialization failed!");
    while (1);
  }

  // 3. Set broadcasting attributes
  BLE.setLocalName("KinesisSensor");
  BLE.setAdvertisedService(imuService);
  imuService.addCharacteristic(imuDataChar);
  BLE.addService(imuService);
  
  // 4. Force the antenna to start shouting its existence
  BLE.advertise();
  
  Serial.println("Bluetooth Peripheral Active. Awaiting Central Connection...");
}

void loop() {
  BLEDevice central = BLE.central();
  if (central && central.connected()) {
    Serial.println("Connected to Laptop Terminal System over BLE");
    
    while (central.connected()) {
      float imuBuffer[6]; // [ax, ay, az, gx, gy, gz]
      if (IMU.accelerationAvailable() && IMU.gyroscopeAvailable()) {
        IMU.readAcceleration(imuBuffer[0], imuBuffer[1], imuBuffer[2]);
        IMU.readGyroscope(imuBuffer[3], imuBuffer[4], imuBuffer[5]);
        
        // Write raw binary packet directly over the airwaves
        imuDataChar.writeValue((byte*)imuBuffer, 24);
      }
      delay(100); // 10Hz stream window tracking frequency
    }
    Serial.println("Disconnected from Laptop.");
  }
}