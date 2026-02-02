#!/usr/bin/env python3
"""Minimal TTN example."""

from ttn_lora import TTN

ttn = TTN("/dev/ttyAMA0")
print(f"DevEUI: {ttn.dev_eui}")

ttn.join(
    app_eui="DFDFDFDF00000000",
    app_key="0102030405060708090A0B0C0D0E0F10"
)

ttn.send(b"Hello TTN!")
ttn.send({"temp": 22, "humidity": 65})

ttn.close()
