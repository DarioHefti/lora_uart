#!/usr/bin/env python3
"""
LoRa Test Script

Usage:
    pip install pyserial
    python lora.py
"""

from client import TTN, TTNError, Region

# =============================================================================
# CONFIGURATION - Update these to match TTN console!
# =============================================================================

SERIAL_PORT = "/dev/ttyS0"  # Windows: COM3, COM4 | RPi: /dev/ttyAMA0
REGION = Region.EU868

# TTN credentials (MUST match TTN console exactly)
APP_EUI = "0000000000000000"
APP_KEY = "0102030405060708090A0B0C0D0E0F10"

# =============================================================================

print("Connecting to LoRa module...")
ttn = TTN(SERIAL_PORT, region=REGION, debug=True)

print(f"\nDevEUI: {ttn.dev_eui}")
print(f"AppEUI: {APP_EUI}")
print(f"AppKey: {APP_KEY}")

print("\n" + "="*50)
print("IMPORTANT: Check TTN Console -> Live Data")
print("If join requests appear there, credentials may be wrong")
print("If nothing appears, gateway may not be receiving")
print("="*50 + "\n")

# Join TTN
ttn.join(app_eui=APP_EUI, app_key=APP_KEY)

# Send test message
ttn.send(b"Hello World!")
print(f"RSSI: {ttn.rssi} dBm, SNR: {ttn.snr} dB")

ttn.close()
