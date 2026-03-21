import bluetooth
import time
import json
from datetime import datetime, timezone
import hike

WATCH_BT_MAC = '94:B5:55:C8:DF:AE'
WATCH_BT_PORT = 1
BT_PROTOCOL_VERSION = 2
SUCCESSFUL_SYNC_COOLDOWN_SECONDS = 15


class HubBluetooth:
    """Handles RFCOMM Bluetooth synchronization with the watch.

    Breaking protocol change (v2):
        - Hub sends HELLO|2 and TIME_SYNC|<unix_epoch> immediately after connect.
        - Watch must acknowledge with HELLO_ACK|2 and TIME_SYNC_ACK|<unix_epoch>.
        - Hub requests sessions with SYNC_PULL.
        - Watch sends SESSION|<json> one at a time.
        - Hub acknowledges each stored session with SESSION_ACK|<session_id>.
        - Watch ends the sync cycle with SYNC_DONE.

    Connection loss caused by watch reboot, timeout, or link interruption is
    treated as a recoverable transport-level event. In those cases, the socket
    is closed, the internal connection state is reset, and control returns to
    the caller so the receiver can wait for a new connection.
    """

    def __init__(self):
        self.connected = False
        self.sock = None
        self.last_successful_sync_at = 0.0

    def close_connection(self):
        """Close the current Bluetooth socket and reset connection state.

        This method is safe to call even if the socket is already closed or was
        only partially initialized.
        """
        try:
            if self.sock is not None:
                self.sock.close()
        except Exception:
            pass
        finally:
            self.sock = None
            self.connected = False

    def send_line(self, message: str):
        """Send one newline-terminated protocol message to the watch.

        Args:
            message: Protocol payload without the trailing newline.

        Raises:
            RuntimeError: If there is no active Bluetooth socket.
            bluetooth.btcommon.BluetoothError: If sending fails.
        """
        if self.sock is None:
            raise RuntimeError("Bluetooth socket is not connected")

        payload = f"{message}\n".encode("utf-8")
        self.sock.send(payload)
        print(f"Hub -> Watch: {message}")

    def current_unix_epoch(self) -> int:
        """Return the current UTC Unix timestamp in seconds."""
        return int(datetime.now(timezone.utc).timestamp())

    def perform_handshake(self):
        """Send the protocol handshake and initial sync request.

        The hub announces the protocol version, sends the current UTC time to
        the watch, and immediately asks the watch to begin session transfer.
        """
        self.send_line(f"HELLO|{BT_PROTOCOL_VERSION}")
        self.send_line(f"TIME_SYNC|{self.current_unix_epoch()}")
        self.send_line("SYNC_PULL")

    def wait_for_connection(self):
        """Block until a Bluetooth RFCOMM connection to the watch is established.

        Any stale socket state from a previous session is replaced by a new
        connection attempt. Once connected, the method performs the protocol
        handshake before returning.
        """
        if self.connected:
            print("WARNING Hub: Bluetooth is already connected.")
            return

        while True:
            cooldown_remaining = (
                self.last_successful_sync_at
                + SUCCESSFUL_SYNC_COOLDOWN_SECONDS
                - time.time()
            )
            if cooldown_remaining > 0:
                print(
                    f"Recent sync completed; delaying reconnect for "
                    f"{cooldown_remaining:.1f}s."
                )
                time.sleep(min(1.0, cooldown_remaining))
                continue

            print("Waiting for connection...")
            try:
                self.close_connection()
                self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
                self.sock.connect((WATCH_BT_MAC, WATCH_BT_PORT))
                self.sock.settimeout(2)
                self.connected = True
                self.perform_handshake()
                print("Connected to Watch!")
                break
            except bluetooth.btcommon.BluetoothError as e:
                self.close_connection()
                print(f"Bluetooth connect failed: {e}")
                time.sleep(1)
            except Exception as e:
                self.close_connection()
                print(e)
                print("Hub: Error occured while trying to connect to the Watch.")

        print("Hub: Established Bluetooth connection with Watch!")

    def synchronize(self, callback):
        """Receive and process protocol messages from the watch.

        Session messages are decoded one by one, forwarded to callback, and
        acknowledged with SESSION_ACK|<session_id> after successful handling.

        A watch reboot or Bluetooth timeout is treated as a recoverable
        connection-level failure rather than a fatal process error.

        Args:
            callback: Function that accepts a list of hike.HikeSession
                objects. In the current protocol, sessions are delivered one at
                a time as a one-element list.

        Returns:
            True if synchronization ends normally with SYNC_DONE, otherwise
            False if the connection is lost and the caller should wait for the
            watch to reconnect.
        """
        print("Synchronizing with watch...")
        remainder = b''
        timeout_count = 0
        max_timeouts = 3

        while True:
            try:
                chunk = self.sock.recv(1024)
                timeout_count = 0

                if not chunk:
                    print("Watch closed the Bluetooth connection.")
                    self.close_connection()
                    return False

                messages = chunk.split(b'\n')
                messages[0] = remainder + messages[0]
                remainder = messages.pop()

                for raw in messages:
                    line = raw.decode("utf-8").strip()
                    if not line:
                        continue

                    print(f"Watch -> Hub: {line}")

                    if line.startswith("HELLO_ACK|"):
                        continue

                    if line.startswith("TIME_SYNC_ACK|"):
                        continue

                    if line.startswith("TIME_SYNC_NACK|"):
                        raise RuntimeError(f"Watch rejected time sync: {line}")

                    if line == "SYNC_DONE":
                        print("Watch reported sync completion.")
                        self.last_successful_sync_at = time.time()
                        self.close_connection()
                        return True

                    if line.startswith("SESSION|"):
                        session = HubBluetooth.session_line_to_session(line)
                        callback([session])
                        self.send_line(f"SESSION_ACK|{session.session_id}")
                        continue

                    print(f"Ignoring unrecognized line: {line}")

            except KeyboardInterrupt:
                self.close_connection()
                raise KeyboardInterrupt("Shutting down the receiver.")

            except bluetooth.btcommon.BluetoothError as bt_err:
                errno = getattr(bt_err, "errno", None)

                if errno in (11, 104, 110, 111, 112, 113):
                    print(f"Lost connection with the watch: {bt_err}")
                    self.close_connection()
                    return False

                if errno is None:
                    timeout_count += 1
                    print(f"Bluetooth receive timeout ({timeout_count}/{max_timeouts}).")

                    if timeout_count >= max_timeouts:
                        print("Too many consecutive timeouts; ending sync attempt.")
                        self.close_connection()
                        return False

                    try:
                        self.send_line("SYNC_PULL")
                        print("Reminder sent to the watch to continue synchronization.")
                        continue
                    except bluetooth.btcommon.BluetoothError:
                        print("Failed to send SYNC_PULL reminder; connection appears lost.")
                        self.close_connection()
                        return False

                raise

            except Exception:
                self.close_connection()
                raise

    @staticmethod
    def messages_to_sessions(messages: list[bytes]) -> list[hike.HikeSession]:
        """Convert raw JSON message payloads into hike session objects.

        Args:
            messages: List of raw byte strings containing JSON session payloads.

        Returns:
            A list of successfully decoded hike.HikeSession objects. Corrupted
            messages are skipped.
        """
        sessions = []
        for msg in messages:
            if not msg.strip():
                continue
            try:
                sessions.append(HubBluetooth.mtos(msg))
            except Exception as e:
                print(f"Skipping corrupted message: {e}")
        return sessions

    @staticmethod
    def session_line_to_session(line: str) -> hike.HikeSession:
        """Parse a SESSION|<json> protocol line into a hike session object.

        Args:
            line: Full protocol line beginning with SESSION|.

        Returns:
            A populated hike.HikeSession instance.
        """
        payload = line.split("|", 1)[1]
        data = json.loads(payload)

        hs = hike.HikeSession()
        hs.session_id = data.get("session_id", "")
        hs.start_time = data.get("start_time", "")
        hs.end_time = data.get("end_time", "")
        hs.steps = int(data.get("steps", 0))
        hs.distance_m = int(data.get("distance_m", 0))
        hs.duration_s = int(data.get("duration_s", 0))
        hs.created_at = datetime.now().isoformat(timespec="seconds")
        return hs

    @staticmethod
    def mtos(message: bytes) -> hike.HikeSession:
        """Parse a raw JSON byte payload into a hike session object.

        Args:
            message: Raw UTF-8 encoded JSON message.

        Returns:
            A populated hike.HikeSession instance.
        """
        data = json.loads(message.decode('utf-8'))

        hs = hike.HikeSession()
        hs.session_id = data.get("session_id", "")
        hs.start_time = data.get("start_time", "")
        hs.end_time = data.get("end_time", "")
        hs.steps = int(data.get("steps", 0))
        hs.distance_m = int(data.get("distance_m", 0))
        hs.duration_s = int(data.get("duration_s", 0))

        return hs
