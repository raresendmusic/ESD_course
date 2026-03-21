import time

import hike
import db
import bt

hubdb = db.HubDatabase()
hubbt = bt.HubBluetooth()


def process_sessions(sessions: list[hike.HikeSession]):
    """Persist synchronized sessions into the database.

    The Bluetooth layer is responsible for parsing incoming protocol messages
    and attaching receiver-side metadata such as `created_at`. This function
    only stores the received sessions in the hub database.

    Args:
        sessions: List of `hike.HikeSession` objects received from the watch.
    """
    for session in sessions:
        hubdb.save(session)


def main():
    """Run the Bluetooth receiver loop until interrupted.

    Bluetooth connection loss, timeouts, and watch reboots are handled inside
    `bt.py`, so this loop only needs to wait for a connection and trigger
    synchronization repeatedly.
    """
    print("Starting Bluetooth receiver.")

    try:
        while True:
            hubbt.wait_for_connection()
            completed = hubbt.synchronize(callback=process_sessions)
            if completed:
                time.sleep(2)

    except KeyboardInterrupt:
        print("CTRL+C Pressed. Shutting down the server...")
        hubbt.close_connection()


if __name__ == "__main__":
    main()
