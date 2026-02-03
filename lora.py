#!/usr/bin/env python3
"""
LoRa Example - Shows how to use the LoRa client.

Usage:
    pip install pyserial
    python lora.py
"""

import time
from client import LoRa, LoRaError, Region

# =============================================================================
# CONFIGURATION
# =============================================================================

SERIAL_PORT = "/dev/ttyS0"  # or /dev/ttyAMA0 for hardware UART
REGION = Region.EU868

# TTN credentials (from TTN console)
APP_EUI = "2309199300000000"
APP_KEY = "0102030405060708090A0B0C0D0E0F10"

# =============================================================================

def main():
    lora = None
    
    try:
        # Connect and join (happens automatically)
        print("Connecting to LoRa module...")
        
        lora = LoRa(
            port=SERIAL_PORT,
            app_eui=APP_EUI,
            app_key=APP_KEY,
            region=REGION,
            debug=True,
        )
        
        print(f"DevEUI: {lora.dev_eui}")
        print(f"Connected: {lora.is_connected}")
        
        # Queue some messages (sent automatically in background)
        lora.send("Hello World!")
        lora.send({"temp": 23.5, "humidity": 65, "battery": 95})
        
        print(f"Queue size: {lora.queue_size}")
        
        # Keep running and watch messages get sent
        while True:
            time.sleep(10)
            print(f"Queue: {lora.queue_size} | RSSI: {lora.rssi} dBm | SNR: {lora.snr} dB")
            
    except LoRaError as e:
        print(f"LoRa error: {e}")
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if lora:
            lora.stop()


if __name__ == "__main__":
    main()
