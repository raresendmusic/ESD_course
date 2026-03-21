from dataclasses import dataclass

@dataclass
class HikeSession:
    session_id: str = ""
    start_time: str = ""
    end_time: str = ""
    steps: int = 0
    distance_m: int = 0
    duration_s: int = 0
    created_at: str = ""

def to_list(s: HikeSession) -> list:
    return [
        s.session_id,
        s.start_time,
        s.end_time,
        s.steps,
        s.distance_m,
        s.duration_s,
        s.created_at,
    ]

def from_list(l: list) -> HikeSession:
    s = HikeSession()
    s.session_id = l[0]
    s.start_time = l[1]
    s.end_time = l[2]
    s.steps = l[3]
    s.distance_m = l[4]
    s.duration_s = l[5]
    s.created_at = l[6]
    return s
