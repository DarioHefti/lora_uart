# LoRa UART

Simple Python scripts for connecting to The Things Network via LoRaWAN.

Works with the DFRobot LoRaWAN Node Module (EU868).

## Files

- `client.py` - LoRa device interface (TTN class with all the serial/AT command logic)
- `lora.py` - Main script to run and test

## Requirements

```bash
pip install pyserial
```

## Quick Start

1. Edit `lora.py` and update:
   - `SERIAL_PORT` - Your COM port (Windows) or `/dev/ttyAMA0` (RPi)
   - `APP_EUI` - From TTN console
   - `APP_KEY` - From TTN console

2. Run:
   ```bash
   python lora.py
   ```

3. Copy the DevEUI shown and register it on TTN console

## Usage

The `lora.py` script will:
1. Connect to the LoRa module
2. Show the DevEUI (register this on TTN)
3. Join TTN using OTAA
4. Send sensor data in a loop

### Using client.py directly

```python
from client import TTN, TTNError, Region

# Connect
ttn = TTN("COM3", region=Region.EU868, debug=True)
print(f"DevEUI: {ttn.dev_eui}")

# Join TTN
ttn.join(
    app_eui="DFDFDFDF00000000",
    app_key="0102030405060708090A0B0C0D0E0F10"
)

# Send data
ttn.send(b"Hello!")
ttn.send({"temp": 22.5, "humidity": 65})

# Check signal
print(f"RSSI: {ttn.rssi} dBm, SNR: {ttn.snr} dB")

# Close
ttn.close()
```

## Hardware Setup (Raspberry Pi)

| Module Pin | RPi Pin | GPIO |
|------------|---------|------|
| TX         | Pin 10  | GPIO 15 (RXD) |
| RX         | Pin 8   | GPIO 14 (TXD) |
| GND        | Pin 6   | GND |
| VCC        | Pin 1   | 3.3V |

### Enable UART on RPi

1. Run `sudo raspi-config`
2. Go to **Interface Options** → **Serial Port**
3. Select **No** for "login shell over serial"
4. Select **Yes** for "serial port hardware enabled"
5. Reboot

## TTN Setup

1. Go to [TTN Console](https://console.cloud.thethings.network/)
2. Create an Application
3. Register a Device (OTAA)
4. Copy **AppEUI** and **AppKey** to `lora.py`
5. Run `python lora.py` to get the **DevEUI**
6. Enter DevEUI in TTN console

## Data Encoding

When sending a dict, values are auto-encoded:

| Key | Encoding |
|-----|----------|
| `temp` / `temperature` | 2 bytes, signed, 0.1°C resolution |
| `humidity` | 1 byte, 0.5% resolution |
| `pressure` | 2 bytes, 0.1 hPa resolution |
| `battery` | 1 byte, percentage |

TTN decoder example:

```javascript
function decodeUplink(input) {
  var data = {};
  data.temp = (input.bytes[0] << 8 | input.bytes[1]) / 10;
  data.humidity = input.bytes[2] / 2;
  data.battery = input.bytes[3];
  return { data: data };
}
```

## License

MIT
