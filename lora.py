#!/usr/bin/env python3
"""
LoRa Test Script

Usage:
    pip install pyserial
    python lora.py
"""

from client import TTN, TTNError, Region

# =============================================================================
# CONFIGURATION
# =============================================================================

SERIAL_PORT = "/dev/ttyS0"  # Windows: COM3, COM4 | RPi: /dev/ttyAMA0
REGION = Region.EU868

# TTN credentials (from TTN console)
APP_EUI = "0000000000000000"  # Can be all zeros for TTN v3
APP_KEY = "0102030405060708090A0B0C0D0E0F10"

# =============================================================================

print("Connecting to LoRa module...")
ttn = TTN(SERIAL_PORT, region=REGION, debug=True)

print(f"DevEUI: {ttn.dev_eui}")
print(f"AppEUI: {APP_EUI}")

# # Join and send example:
# ttn.join(app_eui=APP_EUI, app_key=APP_KEY)
# ttn.send(b"Hello World!")
# print(f"RSSI: {ttn.rssi} dBm, SNR: {ttn.snr} dB")

ttn.close()
