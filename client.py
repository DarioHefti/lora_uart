"""LoRaWAN client - interfaces with DFRobot LoRa module via serial."""

import time
import logging
from enum import Enum
from typing import Union

import serial

logger = logging.getLogger(__name__)


class Region(Enum):
    """LoRaWAN frequency regions."""
    EU868 = "EU868"
    US915 = "US915"
    CN470 = "CN470"


class TTNError(Exception):
    """TTN operation error."""
    pass


class TTN:
    """
    Simple TTN LoRaWAN client for DFRobot module.

    Protocol matches DFRobot_LWNode Arduino library:
    https://github.com/cdjq/DFRobot_LWNode

    Example:
        ttn = TTN("/dev/ttyAMA0")
        print(f"DevEUI: {ttn.dev_eui}")

        ttn.join(app_eui="DFDFDFDF00000000", app_key="0102030405060708090A0B0C0D0E0F10")
        ttn.send(b"Hello TTN!")

    On Raspberry Pi:
        - Use /dev/ttyAMA0 (hardware UART) or /dev/ttyS0
        - Disable serial console in raspi-config first
    
    On Windows:
        - Use COM3, COM4, etc.
    """

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        region: Region = Region.EU868,
        debug: bool = False,
    ):
        """
        Initialize TTN client.

        Args:
            port: Serial port (RPi: /dev/ttyAMA0, Windows: COM3)
            region: LoRaWAN region (default: EU868)
            debug: Enable debug logging
        """
        self._port_name = port
        self._region = region
        self._debug = debug
        self._joined = False

        if debug:
            logging.basicConfig(level=logging.DEBUG)

        # Open serial connection (9600 8N1 per DFRobot spec)
        self._serial = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=5,
        )
        
        # Wait for module to be ready
        time.sleep(0.5)

        # Reboot module to clean state
        self._send_cmd("AT+REBOOT", timeout=2)
        time.sleep(1)

        # Test connection
        if not self._test_connection():
            raise TTNError(f"Module not responding on {port}")

        logger.info(f"Connected to LoRaWAN module on {port}")

    def _send_cmd(self, cmd: str, timeout: float = 3) -> tuple[bool, str]:
        """
        Send AT command and get response.
        
        Response format from module: +CMD=OK\r\n or +CMD=value\r\n
        """
        # Clear buffer
        self._serial.reset_input_buffer()

        # Send command
        full_cmd = f"{cmd}\r\n"
        if self._debug:
            logger.debug(f"TX: {cmd}")

        self._serial.write(full_cmd.encode())
        self._serial.flush()

        # Wait for response
        time.sleep(0.1)
        end_time = time.time() + timeout
        response = b""

        while time.time() < end_time:
            if self._serial.in_waiting:
                chunk = self._serial.read(self._serial.in_waiting)
                response += chunk
                # Check for complete response
                if b"\r\n" in response:
                    break
            time.sleep(0.05)

        response_str = response.decode(errors="ignore").strip()
        if self._debug:
            logger.debug(f"RX: {response_str}")

        # Parse response - format is +CMD=OK or +CMD=value or OK
        success = False
        data = ""
        
        if response_str == "OK":
            success = True
        elif "=OK" in response_str:
            success = True
        elif "=" in response_str:
            # Extract value from +CMD=value format
            parts = response_str.split("=", 1)
            if len(parts) == 2:
                data = parts[1].strip()
                success = True

        return success, data

    def _test_connection(self) -> bool:
        """Test if module is responding."""
        for _ in range(3):
            ok, _ = self._send_cmd("AT")
            if ok:
                return True
            time.sleep(0.5)
        return False

    @property
    def dev_eui(self) -> str:
        """Get DevEUI (needed for TTN device registration)."""
        ok, data = self._send_cmd("AT+DEVEUI?")
        if not ok or not data:
            raise TTNError("Failed to get DevEUI")
        return data

    @property
    def is_joined(self) -> bool:
        """Check if joined to TTN."""
        return self._joined

    def join(
        self,
        app_eui: str,
        app_key: str,
        timeout: int = 60,
        data_rate: int = 5,
        tx_power: int = 14,
    ) -> None:
        """
        Join TTN via OTAA.

        Args:
            app_eui: Application EUI / JoinEUI from TTN (16 hex chars)
            app_key: Application Key from TTN (32 hex chars)
            timeout: Join timeout in seconds (default: 60)
            data_rate: Data rate 0-5 (default: 5 = SF7)
            tx_power: TX power in dBm (default: 14)

        Raises:
            TTNError: If join fails or times out
        """
        logger.info("Configuring for TTN OTAA...")

        # Set LoRaWAN mode (not P2P LoRa)
        ok, _ = self._send_cmd("AT+LORAMODE=LORAWAN")
        if not ok:
            raise TTNError("Failed to set LoRaWAN mode")

        # Set OTAA join type
        ok, _ = self._send_cmd("AT+JOINTYPE=OTAA")
        if not ok:
            raise TTNError("Failed to set OTAA join type")

        # Set region
        ok, _ = self._send_cmd(f"AT+REGION={self._region.value}")
        if not ok:
            raise TTNError(f"Failed to set region {self._region.value}")

        # Set device class (A for battery-powered devices)
        ok, _ = self._send_cmd("AT+CLASS=CLASS_A")
        if not ok:
            logger.warning("Failed to set device class")

        # Set data rate
        ok, _ = self._send_cmd(f"AT+DATARATE={data_rate}")
        if not ok:
            logger.warning("Failed to set data rate")

        # Set TX power (EIRP)
        ok, _ = self._send_cmd(f"AT+EIRP={tx_power}")
        if not ok:
            logger.warning("Failed to set TX power")

        # Disable ADR (we control data rate manually)
        self._send_cmd("AT+ADR=0")

        # Set unconfirmed uplinks
        self._send_cmd("AT+UPLINKTYPE=UNCONFIRMED")

        # Set JoinEUI (AppEUI in TTN v2 terminology)
        ok, _ = self._send_cmd(f"AT+JOINEUI={app_eui.upper()}")
        if not ok:
            raise TTNError("Failed to set JoinEUI/AppEUI")

        # Set AppKey
        ok, _ = self._send_cmd(f"AT+APPKEY={app_key.upper()}")
        if not ok:
            raise TTNError("Failed to set AppKey")

        # Initiate join
        logger.info("Sending join request...")
        ok, _ = self._send_cmd("AT+JOIN=1", timeout=10)
        if not ok:
            raise TTNError("Join request failed")

        # Wait for join to complete
        logger.info("Waiting for join accept...")
        start = time.time()
        while time.time() - start < timeout:
            ok, data = self._send_cmd("AT+JOIN?")
            if ok and data == "1":
                self._joined = True
                logger.info("Successfully joined TTN!")
                return
            time.sleep(2)

        raise TTNError(f"Join timeout after {timeout}s - check gateway coverage and credentials")

    def send(self, data: Union[bytes, str, dict], port: int = 1) -> None:
        """
        Send data to TTN.

        Note: The DFRobot module doesn't support fPort selection via AT command.
        Data is sent on the default port configured in the module.

        Args:
            data: Payload - bytes, string, or dict (auto-encoded)
            port: fPort (ignored - module uses default port)

        Raises:
            TTNError: If not joined or send fails
        """
        if not self._joined:
            raise TTNError("Not joined - call join() first")

        # Convert data to bytes
        if isinstance(data, dict):
            payload = self._encode_dict(data)
        elif isinstance(data, str):
            payload = data.encode()
        else:
            payload = bytes(data)

        # Convert to hex string (uppercase)
        hex_data = payload.hex().upper()

        logger.debug(f"Sending {len(payload)} bytes: {hex_data}")

        # Send command - format is AT+SEND=<hex data>
        ok, _ = self._send_cmd(f"AT+SEND={hex_data}", timeout=10)
        if not ok:
            raise TTNError("Send failed")

        logger.info(f"Sent {len(payload)} bytes to TTN")

    def _encode_dict(self, data: dict) -> bytes:
        """
        Encode dict to bytes using simple format.
        
        Supported keys: temp/temperature, humidity, pressure, battery
        """
        result = bytearray()

        for key, value in data.items():
            if key in ("temp", "temperature"):
                # Temperature: 2 bytes, 0.1°C resolution, signed
                temp = int(value * 10)
                result.extend(temp.to_bytes(2, "big", signed=True))
            elif key == "humidity":
                # Humidity: 1 byte, 0.5% resolution
                result.append(int(value * 2))
            elif key == "pressure":
                # Pressure: 2 bytes, 0.1 hPa resolution
                result.extend(int(value * 10).to_bytes(2, "big"))
            elif key == "battery":
                # Battery: 1 byte, percentage
                result.append(int(value))
            else:
                # Generic: single byte for int, 2 bytes for float
                if isinstance(value, int):
                    result.append(value & 0xFF)
                elif isinstance(value, float):
                    result.extend(int(value * 100).to_bytes(2, "big", signed=True))

        return bytes(result)

    @property
    def rssi(self) -> int:
        """Get last RSSI (dBm)."""
        ok, data = self._send_cmd("AT+RSSI?")
        try:
            return int(data) if ok and data else -999
        except ValueError:
            return -999

    @property
    def snr(self) -> int:
        """Get last SNR (dB)."""
        ok, data = self._send_cmd("AT+SNR?")
        try:
            return int(data) if ok and data else -999
        except ValueError:
            return -999

    def sleep(self, seconds: float) -> None:
        """Sleep (convenience method for timing between sends)."""
        time.sleep(seconds)

    def close(self) -> None:
        """Close serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("Connection closed")

    def send_at(self, cmd: str) -> tuple[bool, str]:
        """
        Send raw AT command (for debugging).
        
        Args:
            cmd: AT command (e.g., "AT+DEVEUI?")
            
        Returns:
            Tuple of (success, response_data)
        """
        return self._send_cmd(cmd)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except:
            pass
