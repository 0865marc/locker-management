"""Time application import inside the real Workers isolate."""

import importlib
from typing import Protocol, cast

import import_clock
from workers import WorkerEntrypoint


class ApplicationModule(Protocol):
    Default: type[WorkerEntrypoint]


# The timestamp is initialized before loading FastAPI and the real schemas.
assert import_clock.STARTED > 0
application = cast(ApplicationModule, importlib.import_module("worker"))
Default = application.Default
