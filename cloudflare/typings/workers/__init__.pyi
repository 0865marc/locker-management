"""Typed subset used by this experiment, checked against workers-runtime-sdk1.9.4.

The runtime's Env and ExecutionContext are generated JavaScript types. Keeping
these opaque forces the application to cross its explicit Protocol boundary.
No runtime implementation is replaced by this analysis-only package.
"""

from . import asgi as asgi

class Request:
    def __init__(self, input: str) -> None: ...

class Context: ...

class WorkerEntrypoint:
    env: object
    ctx: Context

    def __init__(self, ctx: Context, env: object) -> None: ...
