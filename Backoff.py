from __future__ import annotations

import time


class Backoff:
    def __init__(self, timeout_mins: float, backoff_secs: float):
        self.start_time = time.time()
        self.timeout_mins = timeout_mins
        self.backoff_secs = backoff_secs

    def timeout(self):
        return time.time() - self.start_time > self.timeout_mins * 60

    def backoff(self):
        time.sleep(self.backoff_secs)
