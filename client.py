"""
LoRaWAN client for DFRobot module - simple API with automatic queue management.

Usage:
    from client import LoRa

    lora = LoRa(
        port="/dev/ttyS0",
        app_eui="YOUR_APP_EUI",
        app_key="YOUR_APP_KEY",
    )

    lora.send("Hello World!")  # Queued and sent in background
    lora.send({"temp": 23.5})  # Sensor data

    # When done
    lora.stop()
"""

import time
import logging
import threading
from queue import Queue, Full, Empty
from enum import Enum
from typing import Union, Optional
from dataclasses import dataclass

import serial

logger = logging.getLogger(__name__)


class Region(Enum):
    """LoRaWAN frequency regions."""
    EU868 = "EU868"
    US915 = "US915"
    CN470 = "CN470"


class LoRaError(Exception):
    """LoRa operation error."""
    pass


@dataclass
class QueuedMessage:
    """Message waiting to be sent."""
    data: bytes
    retries: int = 0


class LoRa:
    """
    Simple LoRaWAN client with automatic queue management.
    
    Messages are queued and sent in a background thread with 30-second
    spacing to respect duty cycle limits. Failed sends are retried up
    to 3 times.
    
    Example:
        lora = LoRa("/dev/ttyS0", app_eui="...", app_key="...")
        lora.send("Hello!")
        lora.send({"temp": 23.5, "humidity": 65})
        lora.stop()
    """

    SEND_INTERVAL = 30  # Seconds between sends (duty cycle)
    MAX_RETRIES = 3
    MAX_QUEUE_SIZE = 20

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        app_eui: str = "",
        app_key: str = "",
        region: Region = Region.EU868,
        data_rate: int = 3,
        auto_join: bool = True,
        debug: bool = False,
    ):
        """
        Initialize and connect to LoRaWAN.

        Args:
            port: Serial port (e.g. /dev/ttyAMA0 or /dev/ttyS0)
            app_eui: Application EUI from TTN (16 hex chars)
            app_key: Application Key from TTN (32 hex chars)
            region: LoRaWAN region (default: EU868)
            data_rate: 0-5, lower = longer range (default: 3 = SF9)
            auto_join: Automatically join on init (default: True)
            debug: Enable debug logging

        Raises:
            LoRaError: If connection or join fails
        """
        self._port_name = port
        self._region = region
        self._data_rate = data_rate
        self._debug = debug
        self._joined = False
        self._running = False
        self._last_send_time = 0.0
        self._serial: Optional[serial.Serial] = None
        
        self._queue: Queue[QueuedMessage] = Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._worker_thread: Optional[threading.Thread] = None
        self._serial_lock = threading.Lock()

        if debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )

        try:
            self._connect(port)
            
            # Auto join if credentials provided
            if auto_join and app_eui and app_key:
                self.join(app_eui, app_key)
                self._start_worker()
        except Exception as e:
            self._cleanup()
            raise LoRaError(f"Initialization failed: {e}") from e

    def _connect(self, port: str) -> None:
        """Open serial connection and verify module."""
        self._serial = serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=5,
        )
        time.sleep(0.5)

        # Reboot module to clean state
        self._send_cmd("AT+REBOOT", timeout=2)
        time.sleep(1)

        # Test connection
        if not self._test_at():
            raise LoRaError(f"Module not responding on {port}")

        logger.info(f"Connected to LoRa module on {port}")

    def _cleanup(self) -> None:
        """Clean up resources."""
        self._running = False
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def send(self, data: Union[bytes, str, dict]) -> bool:
        """
        Queue a message for sending.

        Messages are sent in the background with 30-second spacing.
        If the queue is full (20 messages), the message is dropped.

        Args:
            data: Message to send (string, bytes, or dict)

        Returns:
            True if queued successfully, False if queue is full
        """
        if not self._joined:
            logger.warning("Not joined to network, message not queued")
            return False
            
        payload = self._to_bytes(data)
        
        if len(payload) == 0:
            logger.warning("Empty payload, message not queued")
            return False
        
        if len(payload) > 242:  # Max LoRaWAN payload
            logger.warning(f"Payload too large ({len(payload)} bytes), max 242")
            return False
        
        try:
            self._queue.put_nowait(QueuedMessage(data=payload))
            logger.debug(f"Queued {len(payload)} bytes ({self._queue.qsize()}/{self.MAX_QUEUE_SIZE})")
            return True
        except Full:
            logger.warning("Queue full, message dropped")
            return False

    def join(self, app_eui: str, app_key: str, timeout: int = 60) -> None:
        """
        Join TTN network via OTAA.

        Args:
            app_eui: Application EUI from TTN (16 hex chars)
            app_key: Application Key from TTN (32 hex chars)
            timeout: Max seconds to wait for join accept

        Raises:
            LoRaError: If join fails or times out
        """
        logger.info("Joining TTN...")

        # Configure module
        config_commands = [
            ("AT+LORAMODE=LORAWAN", False),
            ("AT+JOINTYPE=OTAA", False),
            (f"AT+REGION={self._region.value}", False),
            ("AT+CLASS=CLASS_A", False),
            (f"AT+DATARATE={self._data_rate}", False),
            ("AT+EIRP=14", False),
            ("AT+ADR=0", False),
            ("AT+UPLINKTYPE=UNCONFIRMED", False),
            (f"AT+JOINEUI={app_eui.upper()}", True),  # Critical
            (f"AT+APPKEY={app_key.upper()}", True),   # Critical
        ]

        for cmd, critical in config_commands:
            ok, _ = self._send_cmd(cmd)
            if not ok and critical:
                raise LoRaError(f"Failed to execute: {cmd}")

        # Send join request
        ok, _ = self._send_cmd("AT+JOIN=1", timeout=5)
        if not ok:
            raise LoRaError("Join request rejected by module")

        logger.info("Join request sent, waiting for network accept...")

        # Wait for join accept
        start = time.time()
        while time.time() - start < timeout:
            ok, data = self._send_cmd("AT+JOIN?")
            if ok and data == "1":
                self._joined = True
                logger.info("Joined TTN successfully")
                return
            time.sleep(5)

        raise LoRaError(f"Join timeout after {timeout}s - check gateway coverage and credentials")

    def stop(self) -> None:
        """
        Stop background worker and close connection.
        
        Waits for current send to complete (if any), then exits.
        Queued messages are discarded.
        """
        logger.debug("Stopping LoRa client...")
        self._running = False
        
        # Wait for worker to finish (with timeout)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
            if self._worker_thread.is_alive():
                logger.warning("Worker thread did not stop cleanly")
        
        self._cleanup()
        logger.info("LoRa connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if joined to network."""
        return self._joined

    @property
    def queue_size(self) -> int:
        """Number of messages waiting to be sent."""
        return self._queue.qsize()

    @property
    def dev_eui(self) -> str:
        """Get device EUI (needed for TTN device registration)."""
        ok, data = self._send_cmd("AT+DEVEUI?")
        if ok and data:
            return data
        raise LoRaError("Failed to get DevEUI")

    @property
    def rssi(self) -> int:
        """Last received signal strength (dBm). Returns -999 on error."""
        ok, data = self._send_cmd("AT+RSSI?")
        try:
            return int(data) if ok and data else -999
        except ValueError:
            return -999

    @property
    def snr(self) -> int:
        """Last signal-to-noise ratio (dB). Returns -999 on error."""
        ok, data = self._send_cmd("AT+SNR?")
        try:
            return int(data) if ok and data else -999
        except ValueError:
            return -999

    # -------------------------------------------------------------------------
    # Background worker
    # -------------------------------------------------------------------------

    def _start_worker(self) -> None:
        """Start background send thread."""
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop, 
            daemon=True,
            name="LoRa-Worker"
        )
        self._worker_thread.start()
        logger.debug("Background worker started")

    def _worker_loop(self) -> None:
        """Process queue in background."""
        while self._running:
            try:
                # Wait for next message (with timeout to allow shutdown check)
                try:
                    msg = self._queue.get(timeout=1)
                except Empty:
                    continue

                # Check if we should stop
                if not self._running:
                    self._queue.task_done()
                    break

                # Wait for rate limit (in small increments to allow shutdown)
                elapsed = time.time() - self._last_send_time
                if elapsed < self.SEND_INTERVAL:
                    wait_time = self.SEND_INTERVAL - elapsed
                    logger.debug(f"Rate limit: waiting {wait_time:.1f}s")
                    
                    # Sleep in 1-second chunks to allow responsive shutdown
                    while wait_time > 0 and self._running:
                        time.sleep(min(1.0, wait_time))
                        wait_time -= 1.0
                    
                    if not self._running:
                        self._queue.task_done()
                        break

                # Send with retries
                success = False
                for attempt in range(self.MAX_RETRIES):
                    if not self._running:
                        break
                        
                    try:
                        if self._do_send(msg.data):
                            success = True
                            break
                    except Exception as e:
                        logger.warning(f"Send error: {e}")
                    
                    if attempt < self.MAX_RETRIES - 1:
                        logger.warning(f"Send failed, retry {attempt + 1}/{self.MAX_RETRIES}")
                        time.sleep(2)

                if success:
                    logger.info(f"Sent {len(msg.data)} bytes (queue: {self._queue.qsize()})")
                elif self._running:  # Only log error if we didn't stop
                    logger.error(f"Send failed after {self.MAX_RETRIES} retries, dropping message")

                self._last_send_time = time.time()
                self._queue.task_done()

            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1)

    def _do_send(self, payload: bytes) -> bool:
        """Send data to module. Returns True on success."""
        if not self._joined:
            logger.warning("Cannot send: not joined")
            return False

        hex_data = payload.hex().upper()
        ok, _ = self._send_cmd(f"AT+SEND={hex_data}", timeout=10)
        
        if ok:
            # Wait for TX + RX windows to complete
            time.sleep(3)
        
        return ok

    # -------------------------------------------------------------------------
    # Serial communication
    # -------------------------------------------------------------------------

    def _send_cmd(self, cmd: str, timeout: float = 3, delay: float = 0.8) -> tuple[bool, str]:
        """
        Send AT command and get response.
        
        Thread-safe: uses lock to prevent concurrent access.
        
        Returns:
            Tuple of (success, response_data)
        """
        if not self._serial or not self._serial.is_open:
            return False, ""
            
        with self._serial_lock:
            try:
                self._serial.reset_input_buffer()

                if self._debug:
                    logger.debug(f"TX: {cmd}")

                self._serial.write(f"{cmd}\r\n".encode())
                self._serial.flush()
                time.sleep(delay)

                end_time = time.time() + timeout
                response = b""

                while time.time() < end_time:
                    if self._serial.in_waiting:
                        response += self._serial.read(self._serial.in_waiting)
                        if b"\r\n" in response:
                            break
                    time.sleep(0.05)

                response_str = response.decode(errors="ignore").strip()
                
                if self._debug:
                    logger.debug(f"RX: {response_str}")

                # Parse response
                if response_str == "OK" or "=OK" in response_str:
                    return True, ""
                elif "=" in response_str:
                    parts = response_str.split("=", 1)
                    return True, parts[1].strip() if len(parts) == 2 else ""
                
                return False, ""
                
            except serial.SerialException as e:
                logger.error(f"Serial error: {e}")
                return False, ""

    def _test_at(self) -> bool:
        """Test if module responds to AT command."""
        for _ in range(3):
            ok, _ = self._send_cmd("AT")
            if ok:
                return True
            time.sleep(0.5)
        return False

    # -------------------------------------------------------------------------
    # Data encoding
    # -------------------------------------------------------------------------

    def _to_bytes(self, data: Union[bytes, str, dict]) -> bytes:
        """Convert data to bytes."""
        if isinstance(data, bytes):
            return data
        elif isinstance(data, str):
            return data.encode("utf-8")
        elif isinstance(data, dict):
            return self._encode_dict(data)
        else:
            try:
                return bytes(data)
            except (TypeError, ValueError):
                logger.warning(f"Cannot convert {type(data)} to bytes")
                return b""

    def _encode_dict(self, data: dict) -> bytes:
        """
        Encode sensor dict to compact bytes.
        
        Supported keys:
            temp/temperature: 2 bytes, signed, 0.1°C resolution
            humidity: 1 byte, 0.5% resolution
            pressure: 2 bytes, 0.1 hPa resolution
            battery: 1 byte, percentage
            
        Other values are encoded as:
            str: UTF-8 bytes
            int: 1 byte (0-255)
            float: 2 bytes, signed, 0.01 resolution
        """
        result = bytearray()

        for key, value in data.items():
            try:
                if key in ("temp", "temperature"):
                    temp = int(value * 10)
                    result.extend(temp.to_bytes(2, "big", signed=True))
                elif key == "humidity":
                    result.append(min(255, max(0, int(value * 2))))
                elif key == "pressure":
                    result.extend(int(value * 10).to_bytes(2, "big"))
                elif key == "battery":
                    result.append(min(255, max(0, int(value))))
                elif isinstance(value, str):
                    result.extend(value.encode("utf-8"))
                elif isinstance(value, int):
                    result.append(value & 0xFF)
                elif isinstance(value, float):
                    result.extend(int(value * 100).to_bytes(2, "big", signed=True))
            except (ValueError, OverflowError) as e:
                logger.warning(f"Failed to encode '{key}': {e}")

        return bytes(result)

    # -------------------------------------------------------------------------
    # Context manager
    # -------------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()

    def __del__(self):
        """Destructor - ensure cleanup on garbage collection."""
        try:
            self._cleanup()
        except Exception:
            pass
