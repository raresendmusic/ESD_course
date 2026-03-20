class HikeSession:
    session_id = ""
    start_time = ""
    end_time = ""
    steps = 0
    distance_m = 0
    duration_s = 0

    def __repr__(self):
        return (
            f"HikeSession{{session_id={self.session_id}, "
            f"start_time={self.start_time}, end_time={self.end_time}, "
            f"steps={self.steps}, distance_m={self.distance_m}, "
            f"duration_s={self.duration_s}}}"
        )

def to_list(s: HikeSession) -> list:
    return [
        s.session_id,
        s.start_time,
        s.end_time,
        s.steps,
        s.distance_m,
        s.duration_s,
    ]

def from_list(l: list) -> HikeSession:
    s = HikeSession()
    s.session_id = l[0]
    s.start_time = l[1]
    s.end_time = l[2]
    s.steps = l[3]
    s.distance_m = l[4]
    s.duration_s = l[5]
    return s
