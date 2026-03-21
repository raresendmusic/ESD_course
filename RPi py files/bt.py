import bluetooth
import time
import json
import hike

WATCH_BT_MAC = '94:B5:55:C8:DF:AE'
WATCH_BT_PORT = 1

class HubBluetooth:
    """Handles RFCOMM Bluetooth synchronization with the watch.

    Protocol overview:
        - The hub connects to the watch over RFCOMM.
        - The hub sends line-based control commands terminated by '\n'.
        - 'c\n' means "send the next finished session".
        - The watch responds with one newline-delimited JSON session payload at a time.
        - After the hub successfully saves one session, it replies with
          'a:<session_id>\n' to acknowledge that specific session.
        - The watch may then delete only that acknowledged session and send the next one.

    This is a breaking protocol change from the older version, where the hub sent
    single-character commands such as 'c' and acknowledged synchronization with
    a single global 'r'. The current protocol uses line-based commands and
    per-session acknowledgements instead.

    Attributes:
        connected:
            Whether the Bluetooth connection to the watch is currently established.
        sock:
            The bluetooth.BluetoothSocket used for RFCOMM communication.
    """

    connected = False
    sock = None
    
    def wait_for_connection(self):
        """Continuously tries to connect to the watch over RFCOMM.

        Once a connection is established, the hub sends 'c\n' to request the next
        finished session from the watch.

        Notes:
            - This uses the current line-based synchronization protocol.
            - 'c\n' is a control command, not session data.
            - This replaces the older single-byte 'c' behavior.
        """

        if not self.connected:
            # try to connect every sec while connection is made
            while True:
                print("Waiting for connection...")
                try:
                    self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
                    self.sock.connect((WATCH_BT_MAC, WATCH_BT_PORT))
                    self.sock.settimeout(2)
                    self.connected = True
                    self.sock.send(b'c\n')
                    print("Connected to Watch!")
                    break
                except bluetooth.btcommon.BluetoothError:
                    time.sleep(1)
                except Exception as e:
                    print(e)
                    print("Hub: Error occured while trying to connect to the Watch.")

            print("Hub: Established Bluetooth connection with Watch!")
        print("WARNING Hub: the has already connected via Bluetooth.")

    def synchronize(self, callback):
        """Receives newline-delimited session messages from the watch and processes them.

        Data flow:
            1. The watch sends one or more newline-delimited JSON session payloads.
            2. Each complete JSON message is converted into a hike.HikeSession.
            3. The provided callback is called once per successfully parsed session.
            4. After one session has been processed successfully, the hub sends a
            per-session acknowledgement in the form 'a:<session_id>\n'.

        Keepalive / sync behavior:
            - If no data is received before the socket timeout, the hub sends 'c\n'
            to request the next finished session.
            - This replaces the older protocol where the hub sent a single global
            acknowledgement 'r' after processing a batch.

        Args:
            callback:
                A one-parameter callable that accepts list[hike.HikeSession].
                In the current implementation it is invoked once per saved session as
                callback([session]).

        Raises:
            KeyboardInterrupt:
                Raised when shutting down the receiver interactively.
        """
        print("Synchronizing with watch...")
        remainder = b''
        while True:
            try:
                chunk = self.sock.recv(1024)

                messages = chunk.split(b'\n')
                messages[0] = remainder + messages[0]
                remainder = messages.pop()

                if len(messages):
                    try:
                        print(f"received messages: {messages}")
                        sessions = HubBluetooth.messages_to_sessions(messages)

                        for session in sessions:
                            callback([session])
                            ack = f"a:{session.session_id}\n".encode("utf-8")
                            self.sock.send(ack)
                            print(f"Saved session {session.session_id}. Ack sent: {ack!r}")
                        
                    except (AssertionError, ValueError) as e:
                        print(e)
                        print("WARNING: Receiver -> Message was corrupted. Aborting...")

            except KeyboardInterrupt:
                self.sock.close()
                raise KeyboardInterrupt("Shutting down the receiver.")

            except bluetooth.btcommon.BluetoothError as bt_err:
                if bt_err.errno == 11: # connection down
                    print("Lost connection with the watch.")
                    self.connected = False
                    self.sock.close()
                    break
                elif bt_err.errno == None: # possibly occured by socket.settimeout
                    self.sock.send(b'c\n')
                    print("Reminder has been sent to the Watch about the attempt of the synchronization.")

    @staticmethod
    def messages_to_sessions(messages: list[bytes]) -> list[hike.HikeSession]:
        """Convert multiple newline-delimited JSON messages into hike session objects.

        Each item in messages is expected to contain one complete JSON object
        received from the watch, without the trailing newline delimiter.

        Invalid or corrupted messages are skipped instead of aborting the whole batch.
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
    def mtos(message: bytes) -> hike.HikeSession:
        """Transform one JSON session message into a hike.HikeSession.

        Expected watch payload format:
            {
                "session_id": "...",
                "start_time": "...",
                "end_time": "...",
                "steps": 123,
                "distance_m": 456,
                "duration_s": 30
            }

        Notes:
            - The payload is a newline-delimited JSON object in the Bluetooth stream.
            - Session acknowledgement is not part of this payload. Acknowledgements are
            sent separately by the hub as 'a:<session_id>\n' after successful
            processing.
        """
        
        # Decode the bytes to string and parse JSON
        data = json.loads(message.decode('utf-8'))

        hs = hike.HikeSession()

        hs.session_id = data.get("session_id", "")
        hs.start_time = data.get("start_time", "")
        hs.end_time = data.get("end_time", "")
        hs.steps = int(data.get("steps", 0))
        hs.distance_m = int(data.get("distance_m", 0))
        hs.duration_s = int(data.get("duration_s", 0))

        return hs
