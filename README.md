# ttn-lora

Simple Python package for connecting to The Things Network via LoRaWAN on Raspberry Pi.

Works with the DFRobot LoRaWAN Node Module (EU868).

**Protocol verified against**: [DFRobot_LWNode Arduino Library](https://github.com/cdjq/DFRobot_LWNode)

## Installation

```bash
pip install ttn-lora
```

Or install from source:

```bash
cd ttn_lora
pip install -e .
```

## Quick Start

```python
from ttn_lora import TTN

ttn = TTN("/dev/ttyAMA0")
print(f"DevEUI: {ttn.dev_eui}")  # Register this on TTN

ttn.join(app_eui="...", app_key="...")
ttn.send(b"Hello!")
```

## Usage

### Basic

```python
from ttn_lora import TTN

# Connect
ttn = TTN("/dev/ttyAMA0")  # RPi UART
# ttn = TTN("COM3")        # Windows

# Get DevEUI for TTN registration
print(f"DevEUI: {ttn.dev_eui}")

# Join TTN (blocks until joined, up to 60s)
ttn.join(
    app_eui="DFDFDFDF00000000",
    app_key="0102030405060708090A0B0C0D0E0F10"
)

# Send data
ttn.send(b"\x01\x02\x03", port=1)
ttn.send("Hello TTN!")
ttn.send({"temp": 22.5, "humidity": 65})  # Auto-encoded

# Check signal quality
print(f"RSSI: {ttn.rssi} dBm, SNR: {ttn.snr} dB")

# Clean up
ttn.close()
```

### Context Manager

```python
from ttn_lora import TTN

with TTN("/dev/ttyAMA0") as ttn:
    ttn.join(app_eui="...", app_key="...")
    ttn.send({"temp": 22})
# Auto-closes when done
```

### Sensor Loop

```python
from ttn_lora import TTN
import time

ttn = TTN("/dev/ttyAMA0")
ttn.join(app_eui="...", app_key="...")

while True:
    # Read your sensors
    data = {"temp": 22.5, "humidity": 65, "battery": 85}
    
    ttn.send(data)
    time.sleep(300)  # Send every 5 minutes
```

## Raspberry Pi Setup

### Hardware Connection

| Module Pin | RPi Pin | GPIO |
|------------|---------|------|
| TX         | Pin 10  | GPIO 15 (RXD) |
| RX         | Pin 8   | GPIO 14 (TXD) |
| GND        | Pin 6   | GND |
| VCC        | Pin 1   | 3.3V |

### Enable UART

1. Run `sudo raspi-config`
2. Go to **Interface Options** → **Serial Port**
3. Select **No** for "login shell over serial"
4. Select **Yes** for "serial port hardware enabled"
5. Reboot

### Set DFRobot Module to UART Mode

1. Set the DIP switch on the module to UART position
2. Power cycle the module

## TTN Setup

1. Go to [TTN Console](https://console.cloud.thethings.network/)
2. Create an Application
3. Register a Device (OTAA)
4. Copy **AppEUI** and **AppKey**
5. Get **DevEUI** from your device: `print(ttn.dev_eui)`
6. Enter DevEUI in TTN console

## Data Encoding

When sending a dict, values are auto-encoded:

| Key | Encoding |
|-----|----------|
| `temp` / `temperature` | 2 bytes, signed, 0.1°C resolution |
| `humidity` | 1 byte, 0.5% resolution |
| `pressure` | 2 bytes, 0.1 hPa resolution |
| `battery` | 1 byte, percentage |

Example TTN decoder:

```javascript
function decodeUplink(input) {
  var data = {};
  data.temp = (input.bytes[0] << 8 | input.bytes[1]) / 10;
  data.humidity = input.bytes[2] / 2;
  data.battery = input.bytes[3];
  return { data: data };
}
```

## API Reference

### TTN(port, region, debug)

Create client.

- `port`: Serial port (default: `/dev/ttyAMA0`)
- `region`: `Region.EU868`, `US915`, etc. (default: EU868)
- `debug`: Enable debug logging (default: False)

### ttn.join(app_eui, app_key, timeout, data_rate, tx_power)

Join TTN via OTAA. Blocks until joined.

- `app_eui`: Application EUI (16 hex chars)
- `app_key`: Application Key (32 hex chars)
- `timeout`: Join timeout seconds (default: 60)
- `data_rate`: DR0-DR5 (default: 5 = SF7)
- `tx_power`: dBm (default: 14)

### ttn.send(data, port)

Send data to TTN.

- `data`: bytes, str, or dict
- `port`: fPort 1-223 (default: 1)

### Properties

- `ttn.dev_eui`: Device EUI (str)
- `ttn.is_joined`: Join status (bool)
- `ttn.rssi`: Last RSSI in dBm (int)
- `ttn.snr`: Last SNR in dB (int)

## License

MIT
