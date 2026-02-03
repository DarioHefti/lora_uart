# LoRa UART

Simple Python client for The Things Network via LoRaWAN.

Works with the DFRobot LoRaWAN Node Module (EU868).

## Requirements

```bash
pip install pyserial
```

## Quick Start

```python
from client import LoRa

lora = LoRa(
    port="/dev/ttyS0",
    app_eui="YOUR_APP_EUI",
    app_key="YOUR_APP_KEY",
)

lora.send("Hello World!")
lora.send({"temp": 23.5, "humidity": 65})
```

## Features

- **Auto queue management** - Messages are queued and sent in background
- **Rate limiting** - 30 seconds between sends (respects duty cycle)
- **Auto retry** - Failed sends retry up to 3 times
- **Queue limit** - Max 20 messages, oldest dropped when full

## API

```python
from client import LoRa, LoRaError, Region

try:
    # Connect and join automatically
    lora = LoRa(
        port="/dev/ttyS0",           # Serial port
        app_eui="...",               # From TTN console
        app_key="...",               # From TTN console
        region=Region.EU868,         # EU868, US915, or CN470
        data_rate=3,                 # 0-5 (lower = longer range)
        debug=True,                  # Enable logging
    )
    
    # Send messages (queued, returns immediately)
    lora.send("Hello!")                        # String
    lora.send(b"\x01\x02\x03")                 # Bytes
    lora.send({"temp": 23.5, "battery": 95})   # Dict (auto-encoded)
    
    # Check status
    print(lora.dev_eui)       # Device EUI (for TTN registration)
    print(lora.is_connected)  # True if joined
    print(lora.queue_size)    # Messages waiting
    print(lora.rssi)          # Signal strength (dBm)
    print(lora.snr)           # Signal-to-noise (dB)

except LoRaError as e:
    print(f"Error: {e}")
finally:
    lora.stop()
```

## Hardware Setup (Raspberry Pi)

| Module Pin | RPi Pin | GPIO |
|------------|---------|------|
| TX         | Pin 10  | GPIO 15 (RXD) |
| RX         | Pin 8   | GPIO 14 (TXD) |
| GND        | Pin 6   | GND |
| VCC        | Pin 1   | 3.3V |

### Enable UART

1. Run `sudo raspi-config`
2. Interface Options → Serial Port
3. No for "login shell over serial"
4. Yes for "serial port hardware enabled"
5. Reboot

## TTN Setup

1. Go to [TTN Console](https://console.cloud.thethings.network/)
2. Create an Application
3. Register a Device (OTAA)
4. Copy **AppEUI** and **AppKey** to your code
5. Run once to get **DevEUI**, add it to TTN console

## Data Encoding

When sending a dict, values are encoded compactly:

| Key | Encoding |
|-----|----------|
| `temp` / `temperature` | 2 bytes, signed, 0.1°C |
| `humidity` | 1 byte, 0.5% |
| `pressure` | 2 bytes, 0.1 hPa |
| `battery` | 1 byte, % |

TTN decoder:

```javascript
function decodeUplink(input) {
  return {
    data: {
      temp: ((input.bytes[0] << 8) | input.bytes[1]) / 10,
      humidity: input.bytes[2] / 2,
      battery: input.bytes[3]
    }
  };
}
```

## License

MIT
