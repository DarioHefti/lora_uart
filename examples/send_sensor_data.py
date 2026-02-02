#!/usr/bin/env python3
"""
Example: Send sensor data to TTN from Raspberry Pi.

Setup:
    1. pip install ttn-lora
    2. Connect DFRobot module to RPi UART (GPIO 14/15)
    3. Disable serial console: sudo raspi-config -> Interface -> Serial
    4. Register device on TTN and get AppEUI/AppKey
"""

import time
from ttn_lora import TTN

# Configuration
SERIAL_PORT = "/dev/ttyAMA0"  # RPi hardware UART
APP_EUI = "DFDFDFDF00000000"  # From TTN console
APP_KEY = "0102030405060708090A0B0C0D0E0F10"  # From TTN console


def read_sensors() -> dict:
    """Read sensor values (replace with your actual sensors)."""
    # Example: DHT22, BME280, etc.
    return {
        "temp": 22.5,      # °C
        "humidity": 65,    # %
        "battery": 85,     # %
    }


def main():
    print("=== TTN Sensor Node ===\n")

    # Connect to module
    ttn = TTN(SERIAL_PORT, debug=True)
    print(f"DevEUI: {ttn.dev_eui}")
    print("(Register this DevEUI on TTN console)\n")

    # Join TTN
    print("Joining TTN...")
    ttn.join(app_eui=APP_EUI, app_key=APP_KEY)
    print("Joined!\n")

    # Send data every 5 minutes
    while True:
        sensors = read_sensors()
        print(f"Sensors: {sensors}")

        ttn.send(sensors)
        print(f"Sent! RSSI: {ttn.rssi} dBm, SNR: {ttn.snr} dB\n")

        # Respect duty cycle - wait 5 minutes
        print("Sleeping 5 minutes...")
        ttn.sleep(300)


if __name__ == "__main__":
    main()
