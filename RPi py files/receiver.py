import hike
import db
import bt

from datetime import datetime, timedelta

hubdb = db.HubDatabase()
hubbt = bt.HubBluetooth()


def apply_receiver_timestamps(
        session: hike.HikeSession,
        received_at: datetime | None = None
    ) -> hike.HikeSession:
    if received_at is None:
        received_at = datetime.now()

    duration_s = max(int(session.duration_s), 0)
    start_at = received_at - timedelta(seconds=duration_s)
    received_iso = received_at.isoformat(timespec="seconds")

    session.end_time = received_iso
    session.start_time = start_at.isoformat(timespec="seconds")
    session.created_at = received_iso
    return session

def process_sessions(sessions: list[hike.HikeSession]):
    """Callback function to process sessions.

    Saves the session into the database.

    Args:
        sessions: list of `hike.HikeSession` objects to process
    """

    for s in sessions:
        apply_receiver_timestamps(s)
        hubdb.save(s)

def main():
    print("Starting Bluetooth receiver.")
    try:
        while True:
            hubbt.wait_for_connection()
            hubbt.synchronize(callback=process_sessions)
            
    except KeyboardInterrupt:
        print("CTRL+C Pressed. Shutting down the server...")

    except Exception as e:
        print(f"Unexpected shutdown...")
        print(f"ERROR: {e}")
        hubbt.sock.close()
        raise e

if __name__ == "__main__":
    main()
