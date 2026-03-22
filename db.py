import sqlite3
import threading
import hike
import os
from dotenv import load_dotenv

load_dotenv()

DB_FILE_NAME = os.environ.get("HIKING_DB_PATH", "sessions.db")
LOG_FILE_NAME = "hiking_log.txt"

DB_SESSION_TABLE = {
    "name": "sessions",
    "cols": [
        "session_id text PRIMARY KEY",
        "start_time text",
        "end_time text",
        "steps integer",
        "distance_m integer",
        "duration_s integer",
        "created_at text",
    ]
}


class HubDatabase:
    lock = threading.Lock()

    def __init__(self):
        self.con = sqlite3.connect(DB_FILE_NAME, check_same_thread=False)
        self.cur = self.con.cursor()

        create_table_sql = (
            f"CREATE TABLE IF NOT EXISTS {DB_SESSION_TABLE['name']} "
            f"({', '.join(DB_SESSION_TABLE['cols'])})"
        )
        self.cur.execute(create_table_sql)
        self.con.commit()

    
    def save(self, s: hike.HikeSession):
        try:
            self.lock.acquire()

            try:
                self.cur.execute(
                    f"""INSERT INTO {DB_SESSION_TABLE['name']}
                    (session_id, start_time, end_time, steps, distance_m, duration_s, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        s.session_id,
                        s.start_time,
                        s.end_time,
                        s.steps,
                        s.distance_m,
                        s.duration_s,
                        s.created_at,
                    ),
                )
                self.con.commit()
            except sqlite3.IntegrityError:
                print("WARNING: Session ID already exists in database! Aborting saving current session.")
                return

            try:
                with open(LOG_FILE_NAME, "a") as f:
                    log_entry = (
                        f"{s.session_id} | {s.start_time} | {s.end_time} | "
                        f"{s.steps} | {s.distance_m} | {s.duration_s} | {s.created_at}\n"
                    )
                    f.write(log_entry)
            except Exception:
                print("Error writing file")
        finally:
            self.lock.release()

    def delete(self, session_id: str):
        try:
            self.lock.acquire()
            self.cur.execute(
                f"DELETE FROM {DB_SESSION_TABLE['name']} WHERE session_id = ?",
                (session_id,),
            )
            self.con.commit()
        finally:
            self.lock.release()

    def get_sessions(self) -> list[hike.HikeSession]:
        try:
            self.lock.acquire()
            rows = self.cur.execute(
                f"SELECT * FROM {DB_SESSION_TABLE['name']}"
            ).fetchall()
        finally:
            self.lock.release()

        return [hike.from_list(r) for r in rows]

    def get_session(self, session_id: str) -> hike.HikeSession | None:
        try:
            self.lock.acquire()
            rows = self.cur.execute(
                f"SELECT * FROM {DB_SESSION_TABLE['name']} WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        finally:
            self.lock.release()

        if not rows:
            return None

        return hike.from_list(rows[0])

    def close(self):
        self.cur.close()
        self.con.close()
