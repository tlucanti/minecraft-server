from __future__ import annotations

from typing import Callable
from cprint import *


class Saga:
    def __init__(self):
        self.compensations = []
        self.defers = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            DEBUG("running compensation steps")
            for compensation in reversed(self.compensations):
                compensation()

        for defer in reversed(self.defers):
            defer()

        if exc_type is not None:
            DEBUG(exc_type)
            raise

        return False

    def compensation(self, compensation):
        self.compensations.append(compensation)

    def defer(self, action):
        self.defers.append(action)
