"""
TTN LoRaWAN client for DFRobot module.

Simple usage:
    from ttn_lora import TTN

    ttn = TTN("/dev/ttyAMA0")
    print(f"DevEUI: {ttn.dev_eui}")

    ttn.join(app_eui="...", app_key="...")
    ttn.send(b"Hello!")
"""

from .client import TTN, TTNError, Region

__all__ = ["TTN", "TTNError", "Region"]
__version__ = "1.0.0"
