"""Loaded by bootstrap before application dependencies, with no event bindings."""

from time import perf_counter

STARTED = perf_counter()


def elapsed_ms(started: float, ended: float) -> tuple[float | None, str | None]:
    delta = ended - started
    if delta > 0:
        return delta * 1000, None
    return None, "runtime clock did not advance"
