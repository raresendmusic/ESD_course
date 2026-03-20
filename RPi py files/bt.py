import bluetooth
import time
import json
import hike

WATCH_BT_MAC = '94:B5:55:C8:DF:AE'
WATCH_BT_PORT = 1

class HubBluetooth:
    """Handles Bluetooth pairing and synchronization with the Watch.

    Attributes:
        connected: A boolean indicating if the connection is currently established with the Watch.
        sock: the socket object created with bluetooth.BluetoothSocket(),
              through which the Bluetooth communication is handled.
    """

    connected = False
    sock = None
    
    def wait_for_connection(self):
        """Synchronous function continuously trying to connect to the Watch by 2 sec intervals.
        If a connection has been made, it sends the watch a `c` ASCII character as a confirmation.
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
                    self.sock.send('c')
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
        """Continuously tries to receive data from an established connection with the Watch.

        If receives data, then transforms it to a list of `hike.HikeSession` object.
        After that, calls the `callback` function with the transformed data.
        Finally sends a `r` as a response to the Watch for successfully processing the
        incoming data.

        If does not receive data, then it tries to send `c` as a confirmation of the established
        connection at every second to inform the Watch that the Hub is able to receive sessions.

        Args:
            callback: One parameter function able to accept a list[hike.HikeSession].
                      Used to process incoming sessions arbitrarly

        Raises:
            KeyboardInterrupt: to be able to close a running application.
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
                        callback(sessions)
                        self.sock.send('r')

                        print(f"Saved. 'r' sent to the socket!")

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
                    self.sock.send('c')
                    print("Reminder has been sent to the Watch about the attempt of the synchronization.")

    @staticmethod
    @staticmethod
    def messages_to_sessions(messages: list[bytes]) -> list[hike.HikeSession]:
        """Transforms multiple incoming JSON messages to a list of hike.HikeSession objects."""
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
        """Transforms a single JSON message into a hike.HikeSession object.
        
        Expected JSON format from Watch:
        {
            "session_id": "...",
            "start_time": "...",
            "end_time": "...",
            "steps": 123,
            "distance_m": 456,
            "duration_s": 30
        }
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
